"""
GPTAgent - Module for analyzing logs and user feedback using OpenAI GPT
"""

from openai import OpenAI
import logging
import json
from typing import List, Optional, Dict, Any
from .models import UserReport, LogError, BackendLogEntry, AnalysisResult

logger = logging.getLogger(__name__)


class GPTAgent:
    """Uses GPT to analyze user feedback and logs for root cause analysis"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize GPT agent
        
        Args:
            api_key: OpenAI API key (if None, will use environment variable)
            model: GPT model to use
        """
        self.model = model
        
        # Initialize OpenAI client (will use OPENAI_API_KEY env var if api_key is None)
        self.client = OpenAI(api_key=api_key,base_url="https://yunwu.ai/v1")
        
        # Test the connection
        try:
            # Simple test to verify API key works
            self.client.models.list()
            logger.info(f"GPT agent initialized with model: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize GPT agent: {e}")
            raise
    
    def analyze_user_report(
        self, 
        user_report: UserReport,
        correlations: List[Dict[str, Any]]
    ) -> AnalysisResult:
        """
        Analyze user report with log correlations to determine root cause
        
        Args:
            user_report: The initial user report
            correlations: List of frontend-backend log correlations
            
        Returns:
            AnalysisResult with insights and recommendations
        """
        
        # Construct the analysis prompt
        context = self._build_analysis_context(user_report, correlations)
        
        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(context)

        print(f"System prompt: {system_prompt}")
        print(f"User prompt: {user_prompt}")
        
        try:
            logger.info("Sending analysis request to GPT")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt + "\n" + user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=1500
            )
            
            # Parse the response
            analysis_text = response.choices[0].message.content
            analysis_result = self._parse_gpt_response(analysis_text)
            
            logger.info(f"Analysis completed: {analysis_result.issue_type}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error during GPT analysis: {e}")
            # Return a fallback analysis
            return self._create_fallback_analysis(user_report, correlations)
    
    def _build_analysis_context(
        self,
        user_report: UserReport,
        correlations: List[Dict[str, Any]]
    ) -> str:
        """Build formatted context for GPT analysis using correlation mappings"""
        
        # Count different types of correlations
        total_correlations = len(correlations)
        correlations_with_backend = len([c for c in correlations if c.get('backend_message')])
        no_correlations = total_correlations - correlations_with_backend
        
        # Group correlations by frontend error
        frontend_errors = {}
        for correlation in correlations:
            line_num = correlation['frontend_line_number']
            if line_num not in frontend_errors:
                frontend_errors[line_num] = {
                    'error_type': correlation['frontend_error_type'],
                    'message': correlation['frontend_message'],
                    'timestamp': correlation['frontend_timestamp'],
                    'request_ids': correlation['frontend_request_ids'],
                    'backend_correlations': []
                }
            
            # Add backend correlation if it exists
            if correlation.get('backend_message'):
                frontend_errors[line_num]['backend_correlations'].append({
                    'timestamp': correlation['backend_timestamp'],
                    'message': correlation['backend_message'],
                    'request_id': correlation['backend_request_id'],
                    'method': correlation['correlation_method'],
                    'time_diff': correlation.get('time_diff_seconds', '')
                })
        
        context = f"""
用户评价: "{user_report.feedback}"
用户ID: {user_report.user_id}, 平台: {user_report.platform}, App版本: v{user_report.app_version}
环境: {user_report.env}
操作系统版本: {user_report.os_version}

日志关联汇总:
- 前端错误总数: {len(frontend_errors)}
- 有后端关联的错误: {correlations_with_backend}
- 无后端关联的错误: {no_correlations}
"""
        
        # Add frontend errors with their backend correlations
        if frontend_errors:
            context += "\n前端-后端日志关联:\n"
            for i, (line_num, error_info) in enumerate(frontend_errors.items(), 1):
                context += f"\n错误 {i} (第{line_num}行) - {error_info['error_type']}:\n"
                
                if error_info['timestamp']:
                    context += f"前端时间戳: {error_info['timestamp']}\n"
                if error_info['request_ids']:
                    context += f"前端Request ID: {error_info['request_ids']}\n"
                
                context += f"前端消息: {error_info['message']}\n"
                
                # Add backend correlations (distilled to verbose content only)
                if error_info['backend_correlations']:
                    context += f"后端关联 ({len(error_info['backend_correlations'])}):\n"
                    for j, backend_corr in enumerate(error_info['backend_correlations'], 1):
                        # Extract verbose message content from JSON structure
                        verbose_message = self._extract_verbose_message(backend_corr['message'])
                        context += f"  {j}. {verbose_message}\n"
                else:
                    context += "后端关联: 未找到\n"
                
                context += "\n" + "-"*50 + "\n"
        else:
            context += "\n前端日志: 未检测到错误\n"
        
        return context
    
    def _extract_verbose_message(self, backend_log_message: str) -> str:
        """
        Extract verbose message content from backend log JSON structure
        
        Args:
            backend_log_message: Full JSON log string from CloudWatch
            
        Returns:
            Just the verbose message content for GPT analysis
        """
        try:
            import json
            
            # Try to parse as JSON to extract the inner message field
            log_data = json.loads(backend_log_message)
            
            # Extract the actual verbose message content
            if isinstance(log_data, dict) and 'message' in log_data:
                return log_data['message']
            else:
                # Fallback: return original message if not JSON or no inner message
                return backend_log_message
                
        except (json.JSONDecodeError, TypeError):
            # If it's not valid JSON, return the original message
            return backend_log_message
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for GPT analysis"""
        return """你是一位专业的软件工程师，专门从事移动应用调试和用户反馈分析。请用中文进行分析，但保留英文技术术语、框架名称和应用名称。

