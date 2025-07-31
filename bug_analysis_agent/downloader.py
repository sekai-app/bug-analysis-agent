"""
LogDownloader - Module for downloading frontend logs from S3
"""

import requests
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class LogDownloader:
    """Downloads frontend logs from S3 URLs"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        
    def download_log(self, log_url: str) -> str:
        """
        Download log content from the given URL
        
        Args:
            log_url: S3 URL or any HTTP URL to the log file
            
        Returns:
            String content of the log file
            
        Raises:
            requests.RequestException: If download fails
        """
        try:
            logger.info(f"Downloading log from: {log_url}")
            
            response = self.session.get(log_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Try to decode as UTF-8, fallback to latin-1 if needed
            try:
                content = response.content.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning("UTF-8 decode failed, trying latin-1")
                content = response.content.decode('latin-1')
                
            logger.info(f"Successfully downloaded log: {len(content)} characters")
            return content
            
        except requests.RequestException as e:
            logger.error(f"Failed to download log from {log_url}: {e}")
            raise
    
    def is_valid_log_url(self, url: str) -> bool:
        """
        Validate if the URL looks like a valid log URL
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL appears valid, False otherwise
        """
        try:
            parsed = urlparse(url)
            
            # Check basic URL structure
            if not (parsed.scheme in ('http', 'https') and parsed.netloc):
                return False
            
            # Check if it looks like a log file
            path_lower = parsed.path.lower()
            return (
                url.endswith('.log') or 
                path_lower.endswith('.log') or
                '/log' in path_lower or
                'logs/' in path_lower or
                'log-' in path_lower or
                '_log' in path_lower
            )
        except Exception:
            return False 