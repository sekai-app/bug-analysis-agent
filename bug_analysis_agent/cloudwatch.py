"""
CloudWatchFinder - Module for correlating frontend errors with backend logs
"""

import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError
from .models import LogError, BackendLogEntry

logger = logging.getLogger(__name__)


class CloudWatchFinder:
    """Finds correlating backend logs in AWS CloudWatch"""
    
    def __init__(self, region_name: str = 'us-east-1', log_group: str = None):
        """
        Initialize CloudWatch client
        
        Args:
            region_name: AWS region for CloudWatch
            log_group: Default log group to search in
        """
        self.region_name = region_name
        self.default_log_group = log_group
        self.timestamp_warnings_shown = False  # Track if we've shown timestamp warnings
        
        try:
            self.logs_client = boto3.client('logs', region_name=region_name)
            logger.info(f"CloudWatch client initialized for region: {region_name}")
        except NoCredentialsError:
            logger.warning("AWS credentials not found. CloudWatch correlation will be disabled.")
            self.logs_client = None
        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch client: {e}")
            self.logs_client = None
    
    def find_correlating_logs(
        self, 
        frontend_errors: List[LogError], 
        log_group: Optional[str] = None,
        time_window_minutes: int = 10,  # 10 minutes default
        custom_query: Optional[str] = None
    ) -> List[BackendLogEntry]:
        """
        Find backend logs that correlate with frontend errors using CloudWatch Insights
        
        Args:
            frontend_errors: List of frontend errors to correlate
            log_group: CloudWatch log group to search (uses default if None)
            time_window_minutes: Time window around each error to search
            custom_query: Optional custom CloudWatch Insights query. Use {request_id} as placeholder
                         
                         Examples:
                         
                         # Basic error filtering
                         "fields @timestamp, @message, @logStream | filter @message like /{request_id}/ and @message like /ERROR/"
                         
                         # Filter by specific log level
                         "fields @timestamp, @message, level | filter @message like /{request_id}/ and level = 'ERROR'"
                         
                         # Include stack traces and filter by service
                         "fields @timestamp, @message, service, stack_trace | filter @message like /{request_id}/ and service = 'api-service'"
                         
                         # Search for related database operations
                         "fields @timestamp, @message, query_time | filter @message like /{request_id}/ and @message like /database|sql|query/"
                         
                         # Get logs with specific response codes
                         "fields @timestamp, @message, status_code | filter @message like /{request_id}/ and status_code >= 400"
                         
                         # Sort by log level priority
                         "fields @timestamp, @message, level | filter @message like /{request_id}/ | sort by case level when 'ERROR' then 1 when 'WARN' then 2 else 3 end"
            
        Returns:
            List of correlating backend log entries
        """
        if not self.logs_client:
            logger.warning("CloudWatch client not available. Skipping backend correlation.")
            return []
        
        log_group = log_group or self.default_log_group
        if not log_group:
            logger.warning("No log group specified. Skipping backend correlation.")
            return []
        
        if custom_query:
            logger.info(f"Using custom CloudWatch Insights query: {custom_query}")
        
        backend_logs = []
        
        for error in frontend_errors:
            correlating_logs = self._find_logs_for_error(
                error, log_group, time_window_minutes, custom_query
            )
            backend_logs.extend(correlating_logs)
        
        # Remove duplicates based on timestamp and message
        unique_logs = []
        seen = set()
        for log in backend_logs:
            key = (log.timestamp, log.message)
            if key not in seen:
                seen.add(key)
                unique_logs.append(log)
        
        logger.info(f"Found {len(unique_logs)} unique correlating backend log entries")
        return unique_logs
    
    def _find_logs_for_error(
        self, 
        error: LogError, 
        log_group: str,
        time_window_minutes: int,
        custom_query: Optional[str] = None
    ) -> List[BackendLogEntry]:
        print("FINDING LOGS FOR ERROR", error.request_ids)
        """Find backend logs for a specific frontend error using CloudWatch Insights with request ID correlation"""
        
        logger.info(f"Processing frontend error at line {error.line_number}: {error.error_type}")
        logger.info(f"Error timestamp string: '{error.timestamp}'")
        logger.info(f"Error request_id: '{error.request_id}'")
        logger.info(f"Error request_ids: {error.request_ids}")
        
        # Parse timestamp from error
        timestamp = self._parse_timestamp(error.timestamp)
        print("TIMESTAMP FOUND", timestamp)
        if not timestamp:
            # Only log the first few timestamp warnings to avoid spam
            print("NO TIMESTAMP")
            if not self.timestamp_warnings_shown:
                logger.info(f"Some errors don't have parseable timestamps - skipping CloudWatch correlation for those")
                self.timestamp_warnings_shown = True
            logger.debug(f"Skipping error without valid timestamp: {error.error_type} at line {error.line_number}")
            return []
        
        logger.info(f"Parsed frontend timestamp (UTC-4): {timestamp}")
        
        # Convert from UTC-4 to UTC for CloudWatch compatibility
        # Frontend logs are in UTC-4, so add 4 hours to get UTC
        from datetime import timezone, timedelta

        # Treat parsed timestamp as UTC-4
        timestamp = timestamp.replace(tzinfo=timezone(timedelta(hours=-4)))
        utc_timestamp = timestamp.astimezone(timezone.utc)

        logger.info(f"Converted to UTC for CloudWatch: {utc_timestamp}")
        
        # Calculate time window around the UTC timestamp
        start_time = utc_timestamp - timedelta(minutes=time_window_minutes)
        end_time = utc_timestamp + timedelta(minutes=time_window_minutes)
        logger.info(f"CloudWatch search window (UTC): {start_time} to {end_time}")
        logger.info(f"Time window span: ±{time_window_minutes} minutes ({time_window_minutes * 2} minutes total)")
        
        # Convert to milliseconds since epoch for CloudWatch API
        start_time_ms = int(start_time.timestamp() * 1000)
        end_time_ms = int(end_time.timestamp() * 1000)
        logger.info(f"CloudWatch API timestamps (ms): {start_time_ms} to {end_time_ms}")
        
        # Verify UTC conversion
        start_time_utc_str = start_time.strftime('%Y-%m-%d %H:%M:%S UTC')
        end_time_utc_str = end_time.strftime('%Y-%m-%d %H:%M:%S UTC')
        logger.info(f"Final CloudWatch query range: {start_time_utc_str} to {end_time_utc_str}")
        
        backend_logs = []
        
        # Search by ALL request IDs if available
        request_ids_to_search = error.request_ids if error.request_ids else ([error.request_id] if error.request_id else [])
        
        logger.info(f"Request IDs to search: {request_ids_to_search}")
        
        if not request_ids_to_search:
            logger.warning(f"No request IDs found for frontend error at line {error.line_number}")
            return []
        
        for request_id in request_ids_to_search:
            logger.info(f"Processing request_id: '{request_id}'")
            if request_id and self._is_valid_request_id_for_search(request_id):
                logger.info(f"Request_id '{request_id}' is valid, searching CloudWatch with Insights...")
                # Use CloudWatch Insights approach (more powerful and flexible)
                logs = self._search_by_request_id_insights(
                    log_group, request_id, start_time_ms, end_time_ms, custom_query
                )
                backend_logs.extend(logs)
                logger.debug(f"Found {len(logs)} backend logs via request_id '{request_id}' for frontend error at line {error.line_number}")
            elif request_id:
                logger.warning(f"Skipping invalid request_id '{request_id}' for CloudWatch search")
            else:
                logger.warning(f"Empty/None request_id found")
        
        # Remove duplicates that might occur from multiple request_id searches
        unique_logs = []
        seen = set()
        for log in backend_logs:
            key = (log.timestamp, log.message, log.log_stream)
            if key not in seen:
                seen.add(key)
                unique_logs.append(log)
        backend_logs = unique_logs
        
        logger.info(f"Found {len(backend_logs)} backend logs via CloudWatch Insights for frontend error at line {error.line_number}")
        
        return backend_logs
    
    def _search_by_request_id_insights(
        self, 
        log_group: str, 
        request_id: str, 
        start_time_ms: int, 
        end_time_ms: int,
        custom_query: Optional[str] = None
    ) -> List[BackendLogEntry]:
        """Search for logs with specific request ID using CloudWatch Insights query with optional custom query"""
        
        try:
            logger.debug(f"Searching for request_id: {request_id} using CloudWatch Insights")
            
            # Convert timestamps for debugging and verification
            start_time_dt = datetime.fromtimestamp(start_time_ms / 1000)
            end_time_dt = datetime.fromtimestamp(end_time_ms / 1000)
            logger.info(f"CloudWatch Insights API - Log group: {log_group}")
            logger.info(f"CloudWatch Insights API - Time range (UTC): {start_time_dt} to {end_time_dt}")
            logger.info(f"CloudWatch Insights API - Start time (ms): {start_time_ms} -> {start_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            logger.info(f"CloudWatch Insights API - End time (ms): {end_time_ms} -> {end_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            logger.info(f"CloudWatch Insights API - Request ID to search: {request_id}")
            
            # Use custom query if provided, otherwise use default request ID search
            if custom_query:
                # Replace {request_id} placeholder in custom query
                query = custom_query.replace("{request_id}", request_id)
                logger.info(f"Using custom CloudWatch Insights query")
            else:
                # Default CloudWatch Insights query with request_id filter
                query = f"""
                fields @timestamp, @message, @logStream
                | filter @message like /{request_id}/
                | sort @timestamp desc
                | limit 1000
                """
                logger.info(f"Using default CloudWatch Insights query for request_id search")
            
            logger.info(f"CloudWatch Insights query: {query.strip()}")
            
            # Prepare final API parameters
            api_start_time_seconds = start_time_ms // 1000
            api_end_time_seconds = end_time_ms // 1000
            logger.info(f"CloudWatch Insights API call parameters:")
            logger.info(f"  - logGroupName: {log_group}")
            logger.info(f"  - startTime: {api_start_time_seconds} (UTC seconds) = {datetime.fromtimestamp(api_start_time_seconds).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            logger.info(f"  - endTime: {api_end_time_seconds} (UTC seconds) = {datetime.fromtimestamp(api_end_time_seconds).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            logger.info(f"  - queryString: {query.strip()}")
            
            # Start the CloudWatch Insights query
            response = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=api_start_time_seconds,  # CloudWatch Insights expects seconds
                endTime=api_end_time_seconds,
                queryString=query
            )
            
            query_id = response['queryId']
            logger.info(f"Started CloudWatch Insights query: {query_id}")
            
            # Poll for query completion
            import time
            max_wait_time = 30  # Maximum wait time in seconds
            poll_interval = 1   # Poll every 1 second
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                result_response = self.logs_client.get_query_results(queryId=query_id)
                status = result_response['status']
                logger.debug(f"Query {query_id} status: {status} (elapsed: {elapsed_time}s)")
                
                if status == 'Complete':
                    results = result_response.get('results', [])
                    statistics = result_response.get('statistics', {})
                    logger.info(f"CloudWatch Insights query completed successfully!")
                    logger.info(f"  - Results found: {len(results)}")
                    logger.info(f"  - Query statistics: {statistics}")
                    logger.info(f"  - Search time range (UTC): {start_time_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_time_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.info(f"  - Request ID searched: '{request_id}'")
                    
                    if len(results) == 0:
                        logger.warning(f"No backend logs found for request_id '{request_id}' in UTC time range {start_time_dt} to {end_time_dt}")
                        logger.warning(f"Consider checking if the request_id exists in log group '{log_group}' during this time period")
                    else:
                        logger.info(f"Successfully found {len(results)} correlating backend log entries for request_id '{request_id}'")
                    
                    return self._parse_insights_results(results, log_group)
                elif status == 'Failed':
                    logger.error(f"CloudWatch Insights query failed for request_id '{request_id}'")
                    logger.error(f"Query was: {query.strip()}")
                    return []
                
                # Query still running, wait and poll again
                time.sleep(poll_interval)
                elapsed_time += poll_interval
            
            # Query timed out
            logger.warning(f"CloudWatch Insights query timed out for request_id '{request_id}' after {max_wait_time}s")
            return []
            
        except ClientError as e:
            logger.error(f"CloudWatch Insights search failed for request ID '{request_id}': {e}")
            logger.error(f"Error details: {e.response}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error searching for request ID '{request_id}': {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _search_by_request_id_simple(
        self, 
        log_group: str, 
        request_id: str, 
        start_time_ms: int, 
        end_time_ms: int
    ) -> List[BackendLogEntry]:
        """
        Alternative simpler search using filter_log_events instead of Insights
        
        This method is kept as a fallback option for cases where:
        - CloudWatch Insights is not available or has quota limits
        - Cost optimization is needed (filter_log_events is cheaper)
        - Simple text matching is sufficient
        
        Note: This method is no longer used by default. The system now uses
        CloudWatch Insights (_search_by_request_id_insights) for more powerful querying.
        """
        
        try:
            logger.debug(f"Searching for request_id: {request_id} using filter_log_events")
            
            # Convert timestamps for debugging
            start_time_dt = datetime.fromtimestamp(start_time_ms / 1000)
            end_time_dt = datetime.fromtimestamp(end_time_ms / 1000)
            logger.info(f"CloudWatch filter time range: {start_time_dt} to {end_time_dt}")
            logger.info(f"Log group: {log_group}")
            
            # Use filter_log_events with filterPattern
            response = self.logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=start_time_ms,
                endTime=end_time_ms,
                filterPattern=f'"{request_id}"',  # Simple text search
                limit=1000
            )
            
            events = response.get('events', [])
            logger.info(f"Found {len(events)} events for request_id '{request_id}'")
            
            if len(events) == 0:
                logger.warning(f"No results found for request_id '{request_id}' in time range {start_time_dt} to {end_time_dt}")
                logger.warning(f"Consider checking if the request_id exists in the log group '{log_group}' during this time period")
            
            # Handle pagination if needed
            max_pages = 10  # Safety limit to prevent infinite loops
            pages_processed = 0
            last_token = None
            
            while 'nextToken' in response and len(events) < 1000 and pages_processed < max_pages:
                current_token = response['nextToken']
                
                # Break if we get the same token twice (API issue)
                if current_token == last_token:
                    logger.warning(f"Received same nextToken twice, breaking pagination loop")
                    break
                
                last_token = current_token
                events_before = len(events)
                
                response = self.logs_client.filter_log_events(
                    logGroupName=log_group,
                    startTime=start_time_ms,
                    endTime=end_time_ms,
                    filterPattern=f'"{request_id}"',
                    nextToken=current_token,
                    limit=1000 - len(events)
                )
                
                new_events = response.get('events', [])
                events.extend(new_events)
                pages_processed += 1
                
                # Break if no new events were added (API issue)
                if len(events) == events_before:
                    logger.warning(f"No new events received in pagination, breaking loop")
                    break
                
                logger.debug(f"Pagination: page {pages_processed}, total events: {len(events)}")
            
            return self._parse_cloudwatch_events(events, log_group)
            
        except ClientError as e:
            logger.error(f"CloudWatch filter_log_events search failed for request ID '{request_id}': {e}")
            logger.error(f"Error details: {e.response}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error searching for request ID '{request_id}': {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _is_valid_request_id_for_search(self, request_id: str) -> bool:
        """Check if a request ID is valid for CloudWatch searching"""
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
    
    def _parse_cloudwatch_events(
        self, 
        events: List[Dict[str, Any]], 
        log_group: str
    ) -> List[BackendLogEntry]:
        """Parse CloudWatch events into BackendLogEntry objects"""
        
        backend_logs = []
        
        for event in events:
            try:
                timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                message = event['message']
                log_stream = event.get('logStreamName', 'unknown')
                
                # Try to extract request ID from message
                request_id = self._extract_request_id_from_message(message)
                
                backend_log = BackendLogEntry(
                    timestamp=timestamp,
                    message=message,
                    request_id=request_id,
                    log_group=log_group,
                    log_stream=log_stream
                )
                
                backend_logs.append(backend_log)
                
            except Exception as e:
                logger.error(f"Error parsing CloudWatch event: {e}")
                continue
        
        return backend_logs
    
    def _parse_insights_results(
        self, 
        results: List[List[Dict[str, str]]], 
        log_group: str
    ) -> List[BackendLogEntry]:
        """Parse CloudWatch Insights query results into BackendLogEntry objects"""
        
        backend_logs = []
        
        for result in results:
            try:
                # CloudWatch Insights returns each result as a list of field objects
                # Each field object has 'field' and 'value' keys
                timestamp_str = None
                message = None
                log_stream = None
                
                for field in result:
                    if field['field'] == '@timestamp':
                        timestamp_str = field['value']
                    elif field['field'] == '@message':
                        message = field['value']
                    elif field['field'] == '@logStream':
                        log_stream = field['value']
                
                if not timestamp_str or not message:
                    continue
                
                # Parse timestamp (CloudWatch Insights returns ISO format)
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                # Try to extract request ID from message
                request_id = self._extract_request_id_from_message(message)
                
                backend_log = BackendLogEntry(
                    timestamp=timestamp,
                    message=message,
                    request_id=request_id,
                    log_group=log_group,
                    log_stream=log_stream or 'insights-query'  # Use extracted log stream or fallback
                )
                
                backend_logs.append(backend_log)
                
            except Exception as e:
                logger.error(f"Error parsing CloudWatch Insights result: {e}")
                continue
        
        return backend_logs
    
    def _extract_request_id_from_message(self, message: str) -> Optional[str]:
        """Extract request ID from a log message"""
        import re
        
        # Updated pattern to handle both regular and JSON formats
        # Handles:
        # - "request_id": "some-id"  (JSON format)
        # - request_id: some-id     (regular format)
        # - request-id=some-id      (regular format)
        # - requestId some-id       (regular format)
        request_id_pattern = re.compile(
            r'(?:"?(?:request[_-]?id|req[_-]?id|requestId)"?)[:=\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            re.IGNORECASE
        )
        
        match = request_id_pattern.search(message)
        if match:
            request_id = match.group(1)
            # Filter out invalid request IDs (same logic as scanner)
            if self._is_valid_request_id_for_extraction(request_id):
                return request_id
        return None
    
    def _is_valid_request_id_for_extraction(self, request_id: str) -> bool:
        """Check if a request ID extracted from backend logs is valid"""
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
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp string into datetime object"""
        if not timestamp_str:
            return None
        
        # Try to parse Unix timestamp first (if it's all digits)
        if timestamp_str.isdigit():
            try:
                timestamp_num = int(timestamp_str)
                # Handle both seconds and milliseconds
                if timestamp_num > 1e10:  # Looks like milliseconds
                    return datetime.fromtimestamp(timestamp_num / 1000)
                else:  # Looks like seconds
                    return datetime.fromtimestamp(timestamp_num)
            except (ValueError, OSError):
                pass
        
        # Common timestamp formats
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S',
            '%m-%d %H:%M:%S',  # MM-dd HH:mm:ss format (mobile app logs)
            '%H:%M:%S.%f',  # Time only
            '%H:%M:%S',     # Time only
            '%b %d %H:%M:%S',  # MMM dd HH:mm:ss
        ]
        
        for fmt in formats:
            try:
                parsed_dt = datetime.strptime(timestamp_str, fmt)
                # If parsing time-only format, add today's date
                if fmt.startswith('%H:'):
                    today = datetime.now().date()
                    parsed_dt = datetime.combine(today, parsed_dt.time())
                elif fmt == '%b %d %H:%M:%S':
                    # Add current year for MMM dd format
                    parsed_dt = parsed_dt.replace(year=datetime.now().year)
                elif fmt == '%m-%d %H:%M:%S':
                    # Add current year for MM-dd format
                    parsed_dt = parsed_dt.replace(year=datetime.now().year)
                return parsed_dt
            except ValueError:
                continue
        
        logger.debug(f"Could not parse timestamp format: {timestamp_str}")
        return None
    
    def test_connection(self) -> bool:
        """Test if CloudWatch connection is working"""
        if not self.logs_client:
            return False
        
        try:
            # Try to list log groups (lightweight operation)
            self.logs_client.describe_log_groups(limit=1)
            return True
        except Exception as e:
            logger.error(f"CloudWatch connection test failed: {e}")
            return False
    
    def test_insights_query(self, log_group: str) -> bool:
        """Test if CloudWatch Insights queries are working with a simple query"""
        if not self.logs_client:
            logger.error("CloudWatch client not available")
            return False
        
        try:
            # Simple test query to check if Insights is working
            query = """
            fields @timestamp, @message
            | limit 10
            """
            
            # Use last 1 hour as test time range
            from datetime import datetime, timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=48)
            
            logger.info(f"Testing CloudWatch Insights with log group: {log_group}")
            logger.info(f"Test query: {query.strip()}")
            
            response = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query
            )
            
            query_id = response['queryId']
            logger.info(f"Test query started: {query_id}")
            
            # Poll for completion (shorter timeout for test)
            import time
            max_wait = 10
            elapsed = 0
            
            while elapsed < max_wait:
                result = self.logs_client.get_query_results(queryId=query_id)
                status = result['status']
                
                if status == 'Complete':
                    results = result.get('results', [])
                    logger.info(f"Test query completed successfully. Found {len(results)} sample logs")
                    return True
                elif status == 'Failed':
                    logger.error("Test query failed")
                    return False
                
                time.sleep(1)
                elapsed += 1
            
            logger.warning("Test query timed out")
            return False
            
        except Exception as e:
            logger.error(f"CloudWatch Insights test failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False 