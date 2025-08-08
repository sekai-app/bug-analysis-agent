"""
LogScanner - Module for scanning logs and detecting error events
"""

import re
import logging
from typing import List, Pattern, Match, Optional
from .models import LogError

logger = logging.getLogger(__name__)


class LogScanner:
    """Scans frontend logs for error patterns and extracts context"""
    
    def __init__(self):
        # Define error patterns to search for - more precise matching
        self.error_patterns = [
        # ==== Log Levels ====
        (r'\[E\]', 'LOG_LEVEL_ERROR'),
        (r'\[ERROR\]', 'LOG_LEVEL_ERROR'),
        (r'\[ERR\]', 'LOG_LEVEL_ERROR'),
        (r'\[FATAL\]', 'LOG_LEVEL_FATAL'),
        (r'\[CRITICAL\]', 'LOG_LEVEL_CRITICAL'),
        (r'\[WARN(ING)?\]', 'LOG_LEVEL_WARNING'),

        # ==== Programming Errors ====
        (r'\bAssertionError\b', 'ASSERTION_ERROR'),
        (r'\bRuntimeError\b', 'RUNTIME_ERROR'),
        (r'\bRangeError\b', 'RANGE_ERROR'),
        (r'\bTypeError\b', 'TYPE_ERROR'),
        (r'\bReferenceError\b', 'REFERENCE_ERROR'),
        (r'\bSyntaxError\b', 'SYNTAX_ERROR'),
        (r'\bNameError\b', 'NAME_ERROR'),
        (r'\bValueError\b', 'VALUE_ERROR'),
        (r'\bKeyError\b', 'KEY_ERROR'),
        (r'\bIndexError\b', 'INDEX_ERROR'),
        (r'\bImportError\b', 'IMPORT_ERROR'),
        (r'\bModuleNotFoundError\b', 'MODULE_NOT_FOUND'),

        # ==== Exception Signatures ====
        (r'\bException\b[:\s]', 'GENERIC_EXCEPTION'),
        (r'\bUnhandled exception\b', 'UNHANDLED_EXCEPTION'),
        (r'\bUncaught exception\b', 'UNCAUGHT_EXCEPTION'),
        (r'\bCaught exception\b', 'CAUGHT_EXCEPTION'),
        (r'\bError\b[:\s]', 'GENERIC_ERROR'),
        (r'^Exception\b', 'GENERIC_EXCEPTION'),
        (r'^Error\b', 'GENERIC_ERROR'),

        # ==== System Failures / Crashes ====
        (r'\bFATAL\b', 'FATAL'),
        (r'\bCRITICAL\b', 'CRITICAL'),
        (r'\bSEVERE\b', 'SEVERE'),
        (r'\bPANIC\b', 'PANIC'),
        (r'\bcrash(ed)?\b', 'CRASH'),
        (r'\bsegmentation fault\b', 'SEGFAULT'),
        (r'\bcore dump\b', 'CORE_DUMP'),
        (r'\bkernel panic\b', 'KERNEL_PANIC'),

        # ==== Network / API Failures ====
        (r'\btimeout\b', 'TIMEOUT'),
        (r'\bconnection (reset|refused|timed out|closed)\b', 'CONNECTION_ERROR'),
        (r'\bconnect\w* failed\b', 'CONNECTION_FAILURE'),
        (r'\brequest failed\b', 'REQUEST_FAILURE'),
        (r'\bHTTP [45]\d\d\b', 'HTTP_ERROR'),
        (r'\b503 Service Unavailable\b', 'SERVICE_UNAVAILABLE'),
        (r'\b504 Gateway Timeout\b', 'GATEWAY_TIMEOUT'),
        (r'\bnetwork error\b', 'NETWORK_ERROR'),
        (r'\bDNS (lookup|resolution) failed\b', 'DNS_FAILURE'),

        # ==== Access / Permissions ====
        (r'\bpermission denied\b', 'PERMISSION_DENIED'),
        (r'\baccess denied\b', 'ACCESS_DENIED'),
        (r'\bnot authorized\b', 'UNAUTHORIZED'),
        (r'\bunauthorized\b', 'UNAUTHORIZED'),

        # ==== File System / IO ====
        (r'\bfile not found\b', 'FILE_NOT_FOUND'),
        (r'\bno such file or directory\b', 'FILE_NOT_FOUND'),
        (r'\bread-only file system\b', 'READ_ONLY_FS'),
        (r'\bdisk full\b', 'DISK_FULL'),
        (r'\bI/O error\b', 'IO_ERROR'),

        # ==== Database / Cache / Storage ====
        (r'\bSQLSTATE\b', 'SQL_ERROR'),
        (r'\bdatabase error\b', 'DB_ERROR'),
        (r'\bquery failed\b', 'DB_QUERY_FAILURE'),
        (r'\bconnection pool exhausted\b', 'DB_CONNECTION_EXHAUSTED'),
        (r'\bredis\b.*\b(error|fail)\b', 'REDIS_ERROR'),

        # ==== Authentication / Session ====
        (r'\bauthentication failed\b', 'AUTH_FAILURE'),
        (r'\bsession expired\b', 'SESSION_EXPIRED'),
        (r'\btoken expired\b', 'TOKEN_EXPIRED'),

        # ==== Common Failure Phrases ====
        (r'\bfailed to\b', 'GENERIC_FAILURE'),
        (r'\bcannot\b', 'GENERIC_FAILURE'),
        (r'\bunable to\b', 'GENERIC_FAILURE'),
        (r'\binvalid\b', 'INVALID_INPUT'),
        (r'\bunexpected\b', 'UNEXPECTED'),
        (r'\bmismatch\b', 'MISMATCH'),
        (r'\bnull\b', 'NULL_ERROR'),
        (r'\bundefined\b', 'UNDEFINED'),

        # ==== Miscellaneous Critical Indicators ====
        (r'\babort(ed)?\b', 'ABORT'),
        (r'\bstack trace\b', 'STACK_TRACE'),
        (r'\btraceback\b', 'TRACEBACK'),
        (r'\bbug\b', 'BUG'),
    ]

        
        # Compile patterns for performance
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), error_type)
            for pattern, error_type in self.error_patterns
        ]
        
        # Pattern to extract request IDs - handles both regular and JSON formats
        # Handles:
        # - "request_id": "some-id"  (JSON format)
        # - request_id: some-id     (regular format)
        # - request-id=some-id      (regular format)
        # - requestId some-id       (regular format)
        self.request_id_pattern = re.compile(
            r'(?:"?(?:request[_-]?id|req[_-]?id|requestId)"?)[:=\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            re.IGNORECASE
        )
        
        # Pattern to extract timestamps - multiple formats
        self.timestamp_patterns = [
            # ISO format with milliseconds and timezone
            re.compile(r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d{3})?(?:Z|[+-]\d{2}:?\d{2})?)'),
            # Simple timestamp format
            re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'),
            # Unix timestamp format (if logs use it)
            re.compile(r'(\d{10,13})'),  # Unix timestamp (seconds or milliseconds)
            # Alternative format: MMM dd HH:mm:ss
            re.compile(r'([A-Za-z]{3} \d{1,2} \d{2}:\d{2}:\d{2})'),
            # Format: [MM-dd HH:mm:ss] - common mobile app log format
            re.compile(r'\[(\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]'),
            # Format: [HH:mm:ss.fff]
            re.compile(r'\[(\d{2}:\d{2}:\d{2}(?:\.\d{3})?)\]'),
        ]
    
    def scan_for_errors(self, log_content: str, context_lines: int = 10, request_id_context_lines: int = 5) -> List[LogError]:
        """
        Scan log content for error patterns and extract context
        
        Args:
            log_content: The complete log file content
            context_lines: Number of lines to extract before and after each error (deprecated, not used)
            request_id_context_lines: Number of lines to scan around error for request IDs
            
        Returns:
            List of LogError objects with extracted information
        """
        lines = log_content.split('\n')
        errors = []
        seen_errors = set()  # Track unique error signatures for deduplication
        
        logger.info(f"Scanning {len(lines)} lines for error patterns")
        
        for line_num, line in enumerate(lines):
            # Skip lines that are clearly informational
            if self._should_exclude_line(line):
                continue
                
            for pattern, error_type in self.compiled_patterns:
                if pattern.search(line):
                    error = self._extract_error_details(
                        lines, line_num, line, error_type, request_id_context_lines
                    )
                    
                    # Create a signature for deduplication
                    error_signature = self._create_error_signature(error)
                    
                    # Only add if we haven't seen this exact error before
                    if error_signature not in seen_errors:
                        errors.append(error)
                        seen_errors.add(error_signature)
                        logger.debug(f"Found {error_type} at line {line_num + 1}")
                    else:
                        logger.debug(f"Skipped duplicate {error_type} at line {line_num + 1}")
                    
                    break  # Don't match multiple patterns on the same line
        
        logger.info(f"Found {len(errors)} unique error(s) in log (after deduplication)")
        return errors
    
    def _extract_error_details(
        self, 
        lines: List[str], 
        line_num: int, 
        error_line: str, 
        error_type: str,
        request_id_context_lines: int = 5
    ) -> LogError:
        """Extract detailed information about an error"""
        
        # Extract request IDs from the error line or nearby lines
        context_lines_for_request_id = lines[max(0, line_num - request_id_context_lines):min(len(lines), line_num + request_id_context_lines + 1)]
        request_id = self._extract_request_id(context_lines_for_request_id)  # First one for backward compatibility
        request_ids = self._extract_all_request_ids(context_lines_for_request_id)  # All request IDs
        
        # Extract timestamp from the error line or nearby lines
        timestamp = self._extract_timestamp(
            lines[max(0, line_num - 2):min(len(lines), line_num + 2)]
        )
        
        return LogError(
            timestamp=timestamp,
            request_id=request_id,
            request_ids=request_ids,
            error_type=error_type,
            log_segment=error_line,
            context_before=[],  # Not used, keep empty for backward compatibility
            context_after=[],   # Not used, keep empty for backward compatibility
            line_number=line_num + 1  # 1-based line numbers
        )
    
    def _extract_request_id(self, lines: List[str]) -> Optional[str]:
        """Extract request ID from a list of lines (returns first for backward compatibility)"""
        request_ids = self._extract_all_request_ids(lines)
        return request_ids[0] if request_ids else None
    
    def _extract_all_request_ids(self, lines: List[str]) -> List[str]:
        """Extract all request IDs from a list of lines"""
        request_ids = []
        seen_ids = set()  # Prevent duplicates
        
        for line in lines:
            matches = self.request_id_pattern.findall(line)
            for match in matches:
                # Handle both single group and multiple group regex results
                request_id = match if isinstance(match, str) else match[0] if match else None
                
                # Filter out invalid request IDs
                if request_id and self._is_valid_request_id(request_id) and request_id not in seen_ids:
                    request_ids.append(request_id)
                    seen_ids.add(request_id)
        
        return request_ids
    
    def _is_valid_request_id(self, request_id: str) -> bool:
        """Check if a request ID is valid and should be used for correlation"""
        if not request_id:
            return False
        
        # Filter out common invalid values (case-insensitive)
        invalid_values = {'null', 'none', 'undefined', 'nil', 'empty'}
        if request_id.lower() in invalid_values:
            return False
        
        # Filter out very short IDs (most valid request IDs are 6+ characters)
        if len(request_id) < 6:
            return False
        
        return True
    
    def _extract_timestamp(self, lines: List[str]) -> Optional[str]:
        """Extract timestamp from a list of lines using multiple patterns"""
        for line in lines:
            for pattern in self.timestamp_patterns:
                match = pattern.search(line)
                if match:
                    return match.group(1)
        return None
    
    def _should_exclude_line(self, line: str) -> bool:
        """
        Check if a line should be excluded from error detection
        
        Args:
            line: Log line to check
            
        Returns:
            True if line should be excluded, False otherwise
        """
        line_lower = line.lower()
        
        # Exclude info/debug level logs
        if any(marker in line for marker in ['[I]', '[INFO]', '[D]', '[DEBUG]', '[TRACE]']):
            return True
        
        # Exclude specific non-error patterns that might contain error keywords
        exclude_patterns = [
            r'receivedatawhenstatuserror',  # Your specific case
            r'error.*:.*true',              # Configuration settings like "error: true"
            r'error.*=.*true',              # Assignment patterns
            r'errorcallback',               # Function names
            r'error_code.*=.*0',           # Success codes
            r'no error',                   # Explicit "no error" messages
            r'0 errors',                   # Success messages
            r'error handling',             # Documentation or comments
            r'error recovery',             # System processes
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, line_lower):
                return True
        
        return False
    
    def _create_error_signature(self, error: LogError) -> str:
        """
        Create a unique signature for an error to enable deduplication
        
        Args:
            error: LogError object
            
        Returns:
            String signature for the error
        """
        # Normalize the error message for comparison
        normalized_message = error.log_segment.strip()
        
        # Remove timestamps and line numbers to focus on the actual error
        import re
        
        # Remove common timestamp patterns
        normalized_message = re.sub(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d{3})?(?:Z|[+-]\d{2}:?\d{2})?', '', normalized_message)
        normalized_message = re.sub(r'\[\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]', '', normalized_message)
        
        # Remove line numbers and memory addresses
        normalized_message = re.sub(r'\b\d+\b', 'N', normalized_message)
        normalized_message = re.sub(r'0x[0-9a-fA-F]+', '0xADDR', normalized_message)
        
        # Remove file paths (keep just the filename)
        normalized_message = re.sub(r'[/\\][\w/\\.-]+[/\\](\w+\.\w+)', r'\1', normalized_message)
        
        # Normalize whitespace
        normalized_message = ' '.join(normalized_message.split())
        
        # Create signature: error_type + normalized message
        signature = f"{error.error_type}:{normalized_message.lower()}"
        
        return signature
    
    def add_custom_pattern(self, pattern: str, error_type: str):
        """Add a custom error pattern to scan for"""
        self.error_patterns.append((pattern, error_type))
        self.compiled_patterns.append((re.compile(pattern, re.IGNORECASE), error_type))
        logger.info(f"Added custom pattern: {pattern} -> {error_type}") 