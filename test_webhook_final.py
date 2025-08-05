#!/usr/bin/env python3
"""
Final test of Lark webhook integration
"""

import requests

def test_webhook_integration():
    """Test the complete webhook integration with Lark"""
    print("🧪 Final Webhook Integration Test")
    print("=" * 40)
    
    try:
        # Test 1: Webhook test endpoint
        print("1. Testing webhook connectivity...")
        response = requests.post("http://localhost:8000/webhook/test", timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Webhook test: {result.get('message')}")
        else:
            print(f"   ❌ Webhook test failed: {response.status_code}")
            return
        
        # Test 2: Analysis with webhook
        print("\n2. Running analysis to trigger Lark webhook...")
        analysis_data = {
            "username": "final_test_user",
            "user_id": "final_test_123",
            "platform": "web",
            "os_version": "Chrome 120", 
            "app_version": "1.0.0",
            "log_url": "https://httpbin.org/status/404",  # Will fail
            "env": "test",
            "feedback": "Final webhook integration test",
            "generate_csv": False
        }
        
        response = requests.post(
            "http://localhost:8000/analyze/sync",
            json=analysis_data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Analysis completed: {result.get('status')}")
            print(f"   📋 Analysis ID: {result.get('analysis_id')}")
            
            print(f"\n🎉 SUCCESS! Check your Lark channel for:")
            print(f"   1. 🧪 Webhook connectivity test message")
            print(f"   2. ❌ Bug Analysis Failed message with details")
            
        else:
            print(f"   ❌ Analysis failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        print("Make sure the backend server is running on localhost:8000")

if __name__ == "__main__":
    test_webhook_integration() 