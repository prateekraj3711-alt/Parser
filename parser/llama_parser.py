"""
LLaMA-based Profile Information Parser with deterministic fallback.
Extracts structured candidate data from PDF/DOCX files using hybrid approach.
"""
import json
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from pdfminer.high_level import extract_text as pdf_extract_text
from pdfminer.layout import LAParams
import pytesseract
from PIL import Image
import pdf2image
from docx import Document
import logging

# Optional LLaMA import
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False

logger = logging.getLogger(__name__)

if not LLAMA_AVAILABLE:
    logger.warning("llama-cpp-python not available, LLaMA parsing will be disabled")

class CandidateParser:
    """Parser for extracting candidate profile information from documents."""
    
    def __init__(self, model_path: str, n_ctx: int = 4096, n_threads: int = 4):
        """
        Initialize the parser with LLaMA model.
        
        Args:
            model_path: Path to LLaMA model file (.gguf)
            n_ctx: Context window size
            n_threads: Number of threads for inference
        """
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.llm = None
        
        # Try to load LLaMA model if available
        if not LLAMA_AVAILABLE:
            self.llm = None
            logger.warning("llama-cpp-python not installed, using deterministic parser only")
            return
        
        try:
            if Path(model_path).exists():
                self.llm = Llama(
                    model_path=model_path,
                    n_ctx=n_ctx,
                    n_threads=n_threads,
                    verbose=False
                )
                logger.info(f"Loaded LLaMA model from {model_path}")
            else:
                logger.warning(f"LLaMA model not found at {model_path}, using deterministic parser only")
        except Exception as e:
            logger.warning(f"Failed to load LLaMA model: {e}, using deterministic parser only")
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from PDF or DOCX file.
        Uses OCR as fallback for PDFs with images.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Extracted text content
        """
        file_path = Path(file_path)
        
        if file_path.suffix.lower() == '.pdf':
            try:
                # Try direct text extraction first
                text = pdf_extract_text(
                    str(file_path),
                    laparams=LAParams()
                )
                
                # If text extraction yields minimal text, try OCR
                if len(text.strip()) < 100:
                    logger.info(f"Low text content detected, attempting OCR for {file_path}")
                    images = pdf2image.convert_from_path(str(file_path))
                    ocr_text = []
                    for img in images:
                        ocr_text.append(pytesseract.image_to_string(img))
                    text = "\n\n".join(ocr_text)
                
                return text
            except Exception as e:
                logger.error(f"Error extracting text from PDF {file_path}: {e}")
                # Fallback to OCR
                try:
                    images = pdf2image.convert_from_path(str(file_path))
                    ocr_text = []
                    for img in images:
                        ocr_text.append(pytesseract.image_to_string(img))
                    return "\n\n".join(ocr_text)
                except Exception as ocr_error:
                    logger.error(f"OCR fallback failed for {file_path}: {ocr_error}")
                    return ""
        
        elif file_path.suffix.lower() in ['.docx', '.doc']:
            try:
                doc = Document(str(file_path))
                return "\n".join([paragraph.text for paragraph in doc.paragraphs])
            except Exception as e:
                logger.error(f"Error extracting text from DOCX {file_path}: {e}")
                return ""
        
        else:
            logger.warning(f"Unsupported file type: {file_path.suffix}")
            return ""
    
    def deterministic_extract(self, text: str) -> Dict[str, Any]:
        """
        Extract information using deterministic regex patterns.
        
        Args:
            text: Extracted text from document
            
        Returns:
            Dictionary with extracted fields
        """
        result = {
            "identity": {},
            "documents": {},
            "education": [],
            "experience": [],
            "addresses": {}
        }
        
        text_lower = text.lower()
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            result["identity"]["email"] = emails[0]
        
        # Extract phone numbers (Indian format: +91, 0, or 10 digits)
        phone_pattern = r'(\+91[\s-]?)?[6-9]\d{9}|\b0?[6-9]\d{9}\b'
        phones = re.findall(phone_pattern, text)
        if phones:
            phone = phones[0] if isinstance(phones[0], str) else ''.join(phones[0])
            result["identity"]["phone"] = phone.replace('-', '').replace(' ', '')
        
        # Extract PAN number
        pan_pattern = r'[A-Z]{5}[0-9]{4}[A-Z]'
        pan = re.findall(pan_pattern, text.upper())
        if pan:
            result["documents"]["pan_number"] = pan[0]
        
        # Extract UAN number (12 digits)
        uan_pattern = r'\b\d{12}\b'
        uan = re.findall(uan_pattern, text)
        if uan:
            result["documents"]["uan_number"] = uan[0]
        
        # Extract passport number
        passport_pattern = r'[A-Z]{1}[0-9]{7}|[A-Z]{2}[0-9]{7}'
        passport = re.findall(passport_pattern, text.upper())
        if passport:
            result["documents"]["passport_number"] = passport[0]
        
        # Extract DOB (various formats)
        dob_patterns = [
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',
            r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',
            r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',
        ]
        for pattern in dob_patterns:
            dob_match = re.search(pattern, text, re.IGNORECASE)
            if dob_match:
                result["identity"]["dob"] = dob_match.group(0)
                break
        
        # Extract name (common patterns: "Name:", "Candidate Name:", etc.)
        name_patterns = [
            r'(?:name|candidate name|full name)[\s:]+([A-Z][a-zA-Z\s]+)',
            r'^([A-Z][a-zA-Z\s]{2,})',
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if name_match:
                result["identity"]["name"] = name_match.group(1).strip()
                break
        
        # Extract designation/title
        designation_patterns = [
            r'(?:designation|title|position)[\s:]+([A-Za-z\s]+)',
            r'(?:software engineer|developer|manager|analyst|consultant|engineer)',
        ]
        for pattern in designation_patterns:
            desig_match = re.search(pattern, text, re.IGNORECASE)
            if desig_match:
                result["identity"]["designation"] = desig_match.group(1).strip() if desig_match.groups() else desig_match.group(0)
                break
        
        # Extract gender
        gender_match = re.search(r'\b(male|female|other|m|f)\b', text_lower)
        if gender_match:
            result["identity"]["gender"] = gender_match.group(1)
        
        # Extract nationality
        nationality_match = re.search(r'(?:nationality|citizen)[\s:]+([A-Za-z]+)', text, re.IGNORECASE)
        if nationality_match:
            result["identity"]["nationality"] = nationality_match.group(1).strip()
        
        # Extract addresses (look for address keywords)
        address_keywords = ['address', 'residence', 'location', 'city', 'state', 'pincode']
        address_lines = []
        for line in text.split('\n'):
            if any(keyword in line.lower() for keyword in address_keywords):
                address_lines.append(line.strip())
        
        if address_lines:
            result["addresses"]["current"] = " ".join(address_lines[:3])
            result["addresses"]["permanent"] = " ".join(address_lines[3:6]) if len(address_lines) > 3 else result["addresses"]["current"]
        
        return result
    
    def llama_extract(self, text: str) -> Dict[str, Any]:
        """
        Extract information using LLaMA model.
        
        Args:
            text: Extracted text from document
            
        Returns:
            Dictionary with extracted fields
        """
        if not self.llm:
            return {}
        
        prompt = f"""Extract candidate profile information from the following text and return ONLY valid JSON in this exact format:
{{
  "identity": {{
    "candidate_id": "",
    "name": "",
    "designation": "",
    "email": "",
    "phone": "",
    "dob": "",
    "gender": "",
    "nationality": ""
  }},
  "documents": {{
    "pan_number": "",
    "uan_number": "",
    "passport_number": "",
    "valid_from": "",
    "valid_to": ""
  }},
  "education": [
    {{
      "degree": "",
      "institution": "",
      "year": "",
      "percentage": ""
    }}
  ],
  "experience": [
    {{
      "company": "",
      "position": "",
      "duration": "",
      "description": ""
    }}
  ],
  "addresses": {{
    "current": "",
    "permanent": ""
  }}
}}

