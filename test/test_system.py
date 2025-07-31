#!/usr/bin/env python3
"""
Basic test script for Bug Analysis Agent components
"""

import logging
from bug_analysis_agent.models import UserReport, LogError
from bug_analysis_agent.downloader import LogDownloader
from bug_analysis_agent.scanner import LogScanner
from bug_analysis_agent.cloudwatch import CloudWatchFinder
from bug_analysis_agent.analyzer import BugAnalyzer

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_models():
    """Test Pydantic models"""
    print("🧪 Testing Models...")
    
    # Test UserReport
    report_data = {
        "username": "@testuser",
        "user_id": "12345",
        "platform": "iOS",
        "os_version": "18.5",
        "app_version": "1.0.0",
        "log_url": "https://example.com/test.log",
        "env": "test",
        "feedback": "Test feedback"
    }
    
    try:
        user_report = UserReport(**report_data)
        print(f"✅ UserReport model: {user_report.username}")
    except Exception as e:
        print(f"❌ UserReport model failed: {e}")
        return False
    
    # Test LogError
    try:
        log_error = LogError(
            error_type="TEST_ERROR",
            log_segment="Test error line",
            context_before=["line 1", "line 2"],
            context_after=["line 4", "line 5"],
            line_number=3
        )
        print(f"✅ LogError model: {log_error.error_type}")
    except Exception as e:
        print(f"❌ LogError model failed: {e}")
        return False
    
    return True


def test_log_scanner():
    """Test LogScanner with sample log data"""
    print("\n🧪 Testing LogScanner...")
    
    sample_log = """
2024-01-01T10:00:01.000Z INFO App started
2024-01-01T10:00:02.000Z DEBUG Loading user data
2024-01-01T10:00:03.000Z [E] Failed to connect to database
2024-01-01T10:00:04.000Z INFO Retrying connection
2024-01-01T10:00:05.000Z ERROR: Network timeout occurred
2024-01-01T10:00:06.000Z INFO Connection restored
"""
    
    try:
        scanner = LogScanner()
        errors = scanner.scan_for_errors(sample_log, context_lines=2)
        print(f"✅ LogScanner found {len(errors)} errors")
        
        for error in errors:
            print(f"   - {error.error_type} at line {error.line_number}")
            
        return len(errors) > 0
        
    except Exception as e:
        print(f"❌ LogScanner failed: {e}")
        return False


def test_log_downloader():
    """Test LogDownloader URL validation"""
    print("\n🧪 Testing LogDownloader...")
    
    try:
        downloader = LogDownloader()
        
        # Test URL validation
        valid_urls = [
            "https://example.com/app.log",
            "http://logs.example.com/error.log",
            "https://s3.amazonaws.com/bucket/logs/app.log"
        ]
        
        invalid_urls = [
            "not-a-url",
            "ftp://example.com/file.txt",
            "https://example.com/not-a-log"
        ]
        
        for url in valid_urls:
            if not downloader.is_valid_log_url(url):
                print(f"❌ Valid URL marked as invalid: {url}")
                return False
        
        for url in invalid_urls:
            if downloader.is_valid_log_url(url):
                print(f"❌ Invalid URL marked as valid: {url}")
                return False
        
        print("✅ LogDownloader URL validation works")
        return True
        
    except Exception as e:
        print(f"❌ LogDownloader failed: {e}")
        return False


def test_cloudwatch_finder():
    """Test CloudWatchFinder initialization"""
    print("\n🧪 Testing CloudWatchFinder...")
    
    try:
        # Test without credentials (should not fail initialization)
        finder = CloudWatchFinder(region_name='us-east-1')
        
        # Test connection (may fail without credentials, but shouldn't crash)
        connection_ok = finder.test_connection()
        
        print(f"✅ CloudWatchFinder initialized (connection: {'ok' if connection_ok else 'unavailable'})")
        return True
        
    except Exception as e:
        print(f"❌ CloudWatchFinder failed: {e}")
        return False


def test_bug_analyzer():
    """Test BugAnalyzer initialization"""
    print("\n🧪 Testing BugAnalyzer...")
    
    try:
        # Initialize without API keys (should work with fallbacks)
        analyzer = BugAnalyzer()
        
        # Test health status
        health = analyzer.get_health_status()
        print(f"✅ BugAnalyzer initialized")
        print(f"   Health status: {health}")
        
        return True
        
    except Exception as e:
        print(f"❌ BugAnalyzer failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🔍 Bug Analysis Agent - Component Tests")
    print("=" * 50)
    
    tests = [
        test_models,
        test_log_scanner,
        test_log_downloader,
        test_cloudwatch_finder,
        test_bug_analyzer
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ All tests passed! System is ready to use.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = main()
    sys.exit(exit_code) 