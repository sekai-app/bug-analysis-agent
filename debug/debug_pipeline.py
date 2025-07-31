#!/usr/bin/env python3
"""
Debug the entire bug analysis pipeline to find where CloudWatch is skipped
"""

import logging
import json
from bug_analysis_agent.analyzer import BugAnalyzer
from bug_analysis_agent.config import Config
from bug_analysis_agent.models import LogError
from datetime import datetime

# Setup detailed logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_report():
    """Create a test report with a sample log URL"""
    return {
        "username": "test_user",
        "user_id": "test_123",
        "platform": "iOS",
        "os_version": "17.0",
        "app_version": "1.0.0",
        "log_url": "https://example.com/sample.log",  # Replace with real log URL
        "env": "prod",
        "feedback": "App crashes when I try to login"
    }

def debug_frontend_errors(analyzer, log_content):
    """Debug frontend error detection"""
    print("\n" + "="*60)
    print("🔍 DEBUGGING FRONTEND ERROR DETECTION")
    print("="*60)
    
    print(f"Log content length: {len(log_content)} characters")
    print(f"First 500 chars:\n{log_content[:500]}...")
    
    # Scan for errors
    frontend_errors = analyzer.scanner.scan_for_errors(log_content, 10, 5)
    print(f"\n📊 Found {len(frontend_errors)} frontend errors")
    
    for i, error in enumerate(frontend_errors):
        print(f"\n--- Error {i+1} ---")
        print(f"Line: {error.line_number}")
        print(f"Type: {error.error_type}")
        print(f"Timestamp: '{error.timestamp}'")
        print(f"Request ID: '{error.request_id}'")
        print(f"Request IDs: {error.request_ids}")
        print(f"Message: {error.log_segment[:100]}...")
        
        # Test timestamp parsing
        parsed_ts = analyzer.cloudwatch._parse_timestamp(error.timestamp)
        print(f"Parsed timestamp: {parsed_ts}")
        
        # Test request ID validation
        if error.request_ids:
            for req_id in error.request_ids:
                valid = analyzer.cloudwatch._is_valid_request_id_for_search(req_id)
                print(f"Request ID '{req_id}' valid: {valid}")
    
    return frontend_errors

def debug_cloudwatch_conditions(analyzer, frontend_errors):
    """Debug CloudWatch skip conditions"""
    print("\n" + "="*60)
    print("🔍 DEBUGGING CLOUDWATCH CONDITIONS")
    print("="*60)
    
    # Check 1: CloudWatch client availability
    print(f"1. CloudWatch client available: {analyzer.cloudwatch.logs_client is not None}")
    
    # Check 2: Log group configuration  
    print(f"2. Default log group: '{analyzer.cloudwatch.default_log_group}'")
    print(f"3. Config log group: '{Config.CLOUDWATCH_LOG_GROUP}'")
    
    # Check 3: Frontend errors exist
    print(f"4. Frontend errors found: {len(frontend_errors)} (skip if 0)")
    
    if not frontend_errors:
        print("❌ SKIPPED: No frontend errors found - CloudWatch correlation will be skipped!")
        return
    
    # Check 4: Individual error conditions
    for i, error in enumerate(frontend_errors):
        print(f"\n--- Error {i+1} Analysis ---")
        
        # Timestamp check
        timestamp = analyzer.cloudwatch._parse_timestamp(error.timestamp)
        print(f"  Timestamp parseable: {timestamp is not None}")
        if not timestamp:
            print(f"  ❌ SKIP REASON: No valid timestamp")
            continue
        
        # Request ID check
        request_ids = error.request_ids if error.request_ids else ([error.request_id] if error.request_id else [])
        print(f"  Request IDs to search: {request_ids}")
        
        if not request_ids:
            print(f"  ❌ SKIP REASON: No request IDs found")
            continue
        
        # Validate each request ID
        valid_ids = []
        for req_id in request_ids:
            if req_id and analyzer.cloudwatch._is_valid_request_id_for_search(req_id):
                valid_ids.append(req_id)
            else:
                print(f"  ❌ Invalid request ID: '{req_id}'")
        
        if not valid_ids:
            print(f"  ❌ SKIP REASON: No valid request IDs")
            continue
        
        print(f"  ✅ This error should trigger CloudWatch search for: {valid_ids}")

def main():
    print("🔍 Bug Analysis Pipeline Debugger")
    print("=" * 60)
    
    # Configuration check
    print("\n1. Configuration Check:")
    config_summary = Config.get_summary()
    for key, value in config_summary.items():
        print(f"   {key}: {value}")
    
    # Initialize analyzer
    print("\n2. Initializing Analyzer:")
    try:
        analyzer = BugAnalyzer(
            openai_api_key=Config.OPENAI_API_KEY,
            aws_region=Config.AWS_REGION,
            cloudwatch_log_group=Config.CLOUDWATCH_LOG_GROUP,
            gpt_model=Config.GPT_MODEL
        )
        print("✅ Analyzer initialized successfully")
    except Exception as e:
        print(f"❌ Analyzer initialization failed: {e}")
        return
    
    # Test report
    test_report = create_test_report()
    print(f"\n3. Test Report: {test_report}")
    
    # Prompt for log content (since we can't download from example.com)
    print("\n4. Log Content:")
    print("Since we can't download from example.com, please provide sample log content.")
    print("You can either:")
    print("A) Paste log content directly")
    print("B) Press Enter to use a minimal test log")
    
    user_input = input("\nPaste log content (or press Enter for test log): ").strip()
    
    if user_input:
        log_content = user_input
    else:
        # Create test log with potential issues
        log_content = """
2024-07-31 10:30:15 [INFO] App started
2024-07-31 10:30:20 [INFO] User login attempt request_id: abc123def456
2024-07-31 10:30:25 [ERROR] NetworkError: Connection failed request_id: abc123def456
2024-07-31 10:30:26 [ERROR] Login failed
2024-07-31 10:30:30 [INFO] App terminated
        """.strip()
        print(f"Using test log content:\n{log_content}")
    
    # Debug frontend error detection
    frontend_errors = debug_frontend_errors(analyzer, log_content)
    
    # Debug CloudWatch conditions  
    debug_cloudwatch_conditions(analyzer, frontend_errors)
    
    # Attempt CloudWatch correlation
    if frontend_errors:
        print("\n" + "="*60)
        print("🔍 ATTEMPTING CLOUDWATCH CORRELATION")
        print("="*60)
        
        try:
            backend_logs = analyzer.cloudwatch.find_correlating_logs(
                frontend_errors,
                log_group=Config.CLOUDWATCH_LOG_GROUP,
                time_window_minutes=4
            )
            print(f"✅ CloudWatch search completed: {len(backend_logs)} logs found")
            
            for i, log in enumerate(backend_logs[:3]):
                print(f"  Log {i+1}: {log.timestamp} - {log.message[:100]}...")
                
        except Exception as e:
            print(f"❌ CloudWatch search failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n✅ Pipeline debugging complete!")

if __name__ == "__main__":
    main() 