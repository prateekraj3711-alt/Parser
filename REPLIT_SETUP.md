# Replit Setup Guide

This guide will help you deploy the Candidate Parser application on Replit.

## Quick Start

### 1. Create a New Replit Project

1. Go to [Replit](https://replit.com)
2. Click "Create Repl"
3. Select "Python" template
4. Name it "candidate-parser"

### 2. Upload Files

Upload all files from the `candidate-parser` directory to your Replit project:
- `main.py`
- `config.py`
- `requirements.txt`
- `parser/` directory
- `integrations/` directory
- `README.md` (optional)

### 3. Set Environment Variables

In Replit, go to **Secrets** (lock icon in left sidebar) and add:

```
WATCH_FOLDER=/data/candidates
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
SV_PORTAL_URL=https://admin.example.com
SV_ADMIN_EMAIL=admin@example.com
SV_ADMIN_PASSWORD=your_password_here
```

**Note:** For `GOOGLE_SERVICE_ACCOUNT_JSON`, you can either:
- Paste the entire JSON as a string
- Or upload the JSON file and reference it in code (you'll need to modify `config.py`)

### 4. Install Dependencies

In the Replit Shell, run:

```bash
pip install -r requirements.txt
```

**Note:** For OCR support, you may need to install system packages. In Replit's Shell:

```bash
# Install Tesseract (if available)
# Note: Replit may have limitations on system packages
# You might need to use Replit's package manager or install via apt if available
```

### 5. Install Playwright Browsers

```bash
playwright install chromium
```

### 6. Create Watch Folder

```bash
mkdir -p /data/candidates
```

Or create the folder through Replit's file explorer.

### 7. Create Keep-Alive Script (Optional)

Create a file `keep_alive.py`:

```python
from flask import Flask
from threading import Thread
import requests
import time

app = Flask(__name__)

@app.route('/')
def home():
    return "Keep-alive server running"

def ping():
    while True:
        try:
            requests.get("https://your-repl-url.repl.co/keep_alive")
        except:
            pass
        time.sleep(50)  # Ping every 50 seconds

Thread(target=ping).start()
app.run(host='0.0.0.0', port=8080)
```

### 8. Run the Application

In Replit, click the **Run** button or run:

```bash
python main.py
```

The application will:
- Start watching `/data/candidates` folder
- Process any existing files
- Start Flask server on port 8080
- Keep running 24/7 (if using Replit Core plan)

### 9. Configure Replit for 24/7 Operation

For Replit Core plan:

1. The Flask keep_alive endpoint at `/keep_alive` will keep the app alive
2. You can also set up a simple HTTP ping service
3. Use Replit's "Always On" feature if available

**Alternative:** Use a free service like [UptimeRobot](https://uptimerobot.com) to ping your `/keep_alive` endpoint every 5 minutes.

## Testing

### Test File Upload

1. Place a test PDF or DOCX file in `/data/candidates`
2. Check the console logs for processing status
3. Verify data appears in Google Sheets
4. Check SV Portal for uploaded candidate

### Test Keep-Alive

Visit: `https://your-repl-url.repl.co/keep_alive`

Should return:
```json
{
  "status": "alive",
  "timestamp": "2024-01-01T12:00:00"
}
```

## Troubleshooting

### Application Stops After Inactivity

- Ensure the keep_alive endpoint is being pinged regularly
- Check Replit's plan limits
- Consider using an external ping service

### Google Sheets Upload Fails

- Verify service account JSON is correctly formatted in Secrets
- Ensure the Google Sheet is shared with the service account email
- Check sheet ID is correct (from URL)

### Playwright Not Working

- Ensure Chromium is installed: `playwright install chromium`
- Check if Replit allows browser automation
- Fall back to API-only mode if needed

### LLaMA Model Not Loading

- Models are large - ensure you have enough storage
- Download model separately and upload to Replit
- Application works without LLaMA (deterministic extraction only)

### OCR Not Working

- Replit may have limitations on system packages
- Consider using cloud OCR services as alternative
- Or pre-process PDFs to extract text before uploading

## File Structure in Replit

```
/
├── main.py
├── config.py
├── requirements.txt
├── parser/
│   ├── __init__.py
│   └── llama_parser.py
├── integrations/
│   ├── __init__.py
│   ├── sheets.py
│   └── sv_portal.py
├── /data/
│   └── candidates/          # Watch folder
├── processed_hashes.json    # Auto-generated
└── candidate_parser.log     # Auto-generated
```

## Monitoring

### View Logs

Logs are written to:
- Console output (visible in Replit)
- `candidate_parser.log` file

### Check Status

- Health: `https://your-repl-url.repl.co/health`
- Keep-alive: `https://your-repl-url.repl.co/keep_alive`

## Production Tips

1. **Use Secrets**: Never commit credentials to code
2. **Monitor Logs**: Regularly check `candidate_parser.log`
3. **Backup Data**: Keep backups of `processed_hashes.json`
4. **Error Handling**: The app continues running even if individual uploads fail
5. **Resource Limits**: Monitor Replit's resource usage

## Support

For issues:
1. Check logs in `candidate_parser.log`
2. Review console output in Replit
3. Verify environment variables in Secrets
4. Test individual components (parser, sheets, portal)



