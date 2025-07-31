#!/usr/bin/env python3
"""
Main entry point for Bug Analysis Agent
"""

import json
import logging
from typing import Dict, Any

from bug_analysis_agent.analyzer import BugAnalyzer
from bug_analysis_agent.config import Config


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def create_sample_report() -> Dict[str, Any]:
    """Create a sample user report for testing"""
    return {
        "username": "@chiyoED_67",
        "user_id": "2856398",
        "platform": "iOS",
        "os_version": "18.5 (22F76)",
        "app_version": "1.31.0",
        "log_url": "https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.31.0_prod_20250730T004620Z.log",
        "env": "prod",
        "feedback": "could u make all characters speak"
    }


def main():
    """Main function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("🔍 Bug Analysis Agent - User Review-Driven Log Triage & Analysis")
    print("=" * 70)
    
    # Show configuration
    config_summary = Config.get_summary()
    print(f"📋 Configuration Summary:")
    for key, value in config_summary.items():
        print(f"   {key}: {value}")
    print()
    
    # Initialize analyzer
    try:
        analyzer = BugAnalyzer(
            openai_api_key=Config.OPENAI_API_KEY,
            aws_region=Config.AWS_REGION,
            cloudwatch_log_group=Config.CLOUDWATCH_LOG_GROUP,
            gpt_model=Config.GPT_MODEL
        )
        
        # Check health status
        health = analyzer.get_health_status()
        print(f"🏥 Health Status:")
        for component, status in health.items():
            emoji = "✅" if status == 'ok' else "⚠️" if status == 'unavailable' else "❌"
            print(f"   {emoji} {component}: {status}")
        print()
        
    except Exception as e:
        logger.error(f"Failed to initialize analyzer: {e}")
        return 1
    
    # Demo with sample report
    print("🚀 Running Demo Analysis...")
    print("-" * 30)
    
    sample_report = create_sample_report()
    
    try:
        # Run analysis with CSV export
        result = analyzer.quick_analyze(sample_report, generate_csv=True)
        print(result)
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")
        return 1
    
    print("\n✅ Demo completed successfully!")
    return 0


def analyze_custom_report():
    """Analyze a custom report from command line input"""
    setup_logging()
    
    print("📝 Custom Report Analysis")
    print("-" * 30)
    
    # Get user input
    try:
        user_id = input("User ID: ")
        username = input("Username: ")
        platform = input("Platform (iOS/Android): ")
        os_version = input("OS Version: ")
        app_version = input("App Version: ")
        log_url = input("Log URL: ")
        env = input("Environment (prod/staging/dev): ")
        feedback = input("User Feedback: ")
        
        report_data = {
            "username": username,
            "user_id": user_id,
            "platform": platform,
            "os_version": os_version,
            "app_version": app_version,
            "log_url": log_url,
            "env": env,
            "feedback": feedback
        }
        
        # Initialize and run analyzer
        analyzer = BugAnalyzer(
            openai_api_key=Config.OPENAI_API_KEY,
            aws_region=Config.AWS_REGION,
            cloudwatch_log_group=Config.CLOUDWATCH_LOG_GROUP
        )
        
        result = analyzer.quick_analyze(report_data)
        print("\n" + result)
        
    except KeyboardInterrupt:
        print("\n👋 Analysis cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "custom":
        analyze_custom_report()
    else:
        exit_code = main()
        sys.exit(exit_code) 