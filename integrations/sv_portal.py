"""
SV Admin Portal integration using API or Playwright automation.
"""
import json
import logging
import time
from typing import Dict, Any, Optional
import requests
from playwright.sync_api import sync_playwright, Browser, Page

logger = logging.getLogger(__name__)

class SVPortalUploader:
    """Handler for uploading candidate data to SV Admin Portal."""
    
    def __init__(self, portal_url: str, email: str, password: str):
        """
        Initialize SV Portal uploader.
        
        Args:
            portal_url: Base URL of SV Admin Portal
            email: Admin email for login
            password: Admin password for login
        """
        self.portal_url = portal_url.rstrip('/')
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.api_base = f"{self.portal_url}/api"
        self.browser: Optional[Browser] = None
        self.playwright_context = None
    
    def _try_api_upload(self, candidate_data: Dict[str, Any]) -> bool:
        """
        Try to upload candidate data via API.
        
        Args:
            candidate_data: Structured candidate data
            
        Returns:
            True if successful, False otherwise
        """
        # Try common API endpoints
        endpoints = [
            "/candidates",
            "/candidates/create",
            "/api/candidates",
            "/api/candidates/create",
            "/admin/candidates",
            "/admin/candidates/create"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.portal_url}{endpoint}"
                
                # Try POST request
                response = self.session.post(
                    url,
                    json=candidate_data,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"Successfully uploaded candidate via API: {endpoint}")
                    return True
                elif response.status_code == 401:
                    # Try to authenticate first
                    auth_response = self._authenticate_api()
                    if auth_response:
                        response = self.session.post(
                            url,
                            json=candidate_data,
                            headers={"Content-Type": "application/json"},
                            timeout=10
                        )
                        if response.status_code in [200, 201]:
                            logger.info(f"Successfully uploaded candidate via API after auth: {endpoint}")
                            return True
            except requests.exceptions.RequestException as e:
                logger.debug(f"API endpoint {endpoint} failed: {e}")
                continue
        
        return False
    
    def _authenticate_api(self) -> bool:
        """
        Try to authenticate with SV Portal API.
        
        Returns:
            True if successful, False otherwise
        """
        auth_endpoints = [
            "/api/auth/login",
            "/api/login",
            "/login",
            "/auth/login"
        ]
        
        auth_data = {
            "email": self.email,
            "password": self.password
        }
        
        for endpoint in auth_endpoints:
            try:
                url = f"{self.portal_url}{endpoint}"
                response = self.session.post(
                    url,
                    json=auth_data,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    # Store auth token if provided
                    try:
                        token_data = response.json()
                        if "token" in token_data:
                            self.session.headers.update({
                                "Authorization": f"Bearer {token_data['token']}"
                            })
                        elif "access_token" in token_data:
                            self.session.headers.update({
                                "Authorization": f"Bearer {token_data['access_token']}"
                            })
                    except:
                        pass
                    
                    logger.info("Successfully authenticated with SV Portal API")
                    return True
            except requests.exceptions.RequestException:
                continue
        
        return False
    
    def _playwright_upload(self, candidate_data: Dict[str, Any]) -> bool:
        """
        Upload candidate data using Playwright automation.
        
        Args:
            candidate_data: Structured candidate data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sync_playwright() as p:
                # Launch browser in headless mode
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Navigate to portal
                page.goto(self.portal_url, wait_until="networkidle", timeout=30000)
                
                # Try to find and fill login form
                try:
                    # Look for email/username field
                    email_selectors = [
                        'input[type="email"]',
                        'input[name="email"]',
                        'input[id*="email"]',
                        'input[placeholder*="email" i]',
                        'input[type="text"]'
                    ]
                    
                    email_field = None
                    for selector in email_selectors:
                        try:
                            email_field = page.wait_for_selector(selector, timeout=5000)
                            if email_field:
                                break
                        except:
                            continue
                    
                    if email_field:
                        email_field.fill(self.email)
                        
                        # Find and fill password field
                        password_field = page.wait_for_selector(
                            'input[type="password"]',
                            timeout=5000
                        )
                        if password_field:
                            password_field.fill(self.password)
                            
                            # Find and click login button
                            login_button = page.wait_for_selector(
                                'button[type="submit"], input[type="submit"], button:has-text("Login"), button:has-text("Sign In")',
                                timeout=5000
                            )
                            if login_button:
                                login_button.click()
                                page.wait_for_load_state("networkidle", timeout=15000)
                
                except Exception as login_error:
                    logger.warning(f"Login automation failed, continuing: {login_error}")
                
                # Navigate to candidate creation page
                candidate_urls = [
                    f"{self.portal_url}/candidates/create",
                    f"{self.portal_url}/admin/candidates/create",
                    f"{self.portal_url}/candidates/new",
                    f"{self.portal_url}/admin/candidates/new"
                ]
                
                for url in candidate_urls:
                    try:
                        page.goto(url, wait_until="networkidle", timeout=15000)
                        time.sleep(2)  # Wait for form to load
                        
                        # Fill form fields
                        identity = candidate_data.get("identity", {})
                        documents = candidate_data.get("documents", {})
                        addresses = candidate_data.get("addresses", {})
                        
                        # Map common field names
                        field_mappings = {
                            "name": identity.get("name", ""),
                            "email": identity.get("email", ""),
                            "phone": identity.get("phone", ""),
                            "designation": identity.get("designation", ""),
                            "dob": identity.get("dob", ""),
                            "gender": identity.get("gender", ""),
                            "nationality": identity.get("nationality", ""),
                            "pan": documents.get("pan_number", ""),
                            "uan": documents.get("uan_number", ""),
                            "passport": documents.get("passport_number", ""),
                            "current_address": addresses.get("current", ""),
                            "permanent_address": addresses.get("permanent", "")
                        }
                        
                        # Try to fill form fields
                        filled_count = 0
                        for field_name, value in field_mappings.items():
                            if not value:
                                continue
                            
                            selectors = [
                                f'input[name="{field_name}"]',
                                f'input[id*="{field_name}"]',
                                f'textarea[name="{field_name}"]',
                                f'textarea[id*="{field_name}"]',
                                f'input[placeholder*="{field_name}" i]'
                            ]
                            
                            for selector in selectors:
                                try:
                                    field = page.query_selector(selector)
                                    if field:
                                        field.fill(str(value))
                                        filled_count += 1
                                        break
                                except:
                                    continue
                        
                        # Submit form
                        submit_selectors = [
                            'button[type="submit"]',
                            'input[type="submit"]',
                            'button:has-text("Submit")',
                            'button:has-text("Save")',
                            'button:has-text("Create")'
                        ]
                        
                        for selector in submit_selectors:
                            try:
                                submit_button = page.query_selector(selector)
                                if submit_button:
                                    submit_button.click()
                                    page.wait_for_load_state("networkidle", timeout=10000)
                                    logger.info(f"Successfully uploaded candidate via Playwright: {url}")
                                    browser.close()
                                    return True
                            except:
                                continue
                        
                    except Exception as e:
                        logger.debug(f"Failed to use URL {url}: {e}")
                        continue
                
                browser.close()
                return False
                
        except Exception as e:
            logger.error(f"Playwright upload failed: {e}")
            return False
    
    def upload_candidate(self, candidate_data: Dict[str, Any]) -> bool:
        """
        Upload candidate data to SV Admin Portal.
        Tries API first, falls back to Playwright automation.
        
        Args:
            candidate_data: Structured candidate data dictionary
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Uploading candidate to SV Portal: {candidate_data.get('identity', {}).get('candidate_id', 'unknown')}")
        
        # Try API first
        if self._try_api_upload(candidate_data):
            return True
        
        # Fall back to Playwright
        logger.info("API upload failed, trying Playwright automation")
        return self._playwright_upload(candidate_data)



