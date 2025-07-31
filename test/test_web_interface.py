#!/usr/bin/env python3
"""
Test script for the Bug Analysis Agent Web Interface
"""

import requests
import json
import time

API_BASE_URL = "http://localhost:8000"

def test_api_health():
    """Test API health endpoint"""
    print("🧪 Testing API Health...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API is healthy!")
            health_data = response.json()
            print(f"   Status: {health_data['status']}")
            print("   Components:")
            for component, status in health_data['components'].items():
                emoji = "✅" if status == "ok" else "⚠️"
                print(f"     {emoji} {component}: {status}")
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to API: {e}")
        return False
    
    return True

def test_sync_analysis():
    """Test synchronous analysis with CSV generation"""
    print("\n🔍 Testing Synchronous Analysis...")
    
    # Sample data
    analysis_data = {
        "username": "@testuser",
        "user_id": "12345",
        "platform": "iOS",
        "os_version": "18.5",
        "app_version": "1.31.0",
        "log_url": "https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.31.0_prod_20250730T004620Z.log",
        "env": "prod",
        "feedback": "Test feedback for web interface",
        "context_lines": 10,
        "request_id_context_lines": 5,
        "time_window_minutes": 2,
        "generate_csv": True
    }
    
    try:
        print("   Submitting analysis request...")
        response = requests.post(f"{API_BASE_URL}/analyze/sync", json=analysis_data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Analysis completed!")
            print(f"   Analysis ID: {result['analysis_id']}")
            print(f"   Status: {result['status']}")
            
            if result.get('csv_file'):
                print(f"   CSV File: {result['csv_file']}")
                
                # Test CSV download
                csv_filename = result['csv_file'].split('/')[-1]  # Get filename from path
                csv_url = f"{API_BASE_URL}/download-csv/{csv_filename}"
                print(f"   Testing CSV download: {csv_url}")
                
                csv_response = requests.get(csv_url)
                if csv_response.status_code == 200:
                    print("✅ CSV download successful!")
                    print(f"   CSV size: {len(csv_response.content)} bytes")
                else:
                    print(f"❌ CSV download failed: {csv_response.status_code}")
            else:
                print("   No CSV file generated")
                
            if result.get('result'):
                print("\n📊 Analysis Summary (first 200 chars):")
                print(result['result'][:200] + "..." if len(result['result']) > 200 else result['result'])
                
        else:
            print(f"❌ Analysis failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error during analysis: {e}")

def test_async_analysis():
    """Test asynchronous analysis"""
    print("\n🚀 Testing Asynchronous Analysis...")
    
    analysis_data = {
        "username": "@asyncuser",
        "user_id": "67890",
        "platform": "Android",
        "os_version": "14.0",
        "app_version": "1.31.0", 
        "log_url": "https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.31.0_prod_20250730T004620Z.log",
        "env": "prod",
        "feedback": "Async test feedback",
        "generate_csv": True
    }
    
    try:
        # Submit async analysis
        print("   Submitting async analysis...")
        response = requests.post(f"{API_BASE_URL}/analyze", json=analysis_data)
        
        if response.status_code == 200:
            result = response.json()
            analysis_id = result['analysis_id']
            print(f"✅ Analysis submitted! ID: {analysis_id}")
            
            # Check status periodically
            print("   Checking status...")
            for i in range(10):  # Check for up to 10 times
                time.sleep(2)
                status_response = requests.get(f"{API_BASE_URL}/analyze/{analysis_id}")
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"   Status: {status_data['status']}")
                    
                    if status_data['status'] == 'completed':
                        print("✅ Async analysis completed!")
                        if status_data.get('csv_file'):
                            print(f"   CSV File: {status_data['csv_file']}")
                        break
                    elif status_data['status'] == 'failed':
                        print(f"❌ Analysis failed: {status_data.get('error', 'Unknown error')}")
                        break
                else:
                    print(f"❌ Status check failed: {status_response.status_code}")
                    break
            else:
                print("⏰ Analysis still running after timeout")
                
        else:
            print(f"❌ Failed to submit async analysis: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error during async analysis: {e}")

def main():
    """Main test function"""
    print("🔍 Bug Analysis Agent - Web Interface Test")
    print("=" * 50)
    
    # Check if API is running
    if not test_api_health():
        print("\n❌ API is not available. Please start the backend server:")
        print("   python start_backend.py")
        return
    
    # Test synchronous analysis
    test_sync_analysis()
    
    # Test asynchronous analysis
    test_async_analysis()
    
    print("\n" + "=" * 50)
    print("🎉 Web interface testing completed!")
    print("\n📝 To test the frontend:")
    print("   1. Run: python start_frontend.py")
    print("   2. Open: http://localhost:8501")
    print("   3. Submit a bug report and download the CSV!")

if __name__ == "__main__":
    main() 