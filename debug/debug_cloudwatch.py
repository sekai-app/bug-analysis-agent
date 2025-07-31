#!/usr/bin/env python3
"""
Debug CloudWatch Connectivity and Query Issues
"""

import logging
from bug_analysis_agent.cloudwatch import CloudWatchFinder
from bug_analysis_agent.config import Config
from bug_analysis_agent.models import LogError
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    print("🔍 CloudWatch Debug Tool")
    print("=" * 50)
    
    # Step 1: Check configuration
    print("\n1. Configuration Check:")
    config_summary = Config.get_summary()
    for key, value in config_summary.items():
        print(f"   {key}: {value}")
    
    if not Config.is_aws_configured():
        print("❌ AWS not properly configured!")
        return
    
    if not Config.CLOUDWATCH_LOG_GROUP:
        print("❌ CLOUDWATCH_LOG_GROUP not set!")
        return
    
    # Step 2: Initialize CloudWatch
    print("\n2. CloudWatch Initialization:")
    finder = CloudWatchFinder(
        region_name=Config.AWS_REGION,
        log_group=Config.CLOUDWATCH_LOG_GROUP
    )
    
    if not finder.logs_client:
        print("❌ CloudWatch client failed to initialize!")
        return
    
    # Step 3: Test basic connectivity
    print("\n3. Testing CloudWatch Connectivity:")
    if finder.test_connection():
        print("✅ CloudWatch connection successful!")
    else:
        print("❌ CloudWatch connection failed!")
        return
    
    # Step 4: Test CloudWatch Insights
    print(f"\n4. Testing CloudWatch Insights (log group: {Config.CLOUDWATCH_LOG_GROUP}):")
    if finder.test_insights_query(Config.CLOUDWATCH_LOG_GROUP):
        print("✅ CloudWatch Insights working!")
    else:
        print("❌ CloudWatch Insights failed!")
        return
    
    # Step 5: Test with sample request ID
    print("\n5. Testing Request ID Search:")
    sample_request_id = input("Enter a known request ID to test (or press Enter to skip): ").strip()
    
    if sample_request_id:
        print(f"Searching for request ID: {sample_request_id}")
        
        # Create a sample error
        sample_error = LogError(
            timestamp=datetime.now().isoformat(),
            request_ids=[sample_request_id],
            error_type="TEST_ERROR",
            log_segment="Test error message",
            context_before=[],
            context_after=[],
            line_number=1
        )
        
        print("Executing CloudWatch search...")
        backend_logs = finder.find_correlating_logs([sample_error])
        
        print(f"Found {len(backend_logs)} backend logs")
        for i, log in enumerate(backend_logs[:3]):  # Show first 3
            print(f"  Log {i+1}: {log.timestamp} - {log.message[:100]}...")
    
    # Step 6: Test regex validation
    print("\n6. Testing Request ID Validation:")
    test_ids = [
        "abc123def456",  # Valid
        "null",          # Invalid 
        "12345",         # Too short
        "req-id-12345678",  # Valid
        "",              # Empty
        "undefined"      # Invalid
    ]
    
    for test_id in test_ids:
        valid = finder._is_valid_request_id_for_search(test_id)
        print(f"  '{test_id}' -> {'✅ Valid' if valid else '❌ Invalid'}")
    
    print("\n✅ CloudWatch debugging complete!")

if __name__ == "__main__":
    main() 