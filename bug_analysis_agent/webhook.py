"""
Webhook module for sending analysis results to external endpoints
"""

import logging
import time
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from .config import Config

logger = logging.getLogger(__name__)


class WebhookSender:
    """Handles sending analysis results to webhook endpoints"""
    
    def __init__(self, webhook_url: Optional[str] = None, timeout: int = None, retries: int = None):
        """
        Initialize webhook sender
        
        Args:
            webhook_url: Override webhook URL from config
            timeout: Override timeout from config
            retries: Override retry count from config
        """
        self.webhook_url = webhook_url or Config.WEBHOOK_URL
        self.timeout = timeout or Config.WEBHOOK_TIMEOUT
        self.retries = retries or Config.WEBHOOK_RETRIES
        self.enabled = bool(self.webhook_url and Config.WEBHOOK_ENABLED)
        
        # Detect webhook type
        self.is_lark_webhook = self._is_lark_webhook(self.webhook_url)
        
        if self.enabled:
            webhook_type = "Lark" if self.is_lark_webhook else "Generic"
            logger.info(f"Webhook sender initialized for {webhook_type} URL: {self.webhook_url}")
        else:
            logger.info("Webhook sender disabled (no URL configured or disabled in config)")
    
    def _is_lark_webhook(self, url: Optional[str]) -> bool:
        """Check if the webhook URL is a Lark webhook"""
        if not url:
            return False
        return "larksuite.com" in url or "feishu.cn" in url
    
    def send_analysis_complete(
        self, 
        analysis_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
        csv_file: Optional[str] = None,
        user_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        original_content: Optional[str] = None
    ) -> bool:
        """
        Send analysis completion notification to webhook
        
        Args:
            analysis_id: Unique analysis identifier
            status: Analysis status (completed, failed, etc.)
            result: Analysis result text (if completed)
            error: Error message (if failed)
            csv_file: Path to generated CSV file (if any)
            user_id: User ID from original request
            created_at: Analysis creation timestamp
            completed_at: Analysis completion timestamp
            metadata: Additional metadata to include
            original_content: Original content from Lark submission (for Lark webhooks)
            
        Returns:
            True if webhook sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Webhook not enabled, skipping send")
            return True  # Return True to not break the flow
        
        try:
            if self.is_lark_webhook:
                payload = self._build_lark_payload(
                    analysis_id=analysis_id,
                    status=status,
                    result=result,
                    error=error,
                    csv_file=csv_file,
                    user_id=user_id,
                    created_at=created_at,
                    completed_at=completed_at,
                    metadata=metadata,
                    original_content=original_content
                )
            else:
                payload = self._build_generic_payload(
                    analysis_id=analysis_id,
                    status=status,
                    result=result,
                    error=error,
                    csv_file=csv_file,
                    user_id=user_id,
                    created_at=created_at,
                    completed_at=completed_at,
                    metadata=metadata,
                    original_content=original_content
                )
            
            success = self._send_with_retry(payload)
            
            if success:
                logger.info(f"Webhook notification sent successfully for analysis {analysis_id}")
            else:
                logger.error(f"Failed to send webhook notification for analysis {analysis_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending webhook notification for analysis {analysis_id}: {e}")
            return False
    
    def _build_lark_payload(
        self,
        analysis_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
        csv_file: Optional[str] = None,
        user_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        original_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build Lark-specific webhook payload
        
        Returns:
            Dictionary containing Lark webhook payload
        """
        message_lines = []
        
        # Start with original content if available (for Lark webhook reports)
        if original_content:
            message_lines.extend([
                original_content,
                "",
                "=" * 40,
                ""
            ])
        
        # Add analysis results section
        status_text = "完成" if status == "completed" else "失败"
        message_lines.extend([
            f"用户日志 分析{status_text}!",
            "",
            f"分析ID: {analysis_id}",
            f"完成时间: {completed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if completed_at else 'N/A'}",
            ""
        ])
        
        if status == "completed" and result:
            # Send complete analysis results without truncation
            message_lines.append(f"分析结果:\n{result}")
            
            if csv_file:
                message_lines.append(f"\nCSV报告: {csv_file}")
        
        elif status == "failed" and error:
            # Send complete error message without truncation
            message_lines.append(f"错误信息:\n{error}")
        
        message_text = "\n".join(message_lines)
        
        return {
            "msg_type": "text",
            "content": {
                "text": message_text
            }
        }
    
    def _build_generic_payload(
        self,
        analysis_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
        csv_file: Optional[str] = None,
        user_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        original_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build generic webhook payload (original format)
        
        Returns:
            Dictionary containing generic webhook payload
        """
        payload = {
            "event_type": "analysis_complete",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "analysis": {
                "id": analysis_id,
                "status": status,
                "user_id": user_id,
                "created_at": created_at.isoformat() + "Z" if created_at else None,
                "completed_at": completed_at.isoformat() + "Z" if completed_at else None,
            }
        }
        
        # Add result data if analysis completed successfully
        if status == "completed" and result:
            payload["analysis"]["result"] = result
            payload["analysis"]["csv_file"] = csv_file
        
        # Add error data if analysis failed
        if status == "failed" and error:
            payload["analysis"]["error"] = error
        
        # Add any additional metadata
        if metadata:
            payload["analysis"]["metadata"] = metadata
        
        return payload
    
    def _send_with_retry(self, payload: Dict[str, Any]) -> bool:
        """
        Send webhook with retry logic
        
        Args:
            payload: Webhook payload to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Bug-Analysis-Agent/1.0"
        }
        
        # Add event type header for non-Lark webhooks
        if not self.is_lark_webhook:
            headers["X-Event-Type"] = "analysis_complete"
        
        for attempt in range(self.retries + 1):
            try:
                logger.debug(f"Sending webhook (attempt {attempt + 1}/{self.retries + 1})")
                
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                
                # Check for success
                if 200 <= response.status_code < 300:
                    # For Lark webhooks, also check the response content
                    if self.is_lark_webhook:
                        try:
                            response_data = response.json()
                            if response_data.get("code") == 0:
                                logger.debug(f"Lark webhook sent successfully")
                                return True
                            else:
                                logger.warning(f"Lark webhook error: {response_data}")
                        except:
                            logger.warning(f"Lark webhook response not JSON: {response.text}")
                    else:
                        logger.debug(f"Webhook sent successfully (status: {response.status_code})")
                        return True
                else:
                    logger.warning(f"Webhook returned status {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Webhook timeout on attempt {attempt + 1}")
            except requests.exceptions.ConnectionError:
                logger.warning(f"Webhook connection error on attempt {attempt + 1}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Webhook request error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending webhook on attempt {attempt + 1}: {e}")
            
            # Wait before retry (exponential backoff)
            if attempt < self.retries:
                wait_time = 2 ** attempt  # 1s, 2s, 4s, 8s...
                logger.debug(f"Waiting {wait_time}s before retry")
                time.sleep(wait_time)
        
        return False
    
    def test_webhook(self) -> bool:
        """
        Test webhook connectivity with a simple ping
        
        Returns:
            True if webhook responds successfully, False otherwise
        """
        if not self.enabled:
            logger.info("Webhook not enabled, test skipped")
            return False
        
        if self.is_lark_webhook:
            test_payload = {
                "msg_type": "text",
                "content": {
                    "text": "🧪 Webhook connectivity test from Bug Analysis Agent"
                }
            }
        else:
            test_payload = {
                "event_type": "test",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "message": "Webhook connectivity test"
            }
        
        try:
            logger.info(f"Testing webhook connectivity to {self.webhook_url}")
            success = self._send_with_retry(test_payload)
            
            if success:
                logger.info("Webhook test successful")
            else:
                logger.error("Webhook test failed")
                
            return success
            
        except Exception as e:
            logger.error(f"Webhook test error: {e}")
            return False 