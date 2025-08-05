#!/usr/bin/env python3
"""
Debug script to identify CloudWatch performance bottlenecks
"""

import sys
import os
import time
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_cloudwatch_performance():
    """Test CloudWatch performance and identify bottlenecks"""
    print("🔍 CloudWatch Performance Diagnostic")
    print("=" * 60)
    
    try:
        from bug_analysis_agent.cloudwatch import CloudWatchFinder
        from bug_analysis_agent.config import Config
        
        print(f"📋 Configuration:")
        print(f"  - AWS Region: {Config.AWS_REGION}")
        print(f"  - CloudWatch Log Group: {Config.CLOUDWATCH_LOG_GROUP}")
        print(f"  - AWS Configured: {Config.is_aws_configured()}")
        
        if not Config.is_aws_configured():
            print("❌ AWS not configured - check credentials")
            return False
        
        # Initialize CloudWatch client
        print("\n🔧 Initializing CloudWatch client...")
        start_time = time.time()
        cloudwatch = CloudWatchFinder(
            region_name=Config.AWS_REGION,
            log_group=Config.CLOUDWATCH_LOG_GROUP
        )
        init_time = time.time() - start_time
        print(f"✅ CloudWatch client initialized in {init_time:.2f}s")
        
        # Test connection
        print("\n🔗 Testing CloudWatch connection...")
        start_time = time.time()
        connection_ok = cloudwatch.test_connection()
        connection_time = time.time() - start_time
        print(f"✅ Connection test completed in {connection_time:.2f}s")
        print(f"   Connection status: {'OK' if connection_ok else 'FAILED'}")
        
        if not connection_ok:
            print("❌ CloudWatch connection failed")
            return False
        
        # Test log group access
        if Config.CLOUDWATCH_LOG_GROUP:
            print(f"\n📁 Testing log group access: {Config.CLOUDWATCH_LOG_GROUP}")
            start_time = time.time()
            try:
                # Test a simple query
                test_query = "fields @timestamp, @message | limit 1"
                response = cloudwatch.logs_client.start_query(
                    logGroupName=Config.CLOUDWATCH_LOG_GROUP,
                    startTime=int((datetime.now() - timedelta(minutes=5)).timestamp()),
                    endTime=int(datetime.now().timestamp()),
                    queryString=test_query
                )
                query_id = response['queryId']
                print(f"✅ Test query started: {query_id}")
                
                # Wait for completion
                max_wait = 10
                for i in range(max_wait):
                    result = cloudwatch.logs_client.get_query_results(queryId=query_id)
                    if result['status'] == 'Complete':
                        print(f"✅ Test query completed in {i+1}s")
                        break
                    elif result['status'] == 'Failed':
                        print(f"❌ Test query failed")
                        break
                    time.sleep(1)
                else:
                    print(f"⚠️ Test query timed out after {max_wait}s")
                    
            except Exception as e:
                print(f"❌ Log group access failed: {e}")
        
        # Performance recommendations
        print("\n💡 Performance Recommendations:")
        print("1. ⏱️  Time Window: Reduce time_window_minutes (default: 10)")
        print("2. 🔍 Query Complexity: Simplify CloudWatch Insights queries")
        print("3. 📊 Log Volume: Check if log group has high volume")
        print("4. 🌐 Network: Check AWS region latency")
        print("5. 🔑 Permissions: Ensure proper CloudWatch permissions")
        
        # Common bottlenecks
        print("\n🐌 Common Bottlenecks:")
        print("- Large time windows (>10 minutes)")
        print("- Complex CloudWatch Insights queries")
        print("- High log volume in the specified time range")
        print("- Network latency to AWS region")
        print("- Insufficient IAM permissions")
        print("- CloudWatch Insights query limits")
        
        return True
        
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
        return False

def test_specific_query_performance():
    """Test performance of a specific query"""
    print("\n🧪 Testing Specific Query Performance")
    print("=" * 60)
    
    try:
        from bug_analysis_agent.cloudwatch import CloudWatchFinder
        from bug_analysis_agent.config import Config
        
        cloudwatch = CloudWatchFinder(
            region_name=Config.AWS_REGION,
            log_group=Config.CLOUDWATCH_LOG_GROUP
        )
        
        # Test different time windows
        time_windows = [5, 10, 15, 30]
        
        for window in time_windows:
            print(f"\n⏱️  Testing {window}-minute time window...")
            start_time = time.time()
            
            # Simulate the actual query process
            end_time = datetime.now()
            start_time_query = end_time - timedelta(minutes=window)
            
            query = """
            fields @timestamp, @message, @logStream
            | filter @message like /test/
            | sort @timestamp desc
            | limit 100
            """
            
            try:
                response = cloudwatch.logs_client.start_query(
                    logGroupName=Config.CLOUDWATCH_LOG_GROUP,
                    startTime=int(start_time_query.timestamp()),
                    endTime=int(end_time.timestamp()),
                    queryString=query
                )
                
                query_id = response['queryId']
                
                # Wait for completion
                max_wait = 30
                for i in range(max_wait):
                    result = cloudwatch.logs_client.get_query_results(queryId=query_id)
                    if result['status'] == 'Complete':
                        elapsed = time.time() - start_time
                        print(f"✅ {window}min window completed in {elapsed:.2f}s")
                        break
                    elif result['status'] == 'Failed':
                        print(f"❌ {window}min window failed")
                        break
                    time.sleep(1)
                else:
                    print(f"⚠️ {window}min window timed out")
                    
            except Exception as e:
                print(f"❌ {window}min window error: {e}")
        
    except Exception as e:
        print(f"❌ Query performance test failed: {e}")

def main():
    """Main diagnostic function"""
    print("🔍 CloudWatch Performance Diagnostic")
    print("=" * 60)
    print("This script will help identify why CloudWatch log downloading is slow")
    print("")
    
    # Run basic diagnostics
    success = test_cloudwatch_performance()
    
    if success:
        print("\n✅ Basic diagnostics completed")
        
        # Ask if user wants to run specific query test
        response = input("\n🧪 Run specific query performance test? (y/n): ")
        if response.lower() == 'y':
            test_specific_query_performance()
    else:
        print("\n❌ Basic diagnostics failed")

if __name__ == "__main__":
    main() 