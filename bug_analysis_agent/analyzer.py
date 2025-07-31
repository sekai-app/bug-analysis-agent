"""
BugAnalyzer - Main orchestrator for the User Review-Driven Log Triage & Analysis system
"""

import csv
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from .models import UserReport, TriageReport, LogError, BackendLogEntry
from .downloader import LogDownloader
from .scanner import LogScanner
from .cloudwatch import CloudWatchFinder
from .gpt_agent import GPTAgent

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
        context_lines: int = 10,
        request_id_context_lines: int = 5,
        cloudwatch_log_group: Optional[str] = None,
        time_window_minutes: int = 10,  # 10 minutes default
        max_correlations_per_error: int = 3
    ) -> TriageReport:
        """
        Analyze a complete user report through the full pipeline
        
        Args:
            report_data: Dictionary containing user report data
            context_lines: Number of lines to extract around each error
            request_id_context_lines: Number of lines to scan around error for request IDs
            cloudwatch_log_group: Override default CloudWatch log group
            time_window_minutes: Time window for backend log correlation
            
        Returns:
            Complete TriageReport with analysis
        """
        
        logger.info(f"Starting analysis for user {report_data.get('user_id', 'unknown')}")
        
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
            frontend_errors = self.scanner.scan_for_errors(log_content, context_lines, request_id_context_lines)
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
        correlations = self._create_correlation_mappings(
            frontend_errors, 
            backend_logs,
            global_deduplication=True
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
📋 BUG ANALYSIS REPORT
{'='*50}

🗣️ User Feedback: "{report.feedback}"
👤 User: {report.username} (ID: {report.user_id})
📱 Platform: {report.platform} - {report.os_version}
🔧 App Version: {report.app_version}
🌍 Environment: {report.env}

📊 ANALYSIS RESULTS
{'='*50}

🎯 Issue Type: {analysis.issue_type.upper()}
🎲 Confidence: {analysis.confidence:.1%}

📝 Summary: {analysis.summary}
"""
        
        if analysis.root_cause:
            summary += f"\n🔍 Root Cause: {analysis.root_cause}"
        
        if analysis.related_limitations:
            summary += f"\n⚠️ Technical Limitations: {analysis.related_limitations}"
        
        summary += f"\n\n💡 RECOMMENDATIONS\n{'-'*30}\n"
        for i, rec in enumerate(analysis.recommendations, 1):
            summary += f"{i}. {rec}\n"
        
        summary += f"\n📊 LOG SUMMARY\n{'-'*30}\n"
        summary += f"Frontend Errors: {len(triage_report.frontend_errors)}\n"
        summary += f"Backend Logs: {len(triage_report.backend_logs)}\n"
        
        if triage_report.frontend_errors:
            summary += f"\n🚨 TOP ERRORS\n{'-'*20}\n"
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
        
        summary += f"\n⏰ Processed: {triage_report.processed_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return summary
    
    def export_correlations_to_csv(
        self, 
        triage_report: TriageReport, 
        output_file: str = None,
        global_deduplication: bool = True
    ) -> str:
        """
        Export frontend-backend log correlations to CSV
        
        Args:
            triage_report: Complete triage report
            output_file: Optional output file path (auto-generated if None)
            global_deduplication: If True, deduplicate backend messages globally across all frontend errors
            
        Returns:
            Path to the generated CSV file
        """
        
        # Create logs directory if it doesn't exist
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            user_id = triage_report.user_report.user_id
            output_file = os.path.join(logs_dir, f"log_correlations_{user_id}_{timestamp}.csv")
        else:
            # If output_file is provided, ensure it's in the logs directory
            if not output_file.startswith(logs_dir):
                output_file = os.path.join(logs_dir, os.path.basename(output_file))
        
        # Create correlation mappings with optional global deduplication
        correlations = self._create_correlation_mappings(
            triage_report.frontend_errors, 
            triage_report.backend_logs,
            global_deduplication=global_deduplication
        )
        
        # Write CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
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
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for correlation in correlations:
                writer.writerow(correlation)
        
        logger.info(f"Exported {len(correlations)} log correlations to {output_file}")
        return output_file
    
    def _create_correlation_mappings(
        self, 
        frontend_errors: List[LogError], 
        backend_logs: List[BackendLogEntry],
        global_deduplication: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Create correlation mappings between frontend and backend logs
        
        Args:
            frontend_errors: List of frontend errors
            backend_logs: List of backend logs
            global_deduplication: If True, deduplicate backend messages globally across all frontend errors
            
        Returns:
            List of correlation dictionaries
        """
        correlations = []
        global_backend_seen = set() if global_deduplication else None
        
        for frontend_error in frontend_errors:
            # Find correlating backend logs for this frontend error
            correlated_backends = self._find_correlated_backends(frontend_error, backend_logs)
            
            if correlated_backends:
                # Create a row for each correlated backend log
                for backend_log, correlation_info in correlated_backends:
                    
                    # Global deduplication check
                    if global_deduplication:
                        backend_id = self._create_backend_log_id(backend_log)
                        if backend_id in global_backend_seen:
                            continue  # Skip this duplicate
                        global_backend_seen.add(backend_id)
                    
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
                        # Global deduplication check
                        if global_deduplication:
                            backend_id = self._create_backend_log_id(backend_log)
                            if backend_id in global_backend_seen:
                                continue  # Skip this duplicate
                            global_backend_seen.add(backend_id)
                        
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
    
    def _find_correlated_backends(
        self, 
        frontend_error: LogError, 
        backend_logs: List[BackendLogEntry]
    ) -> List[tuple]:
        """
        Find backend logs that correlate with a frontend error (with deduplication)
        
        Deduplication: Backend logs with same message field will only appear once
        per frontend error, keeping the correlation with highest priority.
        
        Args:
            frontend_error: Frontend error to find correlations for
            backend_logs: List of backend logs to search
            
        Returns:
            List of tuples (backend_log, correlation_info) - deduplicated by message field
        """
        # Use dict to store best correlation for each unique backend log
        best_correlations = {}
        
        for backend_log in backend_logs:
            correlation_info = self._check_correlation(frontend_error, backend_log)
            if correlation_info:
                # Create unique identifier for backend log
                backend_id = self._create_backend_log_id(backend_log)
                
                # Keep the correlation with highest confidence
                if (backend_id not in best_correlations or 
                    self._is_better_correlation(correlation_info, best_correlations[backend_id][1])):
                    best_correlations[backend_id] = (backend_log, correlation_info)
        
        return list(best_correlations.values())
    
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
        
        return None
    
    def _create_backend_log_id(self, backend_log: BackendLogEntry) -> str:
        """
        Create a unique identifier for backend log deduplication using message field
        
        Args:
            backend_log: Backend log entry
            
        Returns:
            The message field as deduplication key (normalized)
        """
        # Use the backend_log.message as the deduplication key
        # Normalize to handle invisible characters and whitespace differences
        message = backend_log.message
        
        # Strip all types of whitespace and normalize
        normalized = ' '.join(message.split())
        
        return normalized
    
    def _is_better_correlation(self, new_correlation: Dict[str, Any], existing_correlation: Dict[str, Any]) -> bool:
        """
        Determine if a new correlation is better than an existing one
        
        Args:
            new_correlation: New correlation info
            existing_correlation: Existing correlation info
            
        Returns:
            True if new correlation is better, False otherwise
        """
        # Define correlation method priority (higher = better)
        priority_map = {
            'request_id_match': 1,          # Only priority - exact match
        }
        
        new_priority = priority_map.get(new_correlation.get('method', ''), 0)
        existing_priority = priority_map.get(existing_correlation.get('method', ''), 0)
        
        # If same priority, prefer the one with smaller time difference
        if new_priority == existing_priority:
            new_time_diff = new_correlation.get('time_diff_seconds', float('inf'))
            existing_time_diff = existing_correlation.get('time_diff_seconds', float('inf'))
            return new_time_diff < existing_time_diff
        
        return new_priority > existing_priority
    
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
        
        # Find backend logs within reasonable time window (±5 minutes)
        time_based_logs = []
        from datetime import timedelta
        
        for backend_log in backend_logs:
            if backend_log.timestamp:
                time_diff = abs((backend_log.timestamp - frontend_time).total_seconds())
                # Include backend logs within 5 minutes of frontend error
                if time_diff <= 300:  # 5 minutes = 300 seconds
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