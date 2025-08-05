#!/usr/bin/env python3
"""
Test script for webhook functionality
"""

import json
import time
from datetime import datetime
from typing import Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import requests


class WebhookTestServer(BaseHTTPRequestHandler):
    """Simple HTTP server to receive webhook calls"""
    
    received_webhooks = []
    
    def do_POST(self):
        """Handle POST requests"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
            WebhookTestServer.received_webhooks.append({
                'timestamp': datetime.utcnow().isoformat(),
                'payload': payload,
                'headers': dict(self.headers)
            })
            
            print(f"📡 Webhook received: {payload.get('event_type', 'unknown')}")
            print(f"   Analysis ID: {payload.get('analysis', {}).get('id', 'N/A')}")
            print(f"   Status: {payload.get('analysis', {}).get('status', 'N/A')}")
            print(f"   Payload: {json.dumps(payload, indent=2)}")
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            
        except Exception as e:
            print(f"❌ Error processing webhook: {e}")
            self.send_response(400)
            self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {
            "status": "ok",
            "received_webhooks": len(WebhookTestServer.received_webhooks),
            "last_webhook": WebhookTestServer.received_webhooks[-1] if WebhookTestServer.received_webhooks else None
        }
        self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def start_webhook_server(port: int = 8888) -> HTTPServer:
    """Start webhook test server"""
    server = HTTPServer(('localhost', port), WebhookTestServer)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"🚀 Webhook test server started on http://localhost:{port}")
    return server


def test_webhook_integration():
    """Test complete webhook integration"""
    print("🧪 Testing Bug Analysis Agent Webhook Integration")
    print("=" * 60)
    
    # Start webhook server
    webhook_server = start_webhook_server()
    webhook_url = "http://localhost:8888"
    
    try:
        # Test 1: Webhook connectivity test
        print("\n📡 Test 1: Testing webhook connectivity...")
        try:
            response = requests.post(
                "http://localhost:8000/webhook/test",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Webhook test: {result.get('status')} - {result.get('message')}")
            else:
                print(f"❌ Webhook test failed: {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError:
            print("❌ Could not connect to API server. Make sure it's running on port 8000")
            return
        except Exception as e:
            print(f"❌ Webhook test error: {e}")
        
        # Test 2: Check health endpoint includes webhook status
        print("\n🏥 Test 2: Checking health endpoint for webhook status...")
        try:
            response = requests.get("http://localhost:8000/health", timeout=10)
            if response.status_code == 200:
                health = response.json()
                webhook_status = health.get('components', {}).get('webhook', 'not found')
                print(f"✅ Webhook status in health check: {webhook_status}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Health check error: {e}")
        
        # Test 3: Analyze with webhook (if we have a sample analysis)
        print("\n🔍 Test 3: Running analysis to trigger webhook...")
        
        # Sample analysis request
        analysis_data = {
            "username": "webhook_test_user",
            "user_id": "webhook_test_123",
            "platform": "web",
            "os_version": "Chrome 120",
            "app_version": "1.0.0",
            "log_url": "https://example.com/sample.log",
            "env": "test",
            "feedback": "Testing webhook integration",
            "generate_csv": False
        }
        
        try:
            response = requests.post(
                "http://localhost:8000/analyze/sync",
                json=analysis_data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Analysis completed: {result.get('analysis_id')}")
                print(f"   Status: {result.get('status')}")
                
                # Wait a moment for webhook to arrive
                time.sleep(2)
                
                # Check if webhook was received
                if WebhookTestServer.received_webhooks:
                    webhook = WebhookTestServer.received_webhooks[-1]
                    print(f"✅ Webhook received successfully!")
                    print(f"   Event type: {webhook['payload'].get('event_type')}")
                    print(f"   Analysis status: {webhook['payload'].get('analysis', {}).get('status')}")
                else:
                    print("❌ No webhook received within timeout")
            else:
                print(f"❌ Analysis failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Analysis error: {e}")
        
        # Summary
        print(f"\n📊 Test Summary:")
        print(f"   Total webhooks received: {len(WebhookTestServer.received_webhooks)}")
        if WebhookTestServer.received_webhooks:
            print("   Received webhook events:")
            for i, webhook in enumerate(WebhookTestServer.received_webhooks, 1):
                event_type = webhook['payload'].get('event_type', 'unknown')
                print(f"     {i}. {event_type}")
        
    finally:
        webhook_server.shutdown()
        print("\n🛑 Webhook test server stopped")


if __name__ == "__main__":
    print("🔧 Bug Analysis Agent - Webhook Test Script")
    print("This script tests the webhook functionality by:")
    print("1. Starting a local webhook receiver")
    print("2. Testing webhook connectivity")
    print("3. Running an analysis to trigger webhooks")
    print("4. Showing received webhook data")
    print("\nMake sure to:")
    print("- Start the API server (python start_backend.py)")
    print("- Set WEBHOOK_ENABLED=true in your .env")
    print("- Set WEBHOOK_URL=http://localhost:8888 in your .env")
    print("\nStarting test in 3 seconds...")
    time.sleep(3)
    
    test_webhook_integration() 