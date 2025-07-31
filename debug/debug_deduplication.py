#!/usr/bin/env python3
"""
Debug script to check CSV deduplication behavior
"""

import os
import csv
import pandas as pd
from collections import Counter

def debug_csv_deduplication():
    print("🔍 CSV Deduplication Debug")
    print("=" * 40)
    
    # Find CSV files in logs directory
    logs_dir = "logs"
    if os.path.exists(logs_dir):
        csv_files = [f for f in os.listdir(logs_dir) if f.startswith('log_correlations_') and f.endswith('.csv')]
    else:
        print("⚠️ Logs directory doesn't exist")
        return
    
    if not csv_files:
        print("❌ No CSV files found in logs folder")
        return
    
    print(f"📂 Found {len(csv_files)} CSV files in logs folder:")
    for f in csv_files:
        print(f"   • {f}")
    
    # Use the latest CSV file
    latest_csv = max(csv_files, key=lambda f: os.path.getctime(os.path.join(logs_dir, f)))
    csv_path = os.path.join(logs_dir, latest_csv)
    print(f"\n🎯 Analyzing: {csv_path}")
    
    try:
        # Read CSV
        df = pd.read_csv(csv_path)
        
        print(f"\n📊 CSV Statistics:")
        print(f"   Total rows: {len(df)}")
        print(f"   Columns: {len(df.columns)}")
        
        # Check for backend message duplicates
        backend_messages = df['backend_message'].dropna()
        message_counts = Counter(backend_messages)
        
        print(f"\n🔄 Backend Message Analysis:")
        print(f"   Unique backend messages: {len(message_counts)}")
        print(f"   Total backend message instances: {len(backend_messages)}")
        
        # Show duplicates
        duplicates = {msg: count for msg, count in message_counts.items() if count > 1}
        if duplicates:
            print(f"   ⚠️ Duplicated messages: {len(duplicates)}")
            print("\n🚨 Top duplicated backend messages:")
            for msg, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"      {count}x: {msg[:100]}...")
        else:
            print("   ✅ No duplicate backend messages found")
        
        # Correlation method breakdown
        print(f"\n🔗 Correlation Methods:")
        correlation_counts = df['correlation_method'].value_counts()
        for method, count in correlation_counts.items():
            print(f"   {method}: {count}")
        
        # Frontend error breakdown
        frontend_errors = df['frontend_line_number'].value_counts()
        print(f"\n📱 Frontend Error Distribution:")
        print(f"   Unique frontend errors: {len(frontend_errors)}")
        print(f"   Max correlations per error: {frontend_errors.max()}")
        print(f"   Avg correlations per error: {frontend_errors.mean():.1f}")
        
        # Show errors with most correlations
        print(f"\n🔥 Frontend errors with most backend correlations:")
        for line_num, count in frontend_errors.head().items():
            print(f"   Line {line_num}: {count} correlations")
        
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")

def compare_csv_files():
    """Compare multiple CSV files to check consistency"""
    logs_dir = "logs"
    if os.path.exists(logs_dir):
        csv_files = [f for f in os.listdir(logs_dir) if f.startswith('log_correlations_') and f.endswith('.csv')]
    else:
        print("⚠️ Logs directory doesn't exist")
        return
    
    if len(csv_files) < 2:
        print("Need at least 2 CSV files to compare")
        return
    
    print(f"\n🔄 Comparing {len(csv_files)} CSV files...")
    
    for i, csv_file in enumerate(csv_files[:3]):  # Compare first 3 files
        csv_path = os.path.join(logs_dir, csv_file)
        try:
            df = pd.read_csv(csv_path)
            backend_messages = df['backend_message'].dropna()
            unique_messages = len(set(backend_messages))
            total_messages = len(backend_messages)
            
            print(f"   File {i+1} ({csv_file}):")
            print(f"      Total: {total_messages}, Unique: {unique_messages}, Duplication: {total_messages - unique_messages}")
            
        except Exception as e:
            print(f"      Error reading {csv_file}: {e}")

if __name__ == "__main__":
    debug_csv_deduplication()
    compare_csv_files() 