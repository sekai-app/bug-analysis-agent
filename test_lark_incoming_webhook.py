#!/usr/bin/env python3
"""
Test script for incoming Lark webhook functionality
"""

import requests
import json

def test_lark_incoming_webhook():
    """Test the incoming Lark webhook endpoint"""
    print("🧪 Testing Lark Incoming Webhook")
    print("=" * 50)
    
    # Sample Lark interactive card payload (based on user's format)
    sample_payload = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text", 
                    "content": "Sekai 日志上报"
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md", 
                        "content": "用户提交日志! \n下载地址: https://sekai-app-log.s3.us-east-1.amazonaws.com/test_filename.log \n环境: stage\n版本号: 1.0.0\n上传用户: user123 @testuser \n 系统：ios \n系统版本：iOS 16.0\n\n反馈内容: App crashes when trying to login, shows error message about network connection\n"
                    }
                },
                {
                    "tag": "hr"
                }
            ]
        }
    }
    
    print("📤 Sending sample Lark payload to webhook endpoint...")
    print(f"📄 Payload preview:")
    print(f"   Log URL: https://sekai-app-log.s3.us-east-1.amazonaws.com/test_filename.log")
    print(f"   User: user123 @testuser")
    print(f"   Environment: stage")
    print(f"   Platform: iOS 16.0")
    print(f"   Feedback: App crashes when trying to login...")
    
    try:
        response = requests.post(
            "http://localhost:8000/webhook/lark",
            json=sample_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"\n📨 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Webhook processed successfully!")
            
            # Check if it's a Lark card response
            if result.get("msg_type") == "interactive":
                card = result.get("card", {})
                title = card.get("header", {}).get("title", {}).get("content", "No title")
                elements = card.get("elements", [])
                
                print(f"📋 Response Card Title: {title}")
                
                if elements and elements[0].get("text"):
                    content = elements[0]["text"].get("content", "No content")
                    print(f"📝 Response Content: {content}")
                
                # Look for analysis ID in content
                if "分析ID" in content:
                    print(f"🎉 Analysis successfully started from Lark webhook!")
                    print(f"💡 The analysis will run in the background and send results to your webhook when complete.")
            else:
                print(f"📄 Response: {result}")
        else:
            print(f"❌ Webhook failed: {response.status_code}")
            print(f"📄 Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API server. Make sure it's running on localhost:8000")
    except Exception as e:
        print(f"❌ Test error: {e}")

def test_invalid_payload():
    """Test with invalid payload to check error handling"""
    print("\n🧪 Testing Invalid Payload Handling")
    print("=" * 50)
    
    invalid_payload = {
        "msg_type": "text",  # Wrong type
        "content": {
            "text": "Invalid payload format"
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/webhook/lark",
            json=invalid_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"📨 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("msg_type") == "interactive":
                card = result.get("card", {})
                title = card.get("header", {}).get("title", {}).get("content", "No title")
                print(f"📋 Error Response Title: {title}")
                
                elements = card.get("elements", [])
                if elements and elements[0].get("text"):
                    content = elements[0]["text"].get("content", "No content")
                    print(f"📝 Error Content: {content}")
                    
                if "失败" in title or "错误" in content:
                    print(f"✅ Error handling working correctly!")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Test error: {e}")

def test_parser_directly():
    """Test the Lark parser directly"""
    print("\n🧪 Testing Lark Parser Directly")
    print("=" * 50)
    
    try:
        # Import and test parser
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from bug_analysis_agent.lark_parser import LarkPayloadParser
        
        parser = LarkPayloadParser()
        
        sample_payload = {
            "msg_type": "interactive",
            "card": {
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md", 
                            "content": "用户提交日志! \n下载地址: https://sekai-app-log.s3.us-east-1.amazonaws.com/test.log \n环境: prod\n版本号: 2.0.0\n上传用户: user456 @devuser \n 系统：android \n系统版本：Android 12\n\n反馈内容: Button not responding on main screen\n"
                        }
                    }
                ]
            }
        }
        
        analysis_data = parser.parse_lark_report(sample_payload)
        
        if analysis_data:
            print("✅ Parser working correctly!")
            print("📊 Extracted data:")
            for key, value in analysis_data.items():
                print(f"   {key}: {value}")
        else:
            print("❌ Parser failed to extract data")
            
    except Exception as e:
        print(f"❌ Parser test error: {e}")

if __name__ == "__main__":
    print("🔧 Lark Incoming Webhook Test Suite")
    print("This tests the new endpoint that receives Lark reports and triggers analysis")
    print("=" * 70)
    
    # Test 1: Valid payload
    test_lark_incoming_webhook()
    
    # Test 2: Invalid payload
    test_invalid_payload()
    
    # Test 3: Parser directly
    test_parser_directly()
    
    print("\n🏁 Test Suite Complete!")
    print("💡 If the tests pass, your Lark bot can now send reports to:")
    print("   POST http://localhost:8000/webhook/lark")
    print("📱 And analysis results will be sent back to your configured webhook URL!") 