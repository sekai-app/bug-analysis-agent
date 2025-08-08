"""
Lark payload parser for incoming webhook reports
"""

import re
import logging
from typing import Dict, Any, Optional
from .config import Config

logger = logging.getLogger(__name__)


class LarkPayloadParser:
    """Parse Lark webhook payloads and extract analysis data"""
    
    def __init__(self):
        # Define patterns for extracting information from Lark markdown content
        self.patterns = {
            'log_url': r'下载地址:\s*(https?://[^\s\n]+)',
            'user_id': r'上传用户:\s*(\w+)\s*@',
            'username': r'上传用户:\s*\w+\s*@([^\n]+)',
            'platform': r'系统：(\w+)',
            'os_version': r'系统版本：([^\n]+)',
            'version': r'版本号:\s*([^\n]+)',
            'environment': r'环境:\s*(\w+)',
            'feedback': r'反馈内容:\s*(.+)',
        }
    
    def parse_lark_report(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Lark interactive card payload and extract analysis data
        
        Args:
            payload: Lark webhook payload
            
        Returns:
            Dictionary with extracted analysis data, None if parsing fails
        """
        try:
            # Validate payload structure
            if not self._validate_payload(payload):
                logger.error("Invalid Lark payload structure")
                return None
            
            # Extract markdown content
            markdown_content = self._extract_markdown_content(payload)
            if not markdown_content:
                logger.error("Could not extract markdown content from payload")
                return None
            
            # Parse data from markdown
            extracted_data = self._parse_markdown_content(markdown_content)
            if not extracted_data:
                logger.error("Could not parse data from markdown content")
                return None
            
            # Convert to analysis request format
            analysis_data = self._convert_to_analysis_format(extracted_data)
            
            logger.info(f"Successfully parsed Lark report for user {analysis_data.get('user_id')}")
            return analysis_data
            
        except Exception as e:
            logger.error(f"Error parsing Lark payload: {e}")
            return None
    
    def _validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate the basic structure of Lark payload"""
        try:
            msg_type = payload.get('msg_type')
            if msg_type != 'interactive':
                logger.warning(f"Unexpected msg_type: {msg_type}")
                return False
            
            card = payload.get('card', {})
            elements = card.get('elements', [])
            
            if not elements:
                logger.error("No elements found in card")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Payload validation error: {e}")
            return False
    
    def _extract_markdown_content(self, payload: Dict[str, Any]) -> Optional[str]:
        """Extract markdown content from the Lark card"""
        try:
            elements = payload.get('card', {}).get('elements', [])
            
            # Look for the div element with lark_md content
            for element in elements:
                if (element.get('tag') == 'div' and 
                    element.get('text', {}).get('tag') == 'lark_md'):
                    return element.get('text', {}).get('content', '')
            
            logger.error("Could not find lark_md content in elements")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting markdown content: {e}")
            return None
    
    def _parse_markdown_content(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse the markdown content to extract structured data"""
        try:
            extracted = {}
            
            # Extract log URL
            log_match = re.search(self.patterns['log_url'], content)
            if log_match:
                extracted['log_url'] = log_match.group(1).strip()
            
            # Extract environment
            env_match = re.search(self.patterns['environment'], content)
            if env_match:
                extracted['environment'] = env_match.group(1).strip()
            
            # Extract version
            version_match = re.search(self.patterns['version'], content)
            if version_match:
                extracted['version'] = version_match.group(1).strip()
            
            # Extract user info (user_id and username)
            user_match = re.search(self.patterns['user_id'], content)
            if user_match:
                extracted['user_id'] = user_match.group(1).strip()
            
            user_match = re.search(self.patterns['username'], content)
            if user_match:
                extracted['username'] = user_match.group(1).strip()
            
            # Extract platform
            platform_match = re.search(self.patterns['platform'], content)
            if platform_match:
                extracted['platform'] = platform_match.group(1).strip()
            
            # Extract OS version
            os_match = re.search(self.patterns['os_version'], content)
            if os_match:
                extracted['os_version'] = os_match.group(1).strip()
            
            # Extract feedback (everything after "反馈内容:")
            feedback_match = re.search(self.patterns['feedback'], content, re.DOTALL)
            if feedback_match:
                extracted['feedback'] = feedback_match.group(1).strip()
            
            # Validate required fields
            required_fields = ['log_url', 'user_id', 'username', 'feedback']
            missing_fields = [field for field in required_fields if not extracted.get(field)]
            
            if missing_fields:
                logger.error(f"Missing required fields: {missing_fields}")
                logger.debug(f"Extracted data: {extracted}")
                logger.debug(f"Original content: {content}")
                return None
            
            return extracted
            
        except Exception as e:
            logger.error(f"Error parsing markdown content: {e}")
            return None
    
    def _convert_to_analysis_format(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert extracted data to analysis request format"""
        try:
            analysis_data = {
                "username": extracted_data.get('username', ''),
                "user_id": extracted_data.get('user_id', ''),
                "platform": extracted_data.get('platform', 'unknown'),
                "os_version": extracted_data.get('os_version', 'unknown'),
                "app_version": extracted_data.get('version', 'unknown'),
                "log_url": extracted_data.get('log_url', ''),
                "env": extracted_data.get('environment', 'unknown'),
                "feedback": extracted_data.get('feedback', ''),
                "request_id_context_lines": Config.DEFAULT_REQUEST_ID_CONTEXT_LINES,
                "time_window_minutes": Config.DEFAULT_TIME_WINDOW_MINUTES,
                "generate_csv": True
            }
            
            return analysis_data
            
        except Exception as e:
            logger.error(f"Error converting to analysis format: {e}")
            return {}
    
    def create_lark_response(self, success: bool, analysis_id: str = None, error: str = None) -> Dict[str, Any]:
        """Create a Lark response card"""
        try:
            if success and analysis_id:
                content = f"**分析已提交成功**\n\n分析ID: `{analysis_id}`\n状态: 正在处理中\n\n分析完成后将通过webhook通知结果。"
                title = "日志分析 - 已提交"
            else:
                content = f"**分析提交失败**\n\n{error or '未知错误'}\n\n请检查日志格式和参数。"
                title = "日志分析 - 失败"
            
            return {
                "msg_type": "interactive",
                "card": {
                    "config": {
                        "wide_screen_mode": True
                    },
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": title
                        }
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": content
                            }
                        }
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating Lark response: {e}")
            return {
                "msg_type": "interactive",
                "card": {
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "plain_text",
                                "content": "系统错误，请稍后重试"
                            }
                        }
                    ]
                }
            } 