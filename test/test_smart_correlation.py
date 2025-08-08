#!/usr/bin/env python3
"""
Test script to demonstrate improved correlation logic with limits
"""

from bug_analysis_agent.analyzer import BugAnalyzer
import json

def test_smart_correlation():
    """Test the improved correlation logic"""
    
    print("🧪 SMART CORRELATION LOGIC TEST")
    print("=" * 60)
    
    # Sample report data
    sample_report = {
        "username": "@chiyoED_67",
        "user_id": "2856398",
        "platform": "iOS",
        "os_version": "18.5 (22F76)",
        "app_version": "1.31.0",
        "log_url": "https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.31.0_prod_20250730T004620Z.log",
        "env": "prod",
        "feedback": "Audio downloads keep failing"
    }
    
    analyzer = BugAnalyzer()
    
    print("🎯 TESTING DIFFERENT CORRELATION LIMITS:")
    print("-" * 40)
    
    # Test with different correlation limits
    test_limits = [1, 3, 10]
    
    for limit in test_limits:
        print(f"\n📊 Testing with max_correlations_per_error = {limit}")
        print("-" * 30)
        
        try:
            # Analyze with specific correlation limit
            triage_report = analyzer.analyze_report(
                sample_report,
                max_correlations_per_error=limit
            )
            
            # Count backend correlations per frontend error
            correlations_per_error = {}
            
            for correlation in analyzer._create_direct_correlation_mappings(
                triage_report.frontend_errors, 
                triage_report.backend_logs,
                max_correlations_per_error=limit
            ):
                frontend_line = correlation['frontend_line_number']
                if frontend_line not in correlations_per_error:
                    correlations_per_error[frontend_line] = 0
                if correlation['backend_message']:  # Skip no_correlation entries
                    correlations_per_error[frontend_line] += 1
            
            print(f"Frontend errors found: {len(triage_report.frontend_errors)}")
            print(f"Total backend logs: {len(triage_report.backend_logs)}")
            
            # Show breakdown by frontend error
            for frontend_line, backend_count in correlations_per_error.items():
                print(f"  Line {frontend_line}: {backend_count} backend correlations")
            
            # Calculate average correlations per error
            if correlations_per_error:
                avg_correlations = sum(correlations_per_error.values()) / len(correlations_per_error)
                print(f"Average correlations per frontend error: {avg_correlations:.1f}")
                
                # Check if limit is being respected
                max_correlations_found = max(correlations_per_error.values()) if correlations_per_error else 0
                if max_correlations_found <= limit:
                    print(f"✅ Limit respected (max found: {max_correlations_found})")
                else:
                    print(f"❌ Limit exceeded (max found: {max_correlations_found})")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    print(f"\n🎯 RECOMMENDED SETTINGS:")
    print("- max_correlations_per_error = 3 (default)")
    print("- Balances thoroughness with noise reduction")
    print("- Prevents one frontend error from dominating the CSV")

def demo_before_after():
    """Show comparison between old unlimited and new limited approach"""
    
    print(f"\n🔄 BEFORE vs AFTER COMPARISON")
    print("=" * 60)
    
    sample_report = {
        "username": "@chiyoED_67", 
        "user_id": "2856398",
        "platform": "iOS",
        "log_url": "https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.31.0_prod_20250730T004620Z.log",
        "feedback": "Multiple issues"
    }
    
    analyzer = BugAnalyzer()
    
    print("📈 BEFORE (Unlimited correlations):")
    print("- One frontend error could match 50+ backend logs")
    print("- CSV filled with mostly noise") 
    print("- Hard to find meaningful patterns")
    print("- Example: Line 7045 → 40+ different backend messages")
    
    print(f"\n📉 AFTER (Limited correlations):")
    print("- Max 3 backend correlations per frontend error")
    print("- Prioritizes request_id matches over time window")
    print("- Cleaner, more actionable CSV output")
    print("- Focus on quality over quantity")

if __name__ == "__main__":
    test_smart_correlation()
    demo_before_after() 