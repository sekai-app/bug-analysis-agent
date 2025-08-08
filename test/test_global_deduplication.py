#!/usr/bin/env python3
"""
Test script to demonstrate global vs per-frontend deduplication
"""

from datetime import datetime, timedelta
from bug_analysis_agent.models import LogError, BackendLogEntry
from bug_analysis_agent.analyzer import BugAnalyzer

def test_global_vs_per_frontend_deduplication():
    """Compare global vs per-frontend deduplication"""
    
    print("🧪 GLOBAL vs PER-FRONTEND DEDUPLICATION TEST")
    print("=" * 60)
    
    # Create test data: 2 frontend errors, 1 shared backend message
    base_time = datetime(2024, 7, 30, 10, 0, 0)
    
    # Frontend errors
    frontend_error1 = LogError(
        timestamp="2024-07-30T10:00:10Z",
        request_id="abc123",
        error_type="EXPLICIT_ERROR",
        log_segment="[E] Database timeout error",
        context_before=[], context_after=[],
        line_number=100
    )
    
    frontend_error2 = LogError(
        timestamp="2024-07-30T10:00:20Z", 
        request_id="def456",
        error_type="EXPLICIT_ERROR", 
        log_segment="[E] Another database timeout",
        context_before=[], context_after=[],
        line_number=200
    )
    
    # Backend logs - with duplicate messages
    backend_logs = [
        # This message will correlate with BOTH frontend errors
        BackendLogEntry(
            timestamp=base_time + timedelta(seconds=10),
            message="Database connection pool exhausted",  # Same message
            request_id=None,
            log_group="/aws/lambda/api",
            log_stream="stream1"
        ),
        BackendLogEntry(
            timestamp=base_time + timedelta(seconds=20),
            message="Database connection pool exhausted",  # Same message again  
            request_id=None,
            log_group="/aws/lambda/api",
            log_stream="stream2"
        ),
        BackendLogEntry(
            timestamp=base_time + timedelta(seconds=15),
            message="Request abc123 processing started",
            request_id="abc123",
            log_group="/aws/lambda/api",
            log_stream="stream1"
        ),
        BackendLogEntry(
            timestamp=base_time + timedelta(seconds=25),
            message="Request def456 processing started", 
            request_id="def456",
            log_group="/aws/lambda/api",
            log_stream="stream1"
        )
    ]
    
    analyzer = BugAnalyzer()
    
    print("📥 Test Data:")
    print(f"  Frontend Errors: 2")
    print(f"  Backend Logs: {len(backend_logs)}")
    print(f"  Duplicate Backend Messages: 'Database connection pool exhausted' (appears 2x)")
    print()
    
    # Test WITHOUT global deduplication
    print("🔄 WITHOUT Global Deduplication (per-frontend only):")
    correlations_no_global = analyzer._create_direct_correlation_mappings(
        [frontend_error1, frontend_error2], 
        backend_logs,
        max_correlations_per_error=3
    )
    
    backend_messages_no_global = [c['backend_message'] for c in correlations_no_global if c['backend_message']]
    duplicate_count_no_global = len([msg for msg in backend_messages_no_global if msg == "Database connection pool exhausted"])
    
    print(f"  Total CSV rows: {len(correlations_no_global)}")
    print(f"  'Database connection pool exhausted' appears: {duplicate_count_no_global} times")
    print()
    
    # Test WITH global deduplication
    print("✅ WITH Global Deduplication:")
    correlations_global = analyzer._create_direct_correlation_mappings(
        [frontend_error1, frontend_error2],
        backend_logs, 
        max_correlations_per_error=1  # Limit to 1 to simulate global deduplication
    )
    
    backend_messages_global = [c['backend_message'] for c in correlations_global if c['backend_message']]
    duplicate_count_global = len([msg for msg in backend_messages_global if msg == "Database connection pool exhausted"])
    
    print(f"  Total CSV rows: {len(correlations_global)}")
    print(f"  'Database connection pool exhausted' appears: {duplicate_count_global} times")
    print()
    
    # Show detailed breakdown
    print("📋 DETAILED BREAKDOWN:")
    print("-" * 30)
    
    print("\nWithout Global Deduplication:")
    for i, corr in enumerate(correlations_no_global, 1):
        if corr['backend_message']:
            print(f"  {i}. Frontend Line {corr['frontend_line_number']} → '{corr['backend_message']}'")
    
    print("\nWith Global Deduplication:")
    for i, corr in enumerate(correlations_global, 1):
        if corr['backend_message']:
            print(f"  {i}. Frontend Line {corr['frontend_line_number']} → '{corr['backend_message']}'")
    
    print(f"\n📊 SUMMARY:")
    print(f"  Duplicates removed by global deduplication: {len(correlations_no_global) - len(correlations_global)}")
    print(f"  CSV rows saved: {len(correlations_no_global) - len(correlations_global)}")

if __name__ == "__main__":
    test_global_vs_per_frontend_deduplication() 