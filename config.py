"""
Configuration module for loading environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration from environment variables."""
    
    # Watch folder for candidate files
    WATCH_FOLDER = os.getenv("WATCH_FOLDER", "/data/candidates")
    
    # Google Sheets configuration
    GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    
    # SV Admin Portal configuration
    SV_PORTAL_URL = os.getenv("SV_PORTAL_URL")
    SV_ADMIN_EMAIL = os.getenv("SV_ADMIN_EMAIL")
    SV_ADMIN_PASSWORD = os.getenv("SV_ADMIN_PASSWORD")
    
    # LLaMA model configuration
    LLAMA_MODEL_PATH = os.getenv("LLAMA_MODEL_PATH", "models/llama-model.gguf")
    LLAMA_N_CTX = int(os.getenv("LLAMA_N_CTX", "4096"))
    LLAMA_N_THREADS = int(os.getenv("LLAMA_N_THREADS", "4"))
    
    # Processing configuration
    PROCESSED_HASHES_FILE = os.getenv("PROCESSED_HASHES_FILE", "processed_hashes.json")
    LOG_FILE = os.getenv("LOG_FILE", "candidate_parser.log")
    
    # Flask keep_alive configuration
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "8080"))
    
    @classmethod
    def validate(cls):
        """Validate required configuration values."""
        required = [
            "GOOGLE_SHEET_ID",
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            "SV_PORTAL_URL",
            "SV_ADMIN_EMAIL",
            "SV_ADMIN_PASSWORD"
        ]
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return True



