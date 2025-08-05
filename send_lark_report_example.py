#!/usr/bin/env python3
"""
Example script showing how to send a Lark report to the incoming webhook
"""

import requests
import json

def send_lark_report(log_url, user_id, username, environment, version, platform, os_version, feedback):
    """
    Send a log report to the Bug Analysis Agent via Lark webhook format
    
    Args:
        log_url: S3 URL or HTTP URL to the log file
        user_id: User identifier
        username: User's display name  
        environment: Environment (prod, stage, dev, etc.)
        version: App version
        platform: Platform (ios, android, web, etc.)
        os_version: Operating system version
        feedback: User's feedback/bug report text
    """
    
    # Format the content in the expected Lark markdown format
    content = f"""用户提交日志! 
下载地址: {log_url} 
环境: {environment}
版本号: {version}
上传用户: {user_id} @{username} 
 系统：{platform} 
系统版本：{os_version}

反馈内容: {feedback}
"""
    
    # Create the Lark interactive card payload
    payload = {
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
                        "content": content
                    }
                },
                {
                    "tag": "hr"
                }
            ]
        }
    }
    
    print(f"📤 Sending log report for user {user_id} to Bug Analysis Agent...")
    print(f"📄 Log URL: {log_url}")
    print(f"🐛 Issue: {feedback[:50]}...")
    
    try:
        response = requests.post(
            "http://localhost:8000/webhook/lark",  # Change to your server URL
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Parse the Lark response
            if result.get("msg_type") == "interactive":
                card = result.get("card", {})
                title = card.get("header", {}).get("title", {}).get("content", "")
                
                elements = card.get("elements", [])
                if elements and elements[0].get("text"):
                    content = elements[0]["text"].get("content", "")
                    
                if "成功" in title:
                    print("✅ Report submitted successfully!")
                    # Extract analysis ID from response
                    if "分析ID" in content:
                        import re
                        analysis_id_match = re.search(r'分析ID: `([^`]+)`', content)
                        if analysis_id_match:
                            analysis_id = analysis_id_match.group(1)
                            print(f"📋 Analysis ID: {analysis_id}")
                            print(f"⏰ Status: Analysis is running in background")
                            print(f"📡 Results will be sent to your webhook when complete")
                else:
                    print("❌ Report submission failed")
                    print(f"📄 Response: {content}")
            else:
                print(f"📄 Unexpected response format: {result}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"📄 Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Bug Analysis Agent. Is the server running?")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("📋 Lark Report Sender Example")
    print("=" * 40)
    
    # Example usage
    send_lark_report(
        log_url="https://sekai-app-log.s3.us-east-1.amazonaws.com/user123_20240804.log",
        user_id="user123",
        username="testuser",
        environment="prod",
        version="2.1.0", 
        platform="ios",
        os_version="iOS 17.0",
        feedback="App crashes when I try to upload photos. The error happens right after selecting the image from gallery."
    )
    
    print("\n💡 This is how your Lark bot would send reports to the analysis system!")
    print("📱 The analysis will run automatically and send results to your configured webhook.") 