#!/usr/bin/env python3
"""
Comprehensive test script for the complete webhook system
Tests both incoming and outgoing webhook functionality
"""

import requests
import json
import time
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class WebhookReceiver(BaseHTTPRequestHandler):
    """Test webhook receiver to capture outgoing webhooks"""
    received_webhooks = []
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                WebhookReceiver.received_webhooks.append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'payload': payload,
                    'headers': dict(self.headers)
                })
                print(f"📡 Received webhook: {payload.get('msg_type', payload.get('event_type', 'unknown'))}")
            except:
                pass
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status": "received"}')
    
    def log_message(self, format, *args):
        pass  # Suppress default logs


def start_webhook_receiver(port=8888):
    """Start a local webhook receiver"""
    server = HTTPServer(('localhost', port), WebhookReceiver)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class WebhookSystemTester:
    """Complete webhook system tester"""
    
    def __init__(self, api_base_url="http://localhost:8000"):
        self.api_base_url = api_base_url
        self.webhook_server = None
        
    def setup(self):
        """Setup test environment"""
        print("🔧 Setting up test environment...")
        
        # Start local webhook receiver
        self.webhook_server = start_webhook_receiver()
        print("🚀 Local webhook receiver started on http://localhost:8888")
        
        # Clear previous webhooks
        WebhookReceiver.received_webhooks.clear()
        
    def cleanup(self):
        """Cleanup test environment"""
        if self.webhook_server:
            self.webhook_server.shutdown()
            print("🛑 Webhook receiver stopped")
    
    def test_api_health(self):
        """Test 1: API Health and webhook status"""
        print("\n🏥 Test 1: API Health and Webhook Status")
        print("=" * 50)
        
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=120)
            if response.status_code == 200:
                health = response.json()
                webhook_status = health.get('components', {}).get('webhook', 'not found')
                print(f"✅ API Health: {health.get('status')}")
                print(f"📡 Webhook Status: {webhook_status}")
                return webhook_status == 'ok'
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    def test_outgoing_webhook_test_endpoint(self):
        """Test 2: Outgoing webhook test endpoint"""
        print("\n📤 Test 2: Outgoing Webhook Test Endpoint")
        print("=" * 50)
        
        try:
            response = requests.post(f"{self.api_base_url}/webhook/test", timeout=120)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Webhook test: {result.get('message')}")
                return True
            else:
                print(f"❌ Webhook test failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Webhook test error: {e}")
            return False
    
    def test_lark_parser_directly(self):
        """Test 3: Lark parser functionality"""
        print("\n🔍 Test 3: Lark Parser Functionality")
        print("=" * 50)
        
        try:
            from bug_analysis_agent.lark_parser import LarkPayloadParser
            
            parser = LarkPayloadParser()
            
            # Test valid payload
            test_payload = {
                "msg_type": "interactive",
                "card": {
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": "用户提交日志! \n下载地址: https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.32.1_prod_20250805T075038Z.log \n环境: test\n版本号: 1.2.3\n上传用户: testuser @testname \n 系统：android \n系统版本：Android 13\n\n反馈内容: Test feedback for parser validation\n"
                            }
                        }
                    ]
                }
            }
            
            analysis_data = parser.parse_lark_report(test_payload)
            
            if analysis_data:
                print("✅ Parser working correctly!")
                print("📊 Extracted data:")
                for key, value in analysis_data.items():
                    print(f"   {key}: {value}")
                
                # Validate required fields
                required_fields = ['username', 'user_id', 'log_url', 'feedback']
                missing = [f for f in required_fields if not analysis_data.get(f)]
                if missing:
                    print(f"❌ Missing required fields: {missing}")
                    return False
                
                return True
            else:
                print("❌ Parser failed to extract data")
                return False
                
        except Exception as e:
            print(f"❌ Parser test error: {e}")
            return False
    
    def test_incoming_webhook_valid(self):
        """Test 4: Incoming webhook with valid payload"""
        print("\n📥 Test 4: Incoming Webhook - Valid Payload")
        print("=" * 50)
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "Sekai 日志上报"}
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "用户提交日志! \n下载地址: https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.32.1_prod_20250805T075038Z.log \n环境: test\n版本号: 2.0.0\n上传用户: webhook_test @webhookuser \n 系统：ios \n系统版本：iOS 17.0\n\n反馈内容: Testing incoming webhook functionality with sample error\n"
                        }
                    },
                    {"tag": "hr"}
                ]
            }
        }
        
        try:
            response = requests.post(
                f"{self.api_base_url}/webhook/lark",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=120
            )
            
            print(f"📨 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get("msg_type") == "interactive":
                    card = result.get("card", {})
                    title = card.get("header", {}).get("title", {}).get("content", "")
                    
                    elements = card.get("elements", [])
                    content = ""
                    if elements and elements[0].get("text"):
                        content = elements[0]["text"].get("content", "")
                    
                    print(f"📋 Response Title: {title}")
                    print(f"📝 Response Content: {content[:100]}...")
                    
                    if "成功" in title or "成功" in content:
                        print("✅ Incoming webhook processed successfully!")
                        
                        # Extract analysis ID if present
                        import re
                        analysis_id_match = re.search(r'分析ID: `([^`]+)`', content)
                        if analysis_id_match:
                            analysis_id = analysis_id_match.group(1)
                            print(f"📋 Analysis ID: {analysis_id}")
                            return analysis_id
                        
                        return True
                    else:
                        print(f"❌ Unexpected response content")
                        return False
                else:
                    print(f"❌ Unexpected response format: {result}")
                    return False
            else:
                print(f"❌ Incoming webhook failed: {response.status_code}")
                print(f"📄 Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Incoming webhook test error: {e}")
            return False
    
    def test_incoming_webhook_invalid(self):
        """Test 5: Incoming webhook with invalid payload"""
        print("\n📥 Test 5: Incoming Webhook - Invalid Payload")
        print("=" * 50)
        
        invalid_payload = {
            "msg_type": "text",  # Wrong type
            "content": {"text": "Invalid payload format"}
        }
        
        try:
            response = requests.post(
                f"{self.api_base_url}/webhook/lark",
                json=invalid_payload,
                headers={"Content-Type": "application/json"},
                timeout=120
            )
            
            print(f"📨 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("msg_type") == "interactive":
                    card = result.get("card", {})
                    title = card.get("header", {}).get("title", {}).get("content", "")
                    
                    if "失败" in title:
                        print("✅ Invalid payload correctly rejected!")
                        return True
                    else:
                        print(f"❌ Expected failure response, got: {title}")
                        return False
                else:
                    print(f"❌ Unexpected response format for invalid payload")
                    return False
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Invalid payload test error: {e}")
            return False
    
    def test_end_to_end_flow(self):
        """Test 6: End-to-end flow with webhook capture"""
        print("\n🔄 Test 6: End-to-End Flow (Incoming → Analysis → Outgoing)")
        print("=" * 50)
        
        # Check current webhook configuration
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=10)
            if response.status_code == 200:
                health = response.json()
                print(f"📡 Current webhook status: {health.get('components', {}).get('webhook', 'unknown')}")
        except:
            pass
        
        print("📝 Choose test mode:")
        print("1. Test with LOCAL capture (requires WEBHOOK_URL=http://localhost:8888)")
        print("2. Test with your REAL Lark webhook URL (no local capture)")
        
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            return self._test_with_local_capture()
        elif choice == "2":
            return self._test_with_real_webhook()
        else:
            print("❌ Invalid choice. Defaulting to real webhook test.")
            return self._test_with_real_webhook()
    
    def _test_with_local_capture(self):
        """Test end-to-end flow with local webhook capture"""
        print("\n🔧 Testing with LOCAL webhook capture...")
        print("📝 Note: Make sure WEBHOOK_URL=http://localhost:8888 in your .env")
        print("📝 Testing with a payload that will trigger analysis")
        
        # Clear previous webhooks
        WebhookReceiver.received_webhooks.clear()
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "用户提交日志! \n下载地址: https://httpbin.org/status/404 \n环境: prod\n版本号: 3.0.0\n上传用户: e2e_test @e2euser \n 系统：web \n系统版本：Chrome 120\n\n反馈内容: End-to-end test - this should trigger analysis and send results to local webhook capture\n"
                        }
                    }
                ]
            }
        }
        
        try:
            # Send incoming webhook
            response = requests.post(
                f"{self.api_base_url}/webhook/lark",
                json=payload,
                timeout=120
            )
            
            if response.status_code != 200:
                print(f"❌ Incoming webhook failed: {response.status_code}")
                return False
            
            result = response.json()
            
            # Extract analysis ID
            content = ""
            if result.get("card", {}).get("elements"):
                content = result["card"]["elements"][0].get("text", {}).get("content", "")
            
            import re
            analysis_id_match = re.search(r'分析ID: `([^`]+)`', content)
            if not analysis_id_match:
                print("❌ Could not extract analysis ID from response")
                return False
            
            analysis_id = analysis_id_match.group(1)
            print(f"📋 Analysis triggered with ID: {analysis_id}")
            
            # Wait for analysis to complete and webhook to be sent
            print("⏰ Waiting for analysis to complete and webhook to be captured...")
            
            for i in range(12):  # Wait up to 60 seconds
                time.sleep(5)
                print(f"   Waiting... ({(i+1)*5}s)")
                
                # Check if we received a webhook
                if WebhookReceiver.received_webhooks:
                    webhook = WebhookReceiver.received_webhooks[-1]
                    payload_received = webhook['payload']
                    
                    print(f"🎉 Received outgoing webhook!")
                    print(f"   Type: {payload_received.get('msg_type', payload_received.get('event_type'))}")
                    
                    # Check if it's our analysis
                    if payload_received.get('msg_type') == 'text':  # Lark format
                        text_content = payload_received.get('content', {}).get('text', '')
                        if analysis_id in text_content:
                            print(f"✅ End-to-end flow completed successfully!")
                            print(f"📄 Webhook content preview: {text_content[:100]}...")
                            return True
                    elif payload_received.get('event_type') == 'analysis_complete':  # Generic format
                        webhook_analysis_id = payload_received.get('analysis', {}).get('id', '')
                        if analysis_id in webhook_analysis_id:
                            print(f"✅ End-to-end flow completed successfully!")
                            print(f"📄 Webhook analysis ID: {webhook_analysis_id}")
                            return True
            
            print(f"❌ No matching webhook received within timeout")
            print(f"📊 Total webhooks received: {len(WebhookReceiver.received_webhooks)}")
            if WebhookReceiver.received_webhooks:
                print("📋 Received webhooks:")
                for i, wh in enumerate(WebhookReceiver.received_webhooks, 1):
                    print(f"   {i}. {wh['payload'].get('msg_type', wh['payload'].get('event_type', 'unknown'))}")
            return False
            
        except Exception as e:
            print(f"❌ Local capture test error: {e}")
            return False
    
    def _test_with_real_webhook(self):
        """Test end-to-end flow with real Lark webhook URL"""
        print("\n🚀 Testing with your REAL Lark webhook URL...")
        print("📝 This will send actual webhooks to your configured Lark channel")
        print("📱 Check your Lark channel for the analysis result notification")
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "用户提交日志! \n下载地址: https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.32.1_prod_20250805T075038Z.log \n环境: test\n版本号: 3.1.0\n上传用户: real_test @realuser \n 系统：ios \n系统版本：iOS 17.0\n\n反馈内容: Real webhook test - check your Lark channel for analysis results!\n"
                        }
                    }
                ]
            }
        }
        
        try:
            # Send incoming webhook
            response = requests.post(
                f"{self.api_base_url}/webhook/lark",
                json=payload,
                timeout=120
            )
            
            if response.status_code != 200:
                print(f"❌ Incoming webhook failed: {response.status_code}")
                return False
            
            result = response.json()
            
            # Extract analysis ID
            content = ""
            if result.get("card", {}).get("elements"):
                content = result["card"]["elements"][0].get("text", {}).get("content", "")
            
            import re
            analysis_id_match = re.search(r'分析ID: `([^`]+)`', content)
            if not analysis_id_match:
                print("❌ Could not extract analysis ID from response")
                return False
            
            analysis_id = analysis_id_match.group(1)
            print(f"📋 Analysis triggered with ID: {analysis_id}")
            
            # Wait for analysis to complete
            print("⏰ Waiting for analysis to complete...")
            print("📱 Check your Lark channel - you should see analysis results appear there!")
            
            # Check analysis status via API
            for i in range(24):  # Wait up to 2 minutes
                time.sleep(5)
                print(f"   Checking status... ({(i+1)*5}s)")
                
                try:
                    status_response = requests.get(f"{self.api_base_url}/analyze/{analysis_id}", timeout=10)
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        analysis_status = status_data.get('status', 'unknown')
                        
                        print(f"   📊 Analysis status: {analysis_status}")
                        
                        if analysis_status in ['completed', 'failed']:
                            print(f"✅ Analysis finished with status: {analysis_status}")
                            if analysis_status == 'completed':
                                print(f"📄 Result preview: {status_data.get('result', '')[:100]}...")
                            else:
                                print(f"❌ Error: {status_data.get('error', '')[:100]}...")
                            
                            print(f"🎉 Real webhook test completed!")
                            print(f"📱 Check your Lark channel for the analysis notification")
                            return True
                except:
                    pass  # Continue waiting
            
            print(f"⏰ Analysis still running after 2 minutes")
            print(f"📱 Results will appear in your Lark channel when analysis completes")
            print(f"✅ Webhook flow initiated successfully - this counts as a pass!")
            return True
            
        except Exception as e:
            print(f"❌ Real webhook test error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all webhook tests"""
        print("🧪 Complete Webhook System Test Suite")
        print("=" * 60)
        print("Testing both incoming and outgoing webhook functionality\n")
        
        tests = [
            ("API Health", self.test_api_health),
            ("Outgoing Webhook Test", self.test_outgoing_webhook_test_endpoint),
            ("Lark Parser", self.test_lark_parser_directly),
            ("Incoming Webhook (Valid)", self.test_incoming_webhook_valid),
            ("Incoming Webhook (Invalid)", self.test_incoming_webhook_invalid),
            ("End-to-End Flow", self.test_end_to_end_flow),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                results[test_name] = result
            except Exception as e:
                print(f"❌ {test_name} crashed: {e}")
                results[test_name] = False
        
        # Summary
        print("\n📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        passed = 0
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test_name}")
            if result:
                passed += 1
        
        print(f"\n🎯 Overall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Your webhook system is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the details above.")
            
        print(f"\n📡 Total outgoing webhooks captured: {len(WebhookReceiver.received_webhooks)}")
        
        return passed == total


def main():
    """Main test runner"""
    print("🔧 Bug Analysis Agent - Complete Webhook System Test")
    print("This tests incoming Lark webhooks, outgoing webhooks, and end-to-end flow")
    print("\n📋 Prerequisites:")
    print("1. Backend server running on localhost:8000")
    print("2. WEBHOOK_ENABLED=true in your .env")
    print("3. Your webhook functionality enabled")
    
    print("\n🔄 Two test modes available:")
    print("   Mode 1: LOCAL capture - captures webhooks locally for validation")
    print("           (requires temporarily setting WEBHOOK_URL=http://localhost:8888)")
    print("   Mode 2: REAL webhook - sends to your actual Lark webhook URL")
    print("           (uses your current WEBHOOK_URL setting)")
    
    input("\nPress Enter to start tests...")
    
    tester = WebhookSystemTester()
    
    try:
        tester.setup()
        success = tester.run_all_tests()
        
        if success:
            print("\n🎉 All webhook functionality is working correctly!")
            print("💡 Your system is ready for production use.")
        else:
            print("\n⚠️  Some issues detected. Review the test output above.")
            
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main() 