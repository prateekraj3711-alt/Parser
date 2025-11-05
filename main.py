"""
Main orchestrator for candidate parser application.
Watches folder for new files, parses them, and uploads to Google Sheets and SV Portal.
"""
import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from flask import Flask, jsonify
import threading

try:
    from config import Config
    from parser.llama_parser import CandidateParser
    from integrations.sheets import GoogleSheetsWriter
    from integrations.sv_portal import SVPortalUploader
    from integrations.drive import GoogleDriveFetcher
except ImportError:
    # Fallback for running from parent directory
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from config import Config
    from parser.llama_parser import CandidateParser
    from integrations.sheets import GoogleSheetsWriter
    from integrations.sv_portal import SVPortalUploader
    from integrations.drive import GoogleDriveFetcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CandidateFileHandler(FileSystemEventHandler):
    """Handler for file system events in the watch folder."""
    
    def __init__(self, parser, sheets_writer, portal_uploader, processed_hashes_file):
        """
        Initialize the file handler.
        
        Args:
            parser: CandidateParser instance
            sheets_writer: GoogleSheetsWriter instance
            portal_uploader: SVPortalUploader instance
            processed_hashes_file: Path to file storing processed file hashes
        """
        super().__init__()
        self.parser = parser
        self.sheets_writer = sheets_writer
        self.portal_uploader = portal_uploader
        self.processed_hashes_file = processed_hashes_file
        self.processed_hashes, self.processed_drive_ids = self._load_processed_hashes()
        self.supported_extensions = {'.pdf', '.docx', '.doc'}
    
    def _load_processed_hashes(self) -> set:
        """Load set of processed file hashes and Drive file IDs."""
        try:
            if os.path.exists(self.processed_hashes_file):
                with open(self.processed_hashes_file, 'r') as f:
                    data = json.load(f)
                    hashes = set(data.get('hashes', []))
                    # Also load Drive file IDs if present
                    drive_ids = set(data.get('drive_file_ids', []))
                    return hashes, drive_ids
        except Exception as e:
            logger.error(f"Error loading processed hashes: {e}")
        return set(), set()
    
    def _save_processed_hashes(self):
        """Save processed file hashes and Drive file IDs to file."""
        try:
            hashes = self.processed_hashes if isinstance(self.processed_hashes, set) else set()
            drive_ids = self.processed_drive_ids if hasattr(self, 'processed_drive_ids') else set()
            data = {
                'hashes': list(hashes),
                'drive_file_ids': list(drive_ids)
            }
            with open(self.processed_hashes_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving processed hashes: {e}")
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    def _is_duplicate(self, file_path: str) -> bool:
        """Check if file has already been processed."""
        file_hash = self._calculate_file_hash(file_path)
        if file_hash in self.processed_hashes:
            logger.info(f"File already processed (duplicate): {file_path}")
            return True
        return False
    
    def _mark_as_processed(self, file_path: str, drive_file_id: str = None):
        """Mark file as processed by adding its hash and optionally Drive file ID."""
        file_hash = self._calculate_file_hash(file_path)
        if file_hash:
            self.processed_hashes.add(file_hash)
        if drive_file_id:
            if not hasattr(self, 'processed_drive_ids'):
                self.processed_drive_ids = set()
            self.processed_drive_ids.add(drive_file_id)
        self._save_processed_hashes()
    
    def _process_file(self, file_path: str):
        """
        Process a candidate file: parse, upload to Sheets and Portal.
        
        Args:
            file_path: Path to the candidate file
        """
        file_path_obj = Path(file_path)
        
        # Check if file extension is supported
        if file_path_obj.suffix.lower() not in self.supported_extensions:
            logger.info(f"Skipping unsupported file type: {file_path}")
            return
        
        # Check if file is a duplicate
        if self._is_duplicate(file_path):
            return
        
        # Wait for file to be fully written (if file is still being written)
        try:
            # Check file size stability
            size1 = file_path_obj.stat().st_size
            import time
            time.sleep(1)
            size2 = file_path_obj.stat().st_size
            if size1 != size2:
                logger.info(f"File still being written, waiting: {file_path}")
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Error checking file stability: {e}")
        
        logger.info(f"Processing new candidate file: {file_path}")
        
        try:
            # Parse the file
            candidate_data = self.parser.parse(file_path)
            
            if not candidate_data or not candidate_data.get("identity"):
                logger.warning(f"No data extracted from {file_path}")
                return
            
            # Log parsed data
            candidate_id = candidate_data.get("identity", {}).get("candidate_id", "unknown")
            logger.info(f"Parsed candidate: {candidate_id}")
            
            # Upload to Google Sheets
            sheets_success = False
            try:
                sheets_success = self.sheets_writer.append_candidate(candidate_data)
                if sheets_success:
                    logger.info(f"Successfully uploaded {candidate_id} to Google Sheets")
                else:
                    logger.error(f"Failed to upload {candidate_id} to Google Sheets")
            except Exception as e:
                logger.error(f"Error uploading to Google Sheets: {e}")
            
            # Upload to SV Portal (if configured)
            portal_success = False
            if self.portal_uploader:
                try:
                    portal_success = self.portal_uploader.upload_candidate(candidate_data)
                    if portal_success:
                        logger.info(f"Successfully uploaded {candidate_id} to SV Portal")
                    else:
                        logger.error(f"Failed to upload {candidate_id} to SV Portal")
                except Exception as e:
                    logger.error(f"Error uploading to SV Portal: {e}")
            else:
                logger.info(f"Skipping SV Portal upload (not configured)")
            
            # Mark as processed if at least one upload succeeded
            if sheets_success or portal_success:
                self._mark_as_processed(file_path)
                logger.info(f"Successfully processed {file_path}")
            else:
                if self.portal_uploader:
                    logger.error(f"Failed to process {file_path} - both uploads failed")
                else:
                    logger.error(f"Failed to process {file_path} - Google Sheets upload failed")
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
    
    def on_created(self, event):
        """Handle file creation event."""
        if not event.is_directory:
            self._process_file(event.src_path)
    
    def on_modified(self, event):
        """Handle file modification event."""
        if not event.is_directory:
            # Only process if file is new (not just modified)
            # This prevents re-processing files that are being written
            pass

class CandidateWatcher:
    """Main watcher class that monitors the folder and processes files."""
    
    def __init__(self):
        """Initialize the watcher with all components."""
        # Validate configuration (SV Portal optional)
        Config.validate(require_sv_portal=False)
        
        # Initialize parser
        self.parser = CandidateParser(
            model_path=Config.LLAMA_MODEL_PATH,
            n_ctx=Config.LLAMA_N_CTX,
            n_threads=Config.LLAMA_N_THREADS
        )
        
        # Initialize Google Sheets writer
        self.sheets_writer = GoogleSheetsWriter(
            sheet_id=Config.GOOGLE_SHEET_ID,
            service_account_json=Config.GOOGLE_SERVICE_ACCOUNT_JSON
        )
        
        # Initialize SV Portal uploader (optional)
        self.portal_uploader = None
        if Config.SV_PORTAL_URL and Config.SV_ADMIN_EMAIL and Config.SV_ADMIN_PASSWORD:
            self.portal_uploader = SVPortalUploader(
                portal_url=Config.SV_PORTAL_URL,
                email=Config.SV_ADMIN_EMAIL,
                password=Config.SV_ADMIN_PASSWORD
            )
            logger.info("SV Portal uploader initialized")
        else:
            logger.info("SV Portal not configured - skipping portal uploads")
        
        # Initialize Google Drive fetcher (optional)
        self.drive_fetcher = None
        drive_folder_id = Config.GOOGLE_DRIVE_FOLDER_ID
        
        # Extract folder ID from URL if provided
        if not drive_folder_id and Config.GOOGLE_DRIVE_FOLDER_URL:
            # Extract folder ID from common URL formats
            url = Config.GOOGLE_DRIVE_FOLDER_URL
            if 'folders/' in url:
                drive_folder_id = url.split('folders/')[-1].split('?')[0].split('&')[0]
            elif 'id=' in url:
                drive_folder_id = url.split('id=')[-1].split('&')[0].split('#')[0]
            elif len(url) > 10 and '/' not in url and '?' not in url:
                # Already an ID
                drive_folder_id = url
        
        if drive_folder_id:
            self.drive_fetcher = GoogleDriveFetcher(
                service_account_json=Config.GOOGLE_SERVICE_ACCOUNT_JSON,
                drive_folder_id=drive_folder_id
            )
            logger.info(f"Google Drive fetcher initialized for folder: {drive_folder_id}")
        else:
            logger.info("Google Drive not configured - will only watch local folder")
        
        # Initialize file handler
        self.event_handler = CandidateFileHandler(
            parser=self.parser,
            sheets_writer=self.sheets_writer,
            portal_uploader=self.portal_uploader,
            processed_hashes_file=Config.PROCESSED_HASHES_FILE
        )
        
        # Initialize observer
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            Config.WATCH_FOLDER,
            recursive=False
        )
        
        # Drive polling thread
        self.drive_polling_active = False
        self.drive_thread = None
    
    def start(self):
        """Start watching the folder."""
        # Ensure watch folder exists
        watch_path = Path(Config.WATCH_FOLDER)
        watch_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Starting to watch folder: {Config.WATCH_FOLDER}")
        
        # Process any existing files in the folder
        self._process_existing_files()
        
        # Start observer
        self.observer.start()
        logger.info("File watcher started")
        
        # Start Google Drive polling if configured
        if self.drive_fetcher:
            self.drive_polling_active = True
            self.drive_thread = threading.Thread(target=self._drive_poll_loop, daemon=True)
            self.drive_thread.start()
            logger.info(f"Google Drive polling started (interval: {Config.DRIVE_POLL_INTERVAL}s)")
    
    def _drive_poll_loop(self):
        """Continuously poll Google Drive for new files."""
        import time
        
        while self.drive_polling_active:
            try:
                logger.info("Polling Google Drive for new files...")
                
                # Get processed Drive file IDs
                processed_ids = self.event_handler.processed_drive_ids if hasattr(self.event_handler, 'processed_drive_ids') else set()
                
                # List files in Drive
                files = self.drive_fetcher.list_files()
                
                for file_info in files:
                    file_id = file_info.get('id')
                    
                    # Skip if already processed
                    if file_id in processed_ids:
                        continue
                    
                    # Download file
                    logger.info(f"Downloading new file from Drive: {file_info.get('name')}")
                    file_path = self.drive_fetcher.download_file(
                        file_id=file_id,
                        file_name=file_info.get('name', 'unknown'),
                        download_path=Config.WATCH_FOLDER
                    )
                    
                    if file_path:
                        # Mark Drive file ID as processed
                        if not hasattr(self.event_handler, 'processed_drive_ids'):
                            self.event_handler.processed_drive_ids = set()
                        self.event_handler.processed_drive_ids.add(file_id)
                        self.event_handler._save_processed_hashes()
                        
                        # The file watcher will pick it up automatically
                        logger.info(f"Downloaded file from Drive: {file_path}")
                
                # Wait before next poll
                time.sleep(Config.DRIVE_POLL_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in Drive polling: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute before retrying on error
    
    def _process_existing_files(self):
        """Process any existing files in the watch folder."""
        watch_path = Path(Config.WATCH_FOLDER)
        if watch_path.exists():
            files = list(watch_path.glob("*"))
            for file_path in files:
                if file_path.is_file() and file_path.suffix.lower() in {'.pdf', '.docx', '.doc'}:
                    logger.info(f"Processing existing file: {file_path}")
                    self.event_handler._process_file(str(file_path))
    
    def stop(self):
        """Stop watching the folder."""
        self.drive_polling_active = False
        if self.drive_thread:
            self.drive_thread.join(timeout=5)
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped")

# Flask app for keep_alive endpoint
app = Flask(__name__)
watcher_instance = None

@app.route('/')
def index():
    """Health check endpoint."""
    return jsonify({
        "status": "running",
        "service": "Candidate Parser",
        "watch_folder": Config.WATCH_FOLDER
    })

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})

@app.route('/keep_alive')
def keep_alive():
    """Keep-alive endpoint for Replit."""
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    })

def run_flask_app():
    """Run Flask app in a separate thread."""
    app.run(host=Config.FLASK_HOST, port=Config.FLASK_PORT, debug=False)

def main():
    """Main entry point."""
    global watcher_instance
    
    logger.info("Starting Candidate Parser Application")
    
    # Initialize and start watcher
    watcher_instance = CandidateWatcher()
    watcher_instance.start()
    
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    logger.info(f"Flask keep_alive server started on {Config.FLASK_HOST}:{Config.FLASK_PORT}")
    
    try:
        # Keep main thread alive
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        watcher_instance.stop()
        logger.info("Application stopped")

if __name__ == "__main__":
    main()

