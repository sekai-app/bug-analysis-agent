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
🗣️ User Review: "{user_report.feedback}"
📱 User ID: {user_report.user_id}, Platform: {user_report.platform}, App v{user_report.app_version}
🌍 Environment: {user_report.env}
💻 OS Version: {user_report.os_version}

🧾 Log Correlation Summary:
- Total frontend errors: {len(frontend_errors)}
- Errors with backend correlation: {correlations_with_backend}
- Errors without backend correlation: {no_correlations}
"""
        
        # Add frontend errors with their backend correlations
        if frontend_errors:
            context += "\n📦 Frontend-Backend Log Correlations:\n"
            for i, (line_num, error_info) in enumerate(frontend_errors.items(), 1):
                context += f"\n🔍 Error {i} (Line {line_num}) - {error_info['error_type']}:\n"
                
                if error_info['timestamp']:
                    context += f"Frontend Timestamp: {error_info['timestamp']}\n"
                if error_info['request_ids']:
                    context += f"Frontend Request IDs: {error_info['request_ids']}\n"
                
                context += f"Frontend Message: {error_info['message']}\n"
                
                # Add backend correlations (distilled to verbose content only)
                if error_info['backend_correlations']:
                    context += f"Backend Correlations ({len(error_info['backend_correlations'])}):\n"
                    for j, backend_corr in enumerate(error_info['backend_correlations'], 1):
                        # Extract verbose message content from JSON structure
                        verbose_message = self._extract_verbose_message(backend_corr['message'])
                        context += f"  {j}. {verbose_message}\n"
                else:
                    context += "Backend Correlations: None found\n"
                
                context += "\n" + "-"*50 + "\n"
        else:
            context += "\n📦 Frontend Logs: No errors detected\n"
        
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
        return """You are an expert software engineer specializing in mobile app debugging and user feedback analysis. 

Your task is to analyze user reports along with frontend-backend log correlations to determine:
1. Whether the user feedback indicates a bug, feature request, or neither
2. If it's a bug, identify the most likely root cause based on the correlated logs
3. If it's a feature request, identify any technical limitations shown in the logs
4. Provide actionable recommendations

Respond with a JSON object in this exact format:
{
  "issue_type": "bug|feature_request|neither",
  "confidence": 0.0-1.0,
  "root_cause": "detailed explanation if bug, null otherwise",
  "related_limitations": "technical limitations if feature request, null otherwise", 
  "recommendations": ["actionable recommendation 1", "actionable recommendation 2"],
  "summary": "brief 2-3 sentence summary of your analysis"
}

Consider these factors:
- User language and context clues
- Error patterns and frequency
- Request ID correlations and timing relationships
- Platform-specific issues
- App version compatibility
- Backend service availability
- Correlation method confidence (request_id_match only)

Be concise but thorough. Focus on actionable insights."""
    
    def _get_user_prompt(self, context: str) -> str:
        """Get the user prompt with context"""
        return f"""Please analyze this user report and associated frontend-backend log correlations:

{context}

🎯 Analysis Tasks:
1. Is this user feedback a feature request, bug report, or neither?
2. If it's a bug, what is the most likely technical issue based on the correlated logs?
3. If it's a feature request, are there any technical limitations visible in the logs?
4. What are your specific recommendations for addressing this?

Please provide your analysis in the requested JSON format."""
    
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