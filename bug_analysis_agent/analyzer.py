"""
BugAnalyzer - Main orchestrator for the User Review-Driven Log Triage & Analysis system
"""

import csv
import json
import logging
import os
import boto3
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from .models import UserReport, TriageReport, LogError, BackendLogEntry
from .downloader import LogDownloader
from .scanner import LogScanner
from .cloudwatch import CloudWatchFinder
from .gpt_agent import GPTAgent
from .config import Config

logger = logging.getLogger(__name__)


class BugAnalyzer:
    """
    Main bug analysis orchestrator that coordinates log scanning, 
    backend correlation, and GPT-based analysis
    """
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        aws_region: str = 'us-east-1',
        cloudwatch_log_group: Optional[str] = None,
        gpt_model: str = "gpt-4o"
    ):
        """
        Initialize the bug analyzer with all components
        
        Args:
            openai_api_key: OpenAI API key for GPT analysis
            aws_region: AWS region for CloudWatch
            cloudwatch_log_group: Default CloudWatch log group
            gpt_model: GPT model to use for analysis
        """
        
        # Initialize components
        self.downloader = LogDownloader()
        self.scanner = LogScanner()
        self.cloudwatch = CloudWatchFinder(
            region_name=aws_region,
            log_group=cloudwatch_log_group
        )
        
        try:
            # Use provided API key or fall back to config
            from .config import Config
            api_key_to_use = openai_api_key or Config.OPENAI_API_KEY
            
            self.gpt_agent = GPTAgent(
                api_key=api_key_to_use,
                model=gpt_model
            )
            self.gpt_available = True
        except Exception as e:
            logger.warning(f"GPT agent initialization failed: {e}")
            self.gpt_agent = None
            self.gpt_available = False
        
        logger.info("BugAnalyzer initialized")
    
    def analyze_report(
        self,
        report_data: Dict[str, Any],
        request_id_context_lines: Optional[int] = None,
        cloudwatch_log_group: Optional[str] = None,
        time_window_minutes: Optional[int] = None,
        max_correlations_per_error: int = 3
    ) -> TriageReport:
        """
        Analyze a complete user report through the full pipeline
        
        Args:
            report_data: Dictionary containing user report data
            request_id_context_lines: Number of lines to scan around error for request IDs (uses config default if None)
            cloudwatch_log_group: Override default CloudWatch log group
            time_window_minutes: Time window for backend log correlation (uses config default if None)
            max_correlations_per_error: Maximum correlations to keep per frontend error
            
        Returns:
            Complete TriageReport with analysis
        """
        
        # Use config defaults if not provided
        if request_id_context_lines is None:
            request_id_context_lines = Config.DEFAULT_REQUEST_ID_CONTEXT_LINES
        if time_window_minutes is None:
            time_window_minutes = Config.DEFAULT_TIME_WINDOW_MINUTES
        
        logger.info(f"Starting analysis for user {report_data.get('user_id', 'unknown')}")
        logger.info(f"Using request ID context lines: {request_id_context_lines}")
        logger.info(f"Using time window: ±{time_window_minutes} minutes")
        
        # Step 1: Parse user report
        try:
            user_report = UserReport(**report_data)
            logger.info(f"User report parsed: {user_report.feedback[:50]}...")
        except Exception as e:
            logger.error(f"Failed to parse user report: {e}")
            raise ValueError(f"Invalid user report data: {e}")
        
        # Step 2: Download frontend logs
        try:
            log_content = self.downloader.download_log(str(user_report.log_url))
            logger.info(f"Downloaded log: {len(log_content)} characters")
        except Exception as e:
            logger.error(f"Failed to download logs: {e}")
            raise RuntimeError(f"Log download failed: {e}")
        
        # Step 3: Scan for errors
        try:
            frontend_errors = self.scanner.scan_for_errors(log_content, request_id_context_lines=request_id_context_lines)
            logger.info(f"Found {len(frontend_errors)} frontend errors")
        except Exception as e:
            logger.error(f"Error scanning logs: {e}")
            frontend_errors = []
        
        # Step 4: Correlate with backend logs
        backend_logs = []
        if frontend_errors: 
            print("FRONTEND ERRORS", frontend_errors)
            # Only search backend if we found frontend errors
            try:
                backend_logs = self.cloudwatch.find_correlating_logs(
                    frontend_errors,
                    log_group=cloudwatch_log_group,
                    time_window_minutes=time_window_minutes
                )
                print("BACKEND LOGS", backend_logs)
                logger.info(f"Found {len(backend_logs)} correlating backend logs")
            except Exception as e:
                logger.warning(f"Backend log correlation failed: {e}")
                backend_logs = []
        
        # Step 5: Create correlation mappings
        correlations = self._create_direct_correlation_mappings(
            frontend_errors, 
            backend_logs,
            max_correlations_per_error=max_correlations_per_error
        )

        print("CORRELATIONS", correlations)
        
        # Step 6: GPT analysis
        try:
            if self.gpt_available:
                analysis = self.gpt_agent.analyze_user_report(
                    user_report, correlations
                )
                logger.info(f"GPT analysis completed: {analysis.issue_type}")
            else:
                analysis = self._create_fallback_analysis(user_report, correlations)
                logger.info("Used fallback analysis (GPT unavailable)")
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            analysis = self._create_fallback_analysis(user_report, correlations)
        
        # Create complete triage report
        triage_report = TriageReport(
            user_report=user_report,
            frontend_errors=frontend_errors,
            backend_logs=backend_logs,
            analysis=analysis,
            processed_at=datetime.now(timezone.utc)
        )
        
        logger.info("Analysis pipeline completed successfully")
        return triage_report
    
    def quick_analyze(self, report_data: Dict[str, Any], generate_csv: bool = True) -> str:
        """
        Quick analysis that returns a formatted summary string
        
        Args:
            report_data: Dictionary containing user report data
            generate_csv: Whether to generate CSV correlation file
            
        Returns:
            Formatted analysis summary
        """
        
        try:
            triage_report = self.analyze_report(report_data)
            summary = self.format_analysis_summary(triage_report)
            
            # Optionally generate CSV
            if generate_csv:
                csv_file = self.export_correlations_to_csv(triage_report)
                summary += f"\n📄 CSV Report: {csv_file}\n"
            
            return summary
        except Exception as e:
            logger.error(f"Quick analysis failed: {e}")
            return f"Analysis failed: {e}"
    
    def format_analysis_summary(self, triage_report: TriageReport) -> str:
        """
        Format triage report into a readable summary
        
        Args:
            triage_report: Complete triage report
            
        Returns:
            Formatted summary string
        """
        
        report = triage_report.user_report
        analysis = triage_report.analysis
        
        summary = f"""
BUG分析报告
{'='*50}

用户反馈: "{report.feedback}"
用户: {report.username} (ID: {report.user_id})
平台: {report.platform} - {report.os_version}
App版本: {report.app_version}
环境: {report.env}

分析结果
{'='*50}

问题类型: {analysis.issue_type.upper()}


总结: {analysis.summary}
"""
        
        if analysis.root_cause:
            summary += f"\n根本原因: {analysis.root_cause}"
        
        if analysis.related_limitations:
            summary += f"\n技术限制: {analysis.related_limitations}"
        
        summary += f"\n\n建议方案\n{'-'*30}\n"
        for i, rec in enumerate(analysis.recommendations, 1):
            summary += f"{i}. {rec}\n"
        
        summary += f"\n日志汇总\n{'-'*30}\n"
        summary += f"前端错误: {len(triage_report.frontend_errors)}\n"
        summary += f"后端日志: {len(triage_report.backend_logs)}\n"
        
        if triage_report.frontend_errors:
            summary += f"\n前端错误详情\n{'-'*20}\n"
            for i, error in enumerate(triage_report.frontend_errors[:3], 1):
                summary += f"{i}. {error.error_type} (Line {error.line_number})\n"
                
                # Show ALL request IDs found, not just the first one
                if error.request_ids:
                    if len(error.request_ids) == 1:
                        summary += f"   Request ID: {error.request_ids[0]}\n"
                    else:
                        summary += f"   Request IDs: {', '.join(error.request_ids)}\n"
                elif error.request_id:
                    # Fallback for backward compatibility
                    summary += f"   Request ID: {error.request_id}\n"
        
        summary += f"\n处理时间: {triage_report.processed_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return summary
    
    def format_concise_analysis(self, triage_report: TriageReport) -> str:
        """
        Format a concise analysis summary without user details (for webhooks with original content)
        
        Args:
            triage_report: Complete triage report
            
        Returns:
            Concise analysis summary string without redundant user info
        """
        analysis = triage_report.analysis
        
        summary = f"""问题类型: {analysis.issue_type.upper()}


总结: {analysis.summary}"""
        
        if analysis.root_cause:
            summary += f"\n\n根本原因: {analysis.root_cause}"
        
        if analysis.related_limitations:
            summary += f"\n\n技术限制: {analysis.related_limitations}"
        
        summary += f"\n\n建议方案\n{'-'*30}\n"
        for i, rec in enumerate(analysis.recommendations, 1):
            summary += f"{i}. {rec}\n"
        
        summary += f"\n日志汇总\n{'-'*30}\n"
        summary += f"前端错误: {len(triage_report.frontend_errors)}\n"
        summary += f"后端日志: {len(triage_report.backend_logs)}\n"
        
        if triage_report.frontend_errors:
            summary += f"\n前端错误详情:\n"
            for i, error in enumerate(triage_report.frontend_errors[:5], 1):  # Show first 3 errors
                summary += f"{i}. {error.error_type}: {error.log_segment[:150]}...\n"
        
        return summary
    
    def _upload_csv_data_to_s3(self, csv_data: str, user_id: str) -> str:
        """
        Upload CSV data directly to S3 and return the S3 URL
        
        Args:
            csv_data: CSV content as string
            user_id: User ID for organizing files in S3
            
        Returns:
            S3 URL of the uploaded file
        """
        try:
            # Initialize S3 client
            s3 = boto3.client(
                "s3", 
                aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
                region_name=Config.AWS_REGION
            )
            
            # Ensure bucket exists and has proper public access
            self._ensure_s3_bucket_public_access(s3)
            
            # Generate S3 key with timestamp and user_id
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            s3_key = f"reports/{user_id}/{timestamp}_log_correlations_{user_id}_{timestamp}.csv"
            
            # Upload CSV data directly to S3 (public access controlled by bucket policy)
            s3.put_object(
                Bucket=Config.S3_BUCKET_NAME,
                Key=s3_key,
                Body=csv_data.encode('utf-8'),
                ContentType='text/csv'
            )
            
            # Construct S3 URL
            s3_url = f"https://{Config.S3_BUCKET_NAME}.s3.{Config.AWS_REGION}.amazonaws.com/{s3_key}"
            
            logger.info(f"✅ CSV data uploaded to S3: {s3_url}")
            return s3_url
            
        except Exception as e:
            logger.error(f"Failed to upload CSV data to S3: {e}")
            raise
    
    def _save_csv_locally(self, csv_data: str, user_id: str) -> str:
        """
        Save CSV data locally as fallback when S3 is not available
        
        Args:
            csv_data: CSV content as string
            user_id: User ID for file naming
            
        Returns:
            Path to the saved local file
        """
        try:
            # Create logs directory if it doesn't exist
            logs_dir = "logs"
            os.makedirs(logs_dir, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"log_correlations_{user_id}_{timestamp}.csv"
            file_path = os.path.join(logs_dir, filename)
            
            # Write CSV data to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(csv_data)
            
            logger.info(f"✅ CSV saved locally: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to save CSV locally: {e}")
            raise
    
    def _ensure_s3_bucket_public_access(self, s3_client):
        """
        Ensure S3 bucket exists and has proper public access for CSV files
        
        Args:
            s3_client: Boto3 S3 client
        """
        try:
            # Check if bucket exists
            try:
                s3_client.head_bucket(Bucket=Config.S3_BUCKET_NAME)
                logger.info(f"S3 bucket {Config.S3_BUCKET_NAME} exists")
            except s3_client.exceptions.NoSuchBucket:
                # Create bucket if it doesn't exist
                s3_client.create_bucket(
                    Bucket=Config.S3_BUCKET_NAME,
                    CreateBucketConfiguration={'LocationConstraint': Config.AWS_REGION}
                )
                logger.info(f"Created S3 bucket {Config.S3_BUCKET_NAME}")
            
            # Disable block public access settings
            try:
                s3_client.put_public_access_block(
                    Bucket=Config.S3_BUCKET_NAME,
                    PublicAccessBlockConfiguration={
                        'BlockPublicAcls': False,
                        'IgnorePublicAcls': False,
                        'BlockPublicPolicy': False,
                        'RestrictPublicBuckets': False
                    }
                )
                logger.info(f"Disabled block public access for bucket {Config.S3_BUCKET_NAME}")
            except Exception as e:
                logger.warning(f"Could not disable block public access (may already be disabled): {e}")
            
            # Set bucket policy to allow public read access for CSV files
            bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicReadGetObject",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{Config.S3_BUCKET_NAME}/reports/*"
                    }
                ]
            }
            
            try:
                s3_client.put_bucket_policy(
                    Bucket=Config.S3_BUCKET_NAME,
                    Policy=json.dumps(bucket_policy)
                )
                logger.info(f"Set public read policy for CSV files in bucket {Config.S3_BUCKET_NAME}")
            except Exception as e:
                logger.warning(f"Could not set bucket policy (may already be set): {e}")
                
        except Exception as e:
            logger.warning(f"Could not ensure bucket public access: {e}")
            # Continue anyway - the upload might still work
    
    def export_correlations_to_csv(
        self, 
        triage_report: TriageReport, 
        output_file: str = None,
        global_deduplication: bool = True
    ) -> str:
        """
        Export frontend-backend log correlations to CSV and upload to S3
        
        Args:
            triage_report: Complete triage report
            output_file: Optional output file path (auto-generated if None)
            global_deduplication: If True, deduplicate backend messages globally across all frontend errors
            
        Returns:
            S3 URL of the uploaded CSV file, or local path if S3 upload fails
        """
        
        # Create correlation mappings with optional global deduplication
        correlations = self._create_direct_correlation_mappings(
            triage_report.frontend_errors, 
            triage_report.backend_logs,
            max_correlations_per_error=3
        )
        
        # Generate CSV content in memory
        csv_content = []
        fieldnames = [
            'frontend_line_number',
            'frontend_timestamp', 
            'frontend_error_type',
            'frontend_message',
            'frontend_request_ids',  # All request_ids found in context
            'backend_timestamp',
            'backend_message',
            'backend_log_group',
            'backend_log_stream',
            'backend_request_id',
            'matched_request_id',  # Which specific request_id was matched
            'correlation_method',
            'time_diff_seconds'
        ]
        
        # Add header
        csv_content.append(','.join(fieldnames))
        
        # Add data rows
        for correlation in correlations:
            row = []
            for field in fieldnames:
                value = correlation.get(field, '')
                # Escape commas and quotes in CSV
                value_str = str(value)
                if ',' in value_str or '"' in value_str:
                    # Double the quotes and wrap in quotes
                    escaped_value = value_str.replace('"', '""')
                    value = f'"{escaped_value}"'
                else:
                    value = value_str
                row.append(value)
            csv_content.append(','.join(row))
        
        csv_data = '\n'.join(csv_content)
        
        logger.info(f"Generated CSV with {len(correlations)} log correlations")
        
        # Upload to S3 if configured
        if Config.is_s3_configured():
            try:
                s3_url = self._upload_csv_data_to_s3(csv_data, triage_report.user_report.user_id)
                logger.info(f"CSV uploaded to S3: {s3_url}")
                return s3_url
            except Exception as e:
                logger.warning(f"Failed to upload CSV to S3: {e}")
                # Fallback to local file if S3 fails
                return self._save_csv_locally(csv_data, triage_report.user_report.user_id)
        else:
            # Save locally if S3 not configured
            return self._save_csv_locally(csv_data, triage_report.user_report.user_id)
    
    def _find_correlated_backends(
        self, 
        frontend_error: LogError, 
        backend_logs: List[BackendLogEntry],
        max_correlations: int = 3
    ) -> List[tuple]:
        """
        Find backend logs that correlate with a frontend error
        
        Keeps up to max_correlations correlations per frontend error, prioritizing:
        1. Request ID matches (highest priority)
        2. Time proximity (closest first)
        3. Log level (ERROR > WARN > INFO > DEBUG)
        
        Args:
            frontend_error: Frontend error to find correlations for
            backend_logs: List of backend logs to search
            max_correlations: Maximum number of correlations to keep per frontend error
            
        Returns:
            List of tuples (backend_log, correlation_info) - sorted by priority
        """
        correlations = []
        
        for backend_log in backend_logs:
            correlation_info = self._check_correlation(frontend_error, backend_log)
            if correlation_info:
                correlations.append((backend_log, correlation_info))
        
        if not correlations:
            return []
        
        # Sort correlations by priority
        def correlation_priority(correlation_tuple):
            backend_log, correlation_info = correlation_tuple
            
            # Priority 1: Correlation method (request_id_match > time_based)
            method_priority = {
                'request_id_match': 2,
                'time_based': 1
            }
            method_score = method_priority.get(correlation_info.get('method', ''), 0)
            
            # Priority 2: Time proximity (smaller time diff = higher priority)
            time_diff = correlation_info.get('time_diff_seconds', float('inf'))
            
            # Priority 3: Log level (ERROR > WARN > INFO > DEBUG)
            log_level_priority = {
                'ERROR': 4,
                'WARN': 3, 
                'WARNING': 3,
                'INFO': 2,
                'DEBUG': 1
            }
            
            # Extract log level from message
            message = backend_log.message.lower()
            log_level = 0
            for level, priority in log_level_priority.items():
                if level.lower() in message:
                    log_level = priority
                    break
            
            # Return tuple for sorting (higher values = higher priority)
            return (method_score, -time_diff, log_level)
        
        # Sort by priority and take top max_correlations
        correlations.sort(key=correlation_priority, reverse=True)
        return correlations[:max_correlations]
    
    def _check_correlation(
        self, 
        frontend_error: LogError, 
        backend_log: BackendLogEntry
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a frontend error correlates with a backend log
        
        Args:
            frontend_error: Frontend error
            backend_log: Backend log entry
            
        Returns:
            Correlation info dict if correlated, None otherwise
        """
        # Check if any of the frontend request_ids match the backend request_id
        if backend_log.request_id:
            # First check new request_ids list
            if frontend_error.request_ids and backend_log.request_id in frontend_error.request_ids:
                return {
                    'method': 'request_id_match',
                    'confidence': 'high',
                    'matched_request_id': backend_log.request_id
                }
            
            # Fallback to old request_id field for backward compatibility
            if (frontend_error.request_id and 
                frontend_error.request_id == backend_log.request_id):
                return {
                    'method': 'request_id_match',
                    'confidence': 'high',
                    'matched_request_id': backend_log.request_id
                }
        
        # If no request ID match, try time-based correlation
        if frontend_error.timestamp and backend_log.timestamp:
            from bug_analysis_agent.cloudwatch import CloudWatchFinder
            cloudwatch = CloudWatchFinder()
            frontend_time = cloudwatch._parse_timestamp(frontend_error.timestamp)
            
            print(f"DEBUG: Frontend timestamp: {frontend_error.timestamp} -> {frontend_time}")
            print(f"DEBUG: Backend timestamp: {backend_log.timestamp}")
            
            if frontend_time:
                # Convert frontend time to UTC (assuming it's in EDT/EST timezone)
                # Frontend logs appear to be in UTC-4 (EDT) timezone
                from datetime import timedelta
                frontend_utc = frontend_time + timedelta(hours=4)  # Convert to UTC
                print(f"DEBUG: Frontend time (UTC): {frontend_utc}")
                
                time_diff = abs((backend_log.timestamp - frontend_utc).total_seconds())
                print(f"DEBUG: Time difference: {time_diff} seconds")
                # Consider logs within config-defined time window as correlated
                time_window_seconds = Config.DEFAULT_TIME_WINDOW_MINUTES * 60
                if time_diff <= time_window_seconds:
                    print(f"DEBUG: Time-based correlation found! Diff: {time_diff}s")
                    return {
                        'method': 'time_based',
                        'confidence': 'medium',
                        'time_diff_seconds': time_diff
                    }
                else:
                    print(f"DEBUG: Time difference too large: {time_diff}s > {time_window_seconds}s")
            else:
                print(f"DEBUG: Could not parse frontend timestamp: {frontend_error.timestamp}")
        
        return None
    
    def _find_time_based_backends(self, frontend_error: LogError, backend_logs: List[BackendLogEntry]) -> List[BackendLogEntry]:
        """Find backend logs that occurred near the same time as frontend error (without request ID match)"""
        if not frontend_error.timestamp:
            return []
        
        # Parse frontend timestamp
        from bug_analysis_agent.cloudwatch import CloudWatchFinder
        cloudwatch = CloudWatchFinder()
        frontend_time = cloudwatch._parse_timestamp(frontend_error.timestamp)
        if not frontend_time:
            return []
        
        # Find backend logs within reasonable time window (±10 minutes)
        time_based_logs = []
        from datetime import timedelta
        
        for backend_log in backend_logs:
            if backend_log.timestamp:
                time_diff = abs((backend_log.timestamp - frontend_time).total_seconds())
                # Include backend logs within config-defined time window of frontend error
                time_window_seconds = Config.DEFAULT_TIME_WINDOW_MINUTES * 60
                if time_diff <= time_window_seconds:
                    time_based_logs.append(backend_log)
        
        # Sort by time proximity (closest first)
        time_based_logs.sort(key=lambda log: abs((log.timestamp - frontend_time).total_seconds()))
        
        # Return up to 3 closest backend logs to avoid overwhelming CSV
        return time_based_logs[:3]
    
    def _calculate_time_diff(self, frontend_error: LogError, backend_log: BackendLogEntry) -> str:
        """Calculate time difference between frontend error and backend log"""
        if not frontend_error.timestamp or not backend_log.timestamp:
            return ''
        
        from bug_analysis_agent.cloudwatch import CloudWatchFinder
        cloudwatch = CloudWatchFinder()
        frontend_time = cloudwatch._parse_timestamp(frontend_error.timestamp)
        if not frontend_time:
            return ''
        
        time_diff = (backend_log.timestamp - frontend_time).total_seconds()
        return f"{time_diff:.1f}"
    
    def _create_direct_correlation_mappings(
        self, 
        frontend_errors: List[LogError], 
        backend_logs: List[BackendLogEntry],
        max_correlations_per_error: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Create direct correlation mappings between frontend and backend logs
        Each frontend error gets mapped to its correlating backend logs directly
        
        Args:
            frontend_errors: List of frontend errors
            backend_logs: List of backend logs
            max_correlations_per_error: Maximum correlations to keep per frontend error
            
        Returns:
            List of correlation dictionaries
        """
        correlations = []
        
        for frontend_error in frontend_errors:
            # Find correlating backend logs for this frontend error
            correlated_backends = self._find_correlated_backends(
                frontend_error, 
                backend_logs,
                max_correlations=max_correlations_per_error
            )
            
            if correlated_backends:
                # Create a row for each correlated backend log
                for backend_log, correlation_info in correlated_backends:
                    correlation = {
                        'frontend_line_number': frontend_error.line_number,
                        'frontend_timestamp': frontend_error.timestamp or '',
                        'frontend_error_type': frontend_error.error_type,
                        'frontend_message': frontend_error.log_segment.strip(),
                        'frontend_request_ids': ','.join(frontend_error.request_ids) if frontend_error.request_ids else '',
                        'backend_timestamp': backend_log.timestamp.isoformat() if backend_log.timestamp else '',
                        'backend_message': backend_log.message.strip(),
                        'backend_log_group': backend_log.log_group,
                        'backend_log_stream': backend_log.log_stream,
                        'backend_request_id': backend_log.request_id or '',
                        'matched_request_id': correlation_info.get('matched_request_id', ''),
                        'correlation_method': correlation_info['method'],
                        'time_diff_seconds': correlation_info.get('time_diff_seconds', '')
                    }
                    correlations.append(correlation)
            else:
                # Frontend error with no backend correlation - check for time-based correlations
                time_based_backends = self._find_time_based_backends(frontend_error, backend_logs)
                
                if time_based_backends:
                    # Create entries for backend logs found in time window (even without request ID match)
                    for backend_log in time_based_backends:
                        correlation = {
                            'frontend_line_number': frontend_error.line_number,
                            'frontend_timestamp': frontend_error.timestamp or '',
                            'frontend_error_type': frontend_error.error_type,
                            'frontend_message': frontend_error.log_segment.strip(),
                            'frontend_request_ids': ','.join(frontend_error.request_ids) if frontend_error.request_ids else '',
                            'backend_timestamp': backend_log.timestamp.isoformat() if backend_log.timestamp else '',
                            'backend_message': backend_log.message.strip(),
                            'backend_log_group': backend_log.log_group,
                            'backend_log_stream': backend_log.log_stream,
                            'backend_request_id': backend_log.request_id or '',
                            'matched_request_id': '',
                            'correlation_method': 'time_window',
                            'time_diff_seconds': self._calculate_time_diff(frontend_error, backend_log)
                        }
                        correlations.append(correlation)
                else:
                    # Frontend error with truly no backend activity
                    correlation = {
                        'frontend_line_number': frontend_error.line_number,
                        'frontend_timestamp': frontend_error.timestamp or '',
                        'frontend_error_type': frontend_error.error_type,
                        'frontend_message': frontend_error.log_segment.strip(),
                        'frontend_request_ids': ','.join(frontend_error.request_ids) if frontend_error.request_ids else '',
                        'backend_timestamp': '',
                        'backend_message': '',
                        'backend_log_group': '',
                        'backend_log_stream': '',
                        'backend_request_id': '',
                        'matched_request_id': '',
                        'correlation_method': 'no_correlation',
                        'time_diff_seconds': ''
                    }
                    correlations.append(correlation)
        
        return correlations
    
    def _create_fallback_analysis(self, user_report, correlations):
        """Create a simple fallback analysis when GPT is unavailable"""
        from .models import AnalysisResult
        
        feedback_lower = user_report.feedback.lower()
        
        # Count frontend errors and backend correlations
        frontend_errors = len(set(c['frontend_line_number'] for c in correlations))
        correlations_with_backend = len([c for c in correlations if c.get('backend_message')])
        
        # Simple classification heuristics
        if any(word in feedback_lower for word in ['make', 'add', 'could', 'can you', 'feature']):
            issue_type = 'feature_request'
            summary = "Appears to be a feature request based on user language patterns"
        elif frontend_errors > 0:
            issue_type = 'bug'
            summary = f"Likely bug - detected {frontend_errors} error(s) in frontend logs"
        else:
            issue_type = 'neither'
            summary = "Unable to classify - no clear errors or feature requests detected"
        
        recommendations = []
        if frontend_errors > 0:
            recommendations.append(f"Investigate {frontend_errors} error(s) found in logs")
            # Find most common error type from correlations
            error_types = [c['frontend_error_type'] for c in correlations]
            if error_types:
                most_common_error = max(set(error_types), key=error_types.count)
                recommendations.append(f"Focus on {most_common_error} errors (most common)")
        
        if correlations_with_backend > 0:
            recommendations.append(f"Review {correlations_with_backend} backend correlations for root cause")
        
        if issue_type == 'feature_request':
            recommendations.append("Consider user feedback for product roadmap planning")
        
        recommendations.append("Manual review recommended for detailed analysis")
        
        return AnalysisResult(
            issue_type=issue_type,
            confidence=0.6 if frontend_errors > 0 else 0.4,
            root_cause=None,
            related_limitations=None,
            recommendations=recommendations,
            summary=summary
        )
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all components"""
        return {
            'downloader': 'ok',
            'scanner': 'ok',
            'cloudwatch': 'ok' if self.cloudwatch.test_connection() else 'unavailable',
            'gpt_agent': 'ok' if self.gpt_available else 'unavailable',
            'overall': 'healthy'
        } 