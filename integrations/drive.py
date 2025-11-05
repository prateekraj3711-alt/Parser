"""
Google Drive integration for fetching candidate files.
"""
import json
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io

logger = logging.getLogger(__name__)

class GoogleDriveFetcher:
    """Handler for fetching files from Google Drive."""
    
    def __init__(self, service_account_json: str, drive_folder_id: str = None):
        """
        Initialize Google Drive fetcher.
        
        Args:
            service_account_json: Path to service account JSON file or JSON string
            drive_folder_id: Google Drive folder ID to watch (optional, will use root if not specified)
        """
        self.service_account_json = service_account_json
        self.drive_folder_id = drive_folder_id
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Drive API service."""
        try:
            # Check if service_account_json is a file path or JSON string
            if isinstance(self.service_account_json, str):
                # Try to load as file first
                try:
                    with open(self.service_account_json, 'r') as f:
                        creds_data = json.load(f)
                except (FileNotFoundError, OSError):
                    # Assume it's a JSON string
                    creds_data = json.loads(self.service_account_json)
            else:
                creds_data = self.service_account_json
            
            credentials = service_account.Credentials.from_service_account_info(
                creds_data,
                scopes=[
                    'https://www.googleapis.com/auth/drive.readonly',
                    'https://www.googleapis.com/auth/drive.metadata.readonly'
                ]
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Google Drive service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise
    
    def _get_folder_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract folder ID from Google Drive URL.
        
        Args:
            url: Google Drive URL (various formats supported)
            
        Returns:
            Folder ID or None
        """
        # Handle different URL formats
        # Format 1: https://drive.google.com/drive/folders/FOLDER_ID
        # Format 2: https://drive.google.com/open?id=FOLDER_ID
        # Format 3: FOLDER_ID (direct)
        
        if not url:
            return None
        
        # If it's already just an ID
        if len(url) > 10 and '/' not in url and '?' not in url:
            return url
        
        # Extract from URL
        if 'folders/' in url:
            return url.split('folders/')[-1].split('?')[0].split('&')[0]
        elif 'id=' in url:
            return url.split('id=')[-1].split('&')[0].split('#')[0]
        
        return None
    
    def list_files(self, folder_id: str = None) -> List[Dict]:
        """
        List files in Google Drive folder.
        
        Args:
            folder_id: Folder ID to list (uses instance folder_id if not provided)
            
        Returns:
            List of file metadata dictionaries
        """
        folder_id = folder_id or self.drive_folder_id
        
        if not folder_id:
            logger.error("No folder ID provided")
            return []
        
        try:
            # Query for files in folder
            query = f"'{folder_id}' in parents and trashed=false"
            
            # Supported file types
            supported_mime_types = [
                'application/pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/msword'
            ]
            
            mime_query = " or ".join([f"mimeType='{mime}'" for mime in supported_mime_types])
            query += f" and ({mime_query})"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType, modifiedTime, size, md5Checksum)",
                orderBy="modifiedTime desc"
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Found {len(files)} files in Google Drive folder")
            return files
            
        except HttpError as e:
            logger.error(f"Error listing files from Google Drive: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing files: {e}")
            return []
    
    def download_file(self, file_id: str, file_name: str, download_path: str) -> Optional[str]:
        """
        Download a file from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            file_name: Name of the file
            download_path: Directory to save the file
            
        Returns:
            Path to downloaded file or None if failed
        """
        try:
            # Create download directory if it doesn't exist
            download_dir = Path(download_path)
            download_dir.mkdir(parents=True, exist_ok=True)
            
            # Get file metadata
            file_metadata = self.service.files().get(fileId=file_id).execute()
            mime_type = file_metadata.get('mimeType', '')
            
            # Determine file extension
            if mime_type == 'application/pdf':
                ext = '.pdf'
            elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                ext = '.docx'
            elif mime_type == 'application/msword':
                ext = '.doc'
            else:
                # Try to extract from filename
                ext = Path(file_name).suffix or '.pdf'
            
            # Clean filename and create full path
            safe_filename = "".join(c for c in file_name if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            safe_filename = Path(safe_filename).stem + ext
            file_path = download_dir / safe_filename
            
            # Download file
            request = self.service.files().get_media(fileId=file_id)
            file_handle = io.BytesIO()
            downloader = MediaIoBaseDownload(file_handle, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            # Save to disk
            file_handle.seek(0)
            with open(file_path, 'wb') as f:
                f.write(file_handle.read())
            
            logger.info(f"Downloaded file: {file_path}")
            return str(file_path)
            
        except HttpError as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading file: {e}")
            return None
    
    def get_file_hash_from_drive(self, file_id: str) -> Optional[str]:
        """
        Get file hash from Google Drive metadata (if available).
        Falls back to downloading and hashing.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            MD5 hash or None
        """
        try:
            # Try to get hash from metadata
            file_metadata = self.service.files().get(
                fileId=file_id,
                fields="md5Checksum"
            ).execute()
            
            md5_hash = file_metadata.get('md5Checksum')
            if md5_hash:
                return md5_hash
            
            # If no MD5 available, we'll need to download and hash
            # But for now, return None and let the main process handle it
            return None
            
        except Exception as e:
            logger.debug(f"Could not get hash from Drive metadata: {e}")
            return None
    
    def fetch_new_files(self, download_folder: str, processed_file_ids: set) -> List[str]:
        """
        Fetch new files from Google Drive folder.
        
        Args:
            download_folder: Local folder to download files to
            processed_file_ids: Set of already processed file IDs
            
        Returns:
            List of paths to downloaded files
        """
        files = self.list_files()
        downloaded_files = []
        
        for file_info in files:
            file_id = file_info.get('id')
            file_name = file_info.get('name', 'unknown')
            
            # Skip if already processed
            if file_id in processed_file_ids:
                logger.info(f"Skipping already processed file: {file_name}")
                continue
            
            # Download file
            file_path = self.download_file(file_id, file_name, download_folder)
            if file_path:
                downloaded_files.append(file_path)
                # Store file_id for tracking
                # We'll need to modify main.py to track by file_id instead of hash
        
        return downloaded_files