你的任务是分析用户报告以及前端-后端日志关联，以确定：
1. 用户反馈是否表明是bug、功能请求或其他
2. 如果是bug，基于关联日志识别最可能的根本原因
3. 如果是功能请求，识别日志中显示的任何技术限制
4. 提供可操作的建议

请使用以下精确格式的JSON对象回复：
{
  "issue_type": "bug|feature_request|neither",
  "confidence": 0.0-1.0,
  "root_cause": "如果是bug则详细解释，否则为null",
  "related_limitations": "如果是功能请求则说明技术限制，否则为null", 
  "recommendations": ["可操作的建议1", "可操作的建议2"],
  "summary": "分析的简要2-3句总结"
}

考虑以下因素：
- 用户语言和上下文线索
- 错误模式和频率
- Request ID关联和时序关系
- 平台特定问题
- App版本兼容性
- Backend服务可用性
- 关联方法置信度（仅request_id_match）

要简洁但全面。专注于可操作的见解。"""
    
    def _get_user_prompt(self, context: str) -> str:
        """Get the user prompt with context"""
        return f"""请分析以下用户报告和相关的前端-后端日志关联：

{context}

分析任务：
1. 此用户反馈是功能请求、bug报告还是其他？
2. 如果是bug，基于关联日志最可能的技术问题是什么？
3. 如果是功能请求，日志中是否显示任何技术限制？
4. 你对解决此问题有什么具体建议？

请以要求的JSON格式提供你的分析。"""
    
    def _parse_gpt_response(self, response_text: str) -> AnalysisResult:
        """Parse GPT response into AnalysisResult object"""
        
        try:
            # Extract JSON from response (in case there's extra text)
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")
            
            json_text = response_text[start_idx:end_idx]
            data = json.loads(json_text)
            
            return AnalysisResult(
                issue_type=data.get('issue_type', 'unknown'),
                confidence=float(data.get('confidence', 0.5)),
                root_cause=data.get('root_cause'),
                related_limitations=data.get('related_limitations'),
                recommendations=data.get('recommendations', []),
                summary=data.get('summary', 'Analysis completed')
            )
            
        except Exception as e:
            logger.error(f"Error parsing GPT response: {e}")
            logger.debug(f"Response text: {response_text}")
            
            # Try to extract key information manually
            response_lower = response_text.lower()
            
            if any(word in response_lower for word in ['feature', 'request', 'add', 'implement']):
                issue_type = 'feature_request'
            elif any(word in response_lower for word in ['bug', 'error', 'issue', 'problem']):
                issue_type = 'bug'
            else:
                issue_type = 'neither'
            
            return AnalysisResult(
                issue_type=issue_type,
                confidence=0.3,
                root_cause=None,
                related_limitations=None,
                recommendations=["Manual review required - GPT response parsing failed"],
                summary="Analysis completed with limited parsing due to response format issues"
            )
    
    def _create_fallback_analysis(
        self, 
        user_report: UserReport, 
        correlations: List[Dict[str, Any]]
    ) -> AnalysisResult:
        """Create a fallback analysis when GPT is unavailable"""
        
        feedback_lower = user_report.feedback.lower()
        
        # Count frontend errors from correlations
        frontend_errors = len(set(c['frontend_line_number'] for c in correlations))
        correlations_with_backend = len([c for c in correlations if c.get('backend_message')])
        
        # Simple heuristics for classification
        if any(word in feedback_lower for word in ['make', 'add', 'could you', 'can you', 'feature']):
            issue_type = 'feature_request'
            summary = "Appears to be a feature request based on user language"
        elif frontend_errors > 0:
            issue_type = 'bug'
            summary = f"Likely bug - {frontend_errors} error(s) detected in logs"
        else:
            issue_type = 'neither'
            summary = "Unable to classify - no clear errors or feature requests detected"
        
        recommendations = []
        if frontend_errors > 0:
            recommendations.append(f"Investigate {frontend_errors} error(s) found in frontend logs")
        if correlations_with_backend > 0:
            recommendations.append(f"Review {correlations_with_backend} backend correlations for root cause")
        recommendations.append("Manual review recommended - automated analysis unavailable")
        
        return AnalysisResult(
            issue_type=issue_type,
            confidence=0.4,
            root_cause=None,
            related_limitations=None,
            recommendations=recommendations,
            summary=summary
        ) 