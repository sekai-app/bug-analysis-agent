"""
Data models for bug analysis agent
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl


class UserReport(BaseModel):
    """Initial user report model"""
    username: str
    user_id: str
    platform: str
    os_version: str
    app_version: str
    log_url: HttpUrl
    env: str
    feedback: str


class LogError(BaseModel):
    """Model for detected log errors"""
    timestamp: Optional[str] = None
    request_id: Optional[str] = None  # Keep for backward compatibility
    request_ids: List[str] = []  # New field for multiple request_ids
    error_type: str
    log_segment: str
    context_before: List[str]
    context_after: List[str]
    line_number: int


class BackendLogEntry(BaseModel):
    """Model for backend log entries from CloudWatch"""
    timestamp: datetime
    message: str
    request_id: Optional[str] = None
    log_group: str
    log_stream: str


class AnalysisResult(BaseModel):
    """Model for GPT analysis result"""
    issue_type: str  # "feature_request", "bug", "neither"
    confidence: float
    root_cause: Optional[str] = None
    related_limitations: Optional[str] = None
    recommendations: List[str]
    summary: str


class TriageReport(BaseModel):
    """Complete triage report"""
    user_report: UserReport
    frontend_errors: List[LogError]
    backend_logs: List[BackendLogEntry]
    analysis: AnalysisResult
    processed_at: datetime 