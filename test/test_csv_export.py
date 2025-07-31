#!/usr/bin/env python3
"""
Demo script to test CSV export functionality
"""

import os
from bug_analysis_agent.analyzer import BugAnalyzer
from bug_analysis_agent.config import Config

def main():
    print("📊 CSV Export Demo - Frontend/Backend Log Correlation")
    print("=" * 60)
    
    # Sample report data
    sample_report = {
        "username": "@testuser",
        "user_id": "12345",
        "platform": "iOS",
        "os_version": "18.5",
        "app_version": "1.31.0",
        "log_url": "https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.31.0_prod_20250730T004620Z.log",
        "env": "prod",
        "feedback": "App keeps crashing when I try to load content"
    }
    
    try:
        # Initialize analyzer
        analyzer = BugAnalyzer(
            openai_api_key=Config.OPENAI_API_KEY,
            aws_region=Config.AWS_REGION,
            cloudwatch_log_group=Config.CLOUDWATCH_LOG_GROUP
        )
        
        print("🔍 Running analysis with CSV export...")
        
        # Run analysis (this will auto-generate CSV)
        result = analyzer.quick_analyze(sample_report, generate_csv=True)
        print(result)
        
        # Show CSV file contents preview
        logs_dir = "logs"
        if os.path.exists(logs_dir):
            csv_files = [f for f in os.listdir(logs_dir) if f.startswith('log_correlations_') and f.endswith('.csv')]
        else:
            csv_files = []
        
        if csv_files:
            latest_csv = max(csv_files, key=lambda f: os.path.getctime(os.path.join(logs_dir, f)))
            csv_path = os.path.join(logs_dir, latest_csv)
            print(f"\n📄 Generated CSV: {csv_path}")
            
            # Show first few lines
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(f"📋 CSV Preview ({len(lines)} total lines):")
                for i, line in enumerate(lines[:5]):  # Show first 5 lines
                    print(f"   {i+1}: {line.strip()}")
                
                if len(lines) > 5:
                    print(f"   ... and {len(lines) - 5} more lines")
        else:
            print("⚠️  No CSV files found in logs folder")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 