#!/usr/bin/env python3
"""
Test script to demonstrate backend log deduplication
"""

from datetime import datetime, timedelta
from bug_analysis_agent.models import LogError, BackendLogEntry
from bug_analysis_agent.analyzer import BugAnalyzer

def create_test_data():
    """Create test frontend error and backend logs"""
    
    # Frontend error with request ID
    frontend_error = LogError(
        timestamp="2024-07-30T10:00:15Z",
        request_id="abc123",
        error_type="EXPLICIT_ERROR",
        log_segment="[E] API call failed: timeout",
        context_before=["Previous line 1", "Previous line 2"],
        context_after=["Next line 1", "Next line 2"],
        line_number=100
    )
    
    # Backend logs - some duplicates that would match through multiple methods
    base_time = datetime(2024, 7, 30, 10, 0, 14)
    
    backend_logs = [
        # This log will match both by request_id AND time_window
        BackendLogEntry(
            timestamp=base_time,
            message="Processing request abc123 - starting validation",
            request_id="abc123",
            log_group="/aws/lambda/api",
            log_stream="stream1"
        ),
        
        # This log will match both by request_id AND time_window  
        BackendLogEntry(
            timestamp=base_time + timedelta(seconds=2),
            message="Request abc123 failed: database timeout",
            request_id="abc123", 
            log_group="/aws/lambda/api",
            log_stream="stream1"
        ),
        
        # This log will match ONLY by time_window (no request_id)
        BackendLogEntry(
            timestamp=base_time + timedelta(seconds=3),
            message="Database connection pool exhausted",
            request_id=None,
            log_group="/aws/lambda/api", 
            log_stream="stream2"
        ),
        
        # Duplicate of first log (same message, different timestamp and stream)
        BackendLogEntry(
            timestamp=base_time + timedelta(seconds=1),  # Different timestamp
            message="Processing request abc123 - starting validation",  # Same message
            request_id="abc123",
            log_group="/aws/lambda/api",
            log_stream="stream2"  # Different stream
        ),
        
        # Another duplicate with exact same message (should be deduplicated)
        BackendLogEntry(
            timestamp=base_time + timedelta(seconds=10),
            message="Processing request abc123 - starting validation",  # Exact same message
            request_id="abc123",
            log_group="/aws/lambda/api",
            log_stream="stream3"
        ),
        
        # This log will match by partial request_id (abc123 in message)
        BackendLogEntry(
            timestamp=base_time + timedelta(seconds=5),
            message="Cleaning up failed request abc123 resources",
            request_id="xyz789",  # Different request ID
            log_group="/aws/lambda/api",
            log_stream="stream3"
        )
    ]
    
    return frontend_error, backend_logs

def test_deduplication():
    """Test backend log deduplication"""
    
    print("🧪 BACKEND LOG DEDUPLICATION TEST")
    print("=" * 50)
    
    frontend_error, backend_logs = create_test_data()
    analyzer = BugAnalyzer()
    
    print(f"📥 Input:")
    print(f"  Frontend Error: {frontend_error.log_segment}")
    print(f"  Request ID: {frontend_error.request_id}")
    print(f"  Timestamp: {frontend_error.timestamp}")
    print(f"  Backend Logs: {len(backend_logs)} logs")
    print()
    
    # Show all backend logs
    print("📋 All Backend Logs:")
    for i, log in enumerate(backend_logs, 1):
        print(f"  {i}. [{log.timestamp}] {log.message}")
        print(f"     Request ID: {log.request_id}, Stream: {log.log_stream}")
    print()
    
    # Find correlations with deduplication
    correlations = analyzer._find_correlated_backends(frontend_error, backend_logs)
    
    print("🔗 Correlations Found (After Deduplication):")
    print(f"  Total correlations: {len(correlations)}")
    print()
    
    for i, (backend_log, correlation_info) in enumerate(correlations, 1):
        print(f"  Correlation {i}:")
        print(f"    Backend: [{backend_log.timestamp}] {backend_log.message}")
        print(f"    Method: {correlation_info['method']}")
        print(f"    Confidence: {correlation_info['confidence']}")
        if 'time_diff_seconds' in correlation_info:
            print(f"    Time Diff: {correlation_info['time_diff_seconds']}s")
        print()
    
    # Show what got deduplicated
    print("🎯 DEDUPLICATION RESULTS:")
    print("-" * 30)
    
    # Create backend log IDs to show what was deduplicated
    unique_ids = set()
    duplicate_count = 0
    
    for backend_log in backend_logs:
        backend_id = analyzer._create_backend_log_id(backend_log)
        if backend_id in unique_ids:
            duplicate_count += 1
            print(f"  ❌ DUPLICATE: {backend_log.message}")
        else:
            unique_ids.add(backend_id)
            print(f"  ✅ UNIQUE: {backend_log.message}")
    
    print(f"\n📊 Summary:")
    print(f"  Original backend logs: {len(backend_logs)}")
    print(f"  Unique backend logs: {len(unique_ids)}")
    print(f"  Duplicates removed: {duplicate_count}")
    print(f"  Final correlations: {len(correlations)}")
    
    # Show correlation priority
    print(f"\n🏆 CORRELATION PRIORITY:")
          print(f"  1. request_id_match (only method)")
    print(f"  • Same priority → prefer smaller time difference")
    print(f"\n🔄 DEDUPLICATION RULE:")
    print(f"  • Same backend.message field = duplicate (regardless of timestamp/stream)")
    print(f"  • Exact message match (case-sensitive, whitespace preserved)")

if __name__ == "__main__":
    test_deduplication() 