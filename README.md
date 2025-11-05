# Candidate Profile Parser

A Replit-ready Python application that continuously watches a folder for new candidate profile files (PDF/DOCX), parses them using a hybrid LLaMA-based extractor, and pushes structured data to Google Sheets and SV Admin Portal.

## Features

- 📁 **Folder Watching**: Automatically detects new candidate files using `watchdog`
- 📄 **Multi-format Support**: Parses PDF and DOCX files with OCR fallback
- 🤖 **Hybrid Extraction**: Combines deterministic regex patterns with LLaMA-based parsing
- 📊 **Google Sheets Integration**: Appends parsed data to Google Sheets
- 🔗 **SV Portal Integration**: Uploads data via API or Playwright automation
- 🚫 **Duplicate Detection**: Tracks processed files using SHA256 hashing
- 📝 **Comprehensive Logging**: Timestamped logs for all operations
- 🔄 **Keep-Alive Endpoint**: Flask server for Replit's 24/7 operation

## Project Structure

```
candidate-parser/
├── main.py                 # Main orchestrator
├── config.py               # Configuration loader
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── parser/
│   ├── __init__.py
│   └── llama_parser.py    # LLaMA-based parser
├── integrations/
│   ├── __init__.py
│   ├── sheets.py          # Google Sheets writer
│   └── sv_portal.py       # SV Portal uploader
├── example_output.json    # Example parsed output
└── README.md             # This file
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install System Dependencies (for OCR)

**On Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils
```

**On macOS:**
```bash
brew install tesseract poppler
```

**On Windows:**
- Download Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
- Download Poppler from: https://github.com/oschwartz10612/poppler-windows/releases
- Add to PATH

### 3. Install Playwright Browsers

```bash
playwright install chromium
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
WATCH_FOLDER=/data/candidates
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_SERVICE_ACCOUNT_JSON=path/to/service-account.json
SV_PORTAL_URL=https://admin.example.com
SV_ADMIN_EMAIL=admin@example.com
SV_ADMIN_PASSWORD=your_password_here
```

### 5. Google Sheets Setup

1. Create a Google Cloud Project
2. Enable Google Sheets API
3. Create a Service Account
4. Download the service account JSON key
5. Share your Google Sheet with the service account email
6. Set `GOOGLE_SERVICE_ACCOUNT_JSON` to the JSON file path or JSON string

### 6. LLaMA Model (Optional)

The application works without a LLaMA model (using deterministic extraction only). To use LLaMA:

1. Download a compatible `.gguf` model (e.g., from Hugging Face)
2. Place it in `models/` directory
3. Set `LLAMA_MODEL_PATH` in `.env`

Example models:
- `llama-2-7b-chat.gguf`
- `mistral-7b-instruct-v0.1.gguf`

## Usage

### Running Locally

```bash
python main.py
```

The application will:
1. Start watching the configured folder
2. Process any existing files
3. Process new files as they appear
4. Start Flask server on port 8080

### Running on Replit

1. Upload all files to Replit
2. Install dependencies: `pip install -r requirements.txt`
3. Set environment variables in Replit Secrets
4. Run: `python main.py`

The Flask keep_alive endpoint at `/keep_alive` will keep the app running on Replit's Core plan.

### Health Check

Visit `http://localhost:8080/health` to check if the service is running.

## API Endpoints

- `GET /` - Service status
- `GET /health` - Health check
- `GET /keep_alive` - Keep-alive for Replit

## Output Format

The parser extracts structured JSON data:

```json
{
  "identity": {
    "candidate_id": "A1B2C3D4",
    "name": "John Doe",
    "designation": "Software Engineer",
    "email": "john.doe@example.com",
    "phone": "+919876543210",
    "dob": "1990-05-15",
    "gender": "Male",
    "nationality": "Indian"
  },
  "documents": {
    "pan_number": "ABCDE1234F",
    "uan_number": "123456789012",
    "passport_number": "A1234567",
    "valid_from": "2020-01-01",
    "valid_to": "2030-01-01"
  },
  "education": [...],
  "experience": [...],
  "addresses": {
    "current": "...",
    "permanent": "..."
  }
}
```

See `example_output.json` for a complete example.

## Logging

Logs are written to:
- Console output
- File: `candidate_parser.log` (configurable via `LOG_FILE`)

Each log entry includes:
- Timestamp
- Filename
- Success/error status
- Detailed error messages

## Duplicate Detection

The application uses SHA256 hashing to track processed files. Processed hashes are stored in `processed_hashes.json`. This prevents:
- Re-processing the same file
- Processing files that are still being written

## Troubleshooting

### Google Sheets Upload Fails
- Verify service account JSON is correct
- Ensure sheet is shared with service account email
- Check sheet ID is correct (from URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`)

### SV Portal Upload Fails
- API upload: Check portal URL and authentication
- Playwright upload: Verify login credentials and form structure
- Check logs for detailed error messages

### LLaMA Model Not Loading
- Verify model path is correct
- Ensure model file is `.gguf` format
- Check available disk space and memory
- Application will fall back to deterministic extraction

### OCR Not Working
- Install Tesseract OCR system package
- Set `TESSDATA_PREFIX` environment variable if needed
- Verify PDF contains images (OCR only used when text extraction fails)

## Development

### Testing

1. Place a test PDF/DOCX in the watch folder
2. Monitor logs for processing
3. Check Google Sheets for new row
4. Verify SV Portal upload

### Adding Custom Fields

Edit `parser/llama_parser.py`:
- Add regex patterns in `deterministic_extract()`
- Update LLaMA prompt in `llama_extract()`
- Update output schema

### Extending Integrations

- Add new uploaders in `integrations/`
- Import and use in `main.py`
- Update configuration as needed

## License

This project is provided as-is for internal use.

## Support

For issues or questions, check the logs in `candidate_parser.log` for detailed error messages.