Text:
{text[:3000]}

Return ONLY the JSON object, no other text:"""
        
        try:
            response = self.llm(
                prompt,
                max_tokens=2000,
                temperature=0.1,
                stop=["\n\n", "Text:"],
                echo=False
            )
            
            generated_text = response['choices'][0]['text'].strip()
            
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', generated_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return json.loads(generated_text)
        except Exception as e:
            logger.error(f"LLaMA extraction failed: {e}")
            return {}
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse candidate profile file and return structured JSON.
        Uses hybrid approach: deterministic + LLaMA.
        
        Args:
            file_path: Path to the candidate file
            
        Returns:
            Structured candidate data as dictionary
        """
        logger.info(f"Parsing file: {file_path}")
        
        # Extract text
        text = self.extract_text(file_path)
        if not text:
            logger.warning(f"No text extracted from {file_path}")
            return {}
        
        # Get deterministic extraction
        deterministic_result = self.deterministic_extract(text)
        
        # Get LLaMA extraction if available
        llama_result = self.llama_extract(text) if self.llm else {}
        
        # Merge results (LLaMA takes precedence, deterministic fills gaps)
        result = deterministic_result.copy()
        
        # Merge identity
        if llama_result.get("identity"):
            for key, value in llama_result["identity"].items():
                if value and value != "":
                    result["identity"][key] = value
            # Ensure all keys exist
            for key in ["candidate_id", "name", "designation", "email", "phone", "dob", "gender", "nationality"]:
                if key not in result["identity"]:
                    result["identity"][key] = ""
        
        # Merge documents
        if llama_result.get("documents"):
            for key, value in llama_result["documents"].items():
                if value and value != "":
                    result["documents"][key] = value
            for key in ["pan_number", "uan_number", "passport_number", "valid_from", "valid_to"]:
                if key not in result["documents"]:
                    result["documents"][key] = ""
        
        # Merge education and experience
        if llama_result.get("education"):
            result["education"] = llama_result["education"]
        if llama_result.get("experience"):
            result["experience"] = llama_result["experience"]
        
        # Merge addresses
        if llama_result.get("addresses"):
            if llama_result["addresses"].get("current"):
                result["addresses"]["current"] = llama_result["addresses"]["current"]
            if llama_result["addresses"].get("permanent"):
                result["addresses"]["permanent"] = llama_result["addresses"]["permanent"]
        
        # Generate candidate_id if missing
        if not result["identity"].get("candidate_id"):
            # Use hash of file path or email
            candidate_id_source = result["identity"].get("email") or file_path
            result["identity"]["candidate_id"] = hashlib.md5(candidate_id_source.encode()).hexdigest()[:8].upper()
        
        logger.info(f"Successfully parsed {file_path}")
        return result

