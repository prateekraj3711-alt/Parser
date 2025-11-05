"""
Google Sheets integration for writing candidate data.
"""
import json
import logging
from typing import Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleSheetsWriter:
    """Handler for writing candidate data to Google Sheets."""
    
    def __init__(self, sheet_id: str, service_account_json: str):
        """
        Initialize Google Sheets writer.
        
        Args:
            sheet_id: Google Sheets spreadsheet ID
            service_account_json: Path to service account JSON file or JSON string
        """
        self.sheet_id = sheet_id
        self.service_account_json = service_account_json
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Sheets API service."""
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
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Google Sheets service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}")
            raise
    
    def _flatten_candidate_data(self, data: Dict[str, Any]) -> list:
        """
        Flatten nested candidate data into a row format.
        
        Args:
            data: Structured candidate data
            
        Returns:
            List of values for one row
        """
        row = []
        
        # Identity fields
        identity = data.get("identity", {})
        row.extend([
            identity.get("candidate_id", ""),
            identity.get("name", ""),
            identity.get("designation", ""),
            identity.get("email", ""),
            identity.get("phone", ""),
            identity.get("dob", ""),
            identity.get("gender", ""),
            identity.get("nationality", "")
        ])
        
        # Document fields
        documents = data.get("documents", {})
        row.extend([
            documents.get("pan_number", ""),
            documents.get("uan_number", ""),
            documents.get("passport_number", ""),
            documents.get("valid_from", ""),
            documents.get("valid_to", "")
        ])
        
        # Education (serialize as JSON string)
        education = data.get("education", [])
        row.append(json.dumps(education) if education else "")
        
        # Experience (serialize as JSON string)
        experience = data.get("experience", [])
        row.append(json.dumps(experience) if experience else "")
        
        # Addresses
        addresses = data.get("addresses", {})
        row.extend([
            addresses.get("current", ""),
            addresses.get("permanent", "")
        ])
        
        return row
    
    def _ensure_headers(self):
        """Ensure header row exists in the sheet."""
        headers = [
            "Candidate ID", "Name", "Designation", "Email", "Phone", "DOB", "Gender", "Nationality",
            "PAN Number", "UAN Number", "Passport Number", "Valid From", "Valid To",
            "Education", "Experience", "Current Address", "Permanent Address"
        ]
        
        try:
            # Check if headers exist
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='A1:Q1'
            ).execute()
            
            existing_headers = result.get('values', [])
            if not existing_headers or len(existing_headers[0]) < len(headers):
                # Write headers
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range='A1:Q1',
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()
                logger.info("Headers written to Google Sheet")
        except HttpError as e:
            logger.error(f"Error ensuring headers: {e}")
            raise
    
    def append_candidate(self, candidate_data: Dict[str, Any]) -> bool:
        """
        Append candidate data as a new row to Google Sheets.
        
        Args:
            candidate_data: Structured candidate data dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure headers exist
            self._ensure_headers()
            
            # Flatten data
            row = self._flatten_candidate_data(candidate_data)
            
            # Append row
            body = {
                'values': [row]
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range='A:Q',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            logger.info(f"Successfully appended candidate to Google Sheets: {candidate_data.get('identity', {}).get('candidate_id', 'unknown')}")
            return True
            
        except HttpError as e:
            logger.error(f"Error appending to Google Sheets: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing to Google Sheets: {e}")
            return False



