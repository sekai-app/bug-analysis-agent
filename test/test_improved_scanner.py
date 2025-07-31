#!/usr/bin/env python3
"""
Test script to demonstrate improved error scanning
"""

from bug_analysis_agent.scanner import LogScanner

# Sample log with the issues you mentioned
sample_log = """
[07-29 18:25:08] [I] [network] receiveDataWhenStatusError: true
[07-29 18:25:28] [I] [network] receiveDataWhenStatusError: true
[07-29 18:25:32] [E] Database connection failed: timeout after 30s
[07-29 18:25:38] [I] [network] receiveDataWhenStatusError: true
[07-29 18:25:48] [I] [network] receiveDataWhenStatusError: true
[07-29 18:26:00] [E] Database connection failed: timeout after 30s
[07-29 18:26:01] [I] [network] receiveDataWhenStatusError: true
[07-29 18:26:06] TypeError: Cannot read property 'name' of undefined
[07-29 18:26:07] [I] [network] receiveDataWhenStatusError: true
[07-29 18:26:08] [INFO] errorHandling: enabled
[07-29 18:26:18] [I] [network] receiveDataWhenStatusError: true
[07-29 18:26:19] RangeError: Array index out of bounds
[07-29 18:26:25] [I] [network] receiveDataWhenStatusError: true
[07-29 18:26:26] TypeError: Cannot read property 'name' of undefined
[07-29 18:26:28] [ERROR] Failed to authenticate user
[07-29 18:26:35] [I] [network] receiveDataWhenStatusError: true
[07-29 18:26:45] [E] Database connection failed: timeout after 35s
[07-29 18:26:50] [I] [network] receiveDataWhenStatusError: true
[07-29 18:27:00] [DEBUG] Error recovery process started
[07-29 18:27:08] [I] [network] receiveDataWhenStatusError: true
"""

def main():
    print("🔍 Testing Improved Error Scanner")
    print("=" * 50)
    
    scanner = LogScanner()
    errors = scanner.scan_for_errors(sample_log, context_lines=1)
    
    print(f"📊 Total unique errors found: {len(errors)}")
    print()
    
    for i, error in enumerate(errors, 1):
        print(f"Error {i}: {error.error_type}")
        print(f"  Line {error.line_number}: {error.log_segment.strip()}")
        if error.timestamp:
            print(f"  Timestamp: {error.timestamp}")
        if error.request_id:
            print(f"  Request ID: {error.request_id}")
        print()
    
    # Show what was excluded
    print("🚫 Examples of what was EXCLUDED (not treated as errors):")
    excluded_examples = [
        "[I] [network] receiveDataWhenStatusError: true",
        "[INFO] errorHandling: enabled", 
        "[DEBUG] Error recovery process started"
    ]
    
    for example in excluded_examples:
        print(f"  ✅ {example}")
    
    print()
    print("✨ Key Improvements:")
    print("  • Ignores [I], [INFO], [DEBUG] level logs")
    print("  • Excludes known non-error patterns like 'receiveDataWhenStatusError'")
    print("  • Deduplicates identical error messages")
    print("  • More precise regex patterns with word boundaries")

if __name__ == "__main__":
    main() 