# 🔍 Bug Analysis Agent - Design Document

**User Review-Driven Log Triage & Analysis System**

---

## 📖 Executive Summary

The Bug Analysis Agent is an intelligent system that automatically analyzes user feedback by correlating frontend and backend logs to determine if issues are bugs, feature requests, or neither. Using the Input-Process-Output (IPO) framework, this document describes the system architecture, data flow, and processing components.

---

## 🏗️ System Architecture Overview

```
┌─────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│   INPUTS    │───▶│      PROCESSES      │───▶│    OUTPUTS      │
│             │    │                     │    │                 │
│ User Reports│    │ 6-Stage Pipeline    │    │ Analysis Reports│
│ Frontend    │    │ - Parse & Validate  │    │ CSV Correlations│
│ Backend     │    │ - Download Logs     │    │ Recommendations │
│ Config      │    │ - Scan Errors       │    │ Health Status   │
│             │    │ - Correlate Logs    │    │                 │
│             │    │ - Map Relations     │    │                 │
│             │    │ - AI Analysis       │    │                 │
└─────────────┘    └─────────────────────┘    └─────────────────┘
```

---

## 📥 INPUT SPECIFICATION

### 1. **Primary Input: User Report**
```python
UserReport {
    username: str          # User identifier (e.g., "@user123")
    user_id: str          # Unique user ID
    platform: str         # "iOS" | "Android" | "Web"
    os_version: str       # Operating system version
    app_version: str      # Application version
    log_url: HttpUrl      # URL to frontend log file
    env: str             # "prod" | "staging" | "dev"
    feedback: str        # User's description of the issue
}
```
2. Time Window Match (Medium Confidence) !!!!
  - ±2 minute time window
  - Error pattern filtering
**Input Sources:**
- User support tickets
- App crash reports
- Customer feedback forms
- Bug report submissions

### 2. **Configuration Inputs**
```python
Configuration {
    # OpenAI Configuration
    OPENAI_API_KEY: str
    GPT_MODEL: str = "gpt-4o"
    
    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    CLOUDWATCH_LOG_GROUP: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    
    # Analysis Parameters
    DEFAULT_CONTEXT_LINES: int = 10
    DEFAULT_TIME_WINDOW_MINUTES: int = 2
    LOG_DOWNLOAD_TIMEOUT: int = 30
    
    # Processing Limits
    max_correlations_per_error: int = 3
    global_deduplication: bool = True
}
```

### 3. **External Data Sources**
- **Frontend Logs**: Downloaded from S3 or HTTP endpoints
- **Backend Logs**: Retrieved from AWS CloudWatch
- **Error Patterns**: Pre-defined regex patterns for error detection

---

## ⚙️ PROCESS SPECIFICATION

### **6-Stage Processing Pipeline**

#### **Stage 1: Input Validation & Parsing**
```python
Process: UserReport Validation
Input: Raw user report data (Dict[str, Any])
Output: Validated UserReport object
Components: Pydantic model validation
Error Handling: ValueError for invalid data
```

#### **Stage 2: Frontend Log Acquisition**
```python
Process: Log Download
Input: log_url from UserReport
Output: Raw log content (str)
Components: LogDownloader
- HTTP/HTTPS download
- S3 integration
- Timeout handling
Error Handling: RuntimeError for download failures
```

#### **Stage 3: Frontend Error Detection**
```python
Process: Error Pattern Scanning
Input: Raw log content
Output: List[LogError]
Components: LogScanner
- Regex pattern matching
- Context extraction (lines before/after)
- Timestamp extraction
- Multiple request ID extraction (11-line window: ±5 lines)
Patterns Detected:
- EXPLICIT_ERROR: [E], [ERROR], [FATAL]
- EXCEPTION: Exception:, Error:
- NETWORK_ERROR: NetworkError
- TIMEOUT: timeout patterns
- CRASH: crash, failed to
```

#### **Stage 4: Backend Log Correlation**
```python
Process: CloudWatch Log Correlation
Input: List[LogError], CloudWatch configuration
Output: List[BackendLogEntry]
Components: CloudWatchFinder
Correlation Methods:
1. Multiple Request ID Match (High Confidence)
   - Searches backend logs for ALL frontend request_ids
   - Retrieves ALL matching backend logs (no artificial limits)
   - Uses CloudWatch pagination to get complete results
   - Exact matching only
Optimization:
- Searches for each request_id found in frontend error context
- Deduplicates backend logs across multiple request_id searches
- No limits on exact request_id matches
- Only limits  pattern searches (fallback)
- Global deduplication
```

#### **Stage 5: Correlation Mapping**
```python
Process: Frontend-Backend Relationship Mapping
Input: List[LogError], List[BackendLogEntry]
Output: List[CorrelationMapping]
Components: Correlation Engine
Mapping Structure:
{
    frontend_line_number: int
    frontend_timestamp: str
    frontend_error_type: str
    frontend_message: str
    frontend_request_ids: str  # All request_ids (comma-separated)
    backend_timestamp: str
    backend_message: str
    backend_log_group: str
    backend_log_stream: str
    backend_request_id: str
    matched_request_id: str  # Which frontend request_id matched
    correlation_method: str  # "request_id_match" | "no_correlation"
    time_diff_seconds: float
}
```

#### **Stage 6: AI-Powered Analysis**
```python
Process: GPT-4o Root Cause Analysis
Input: UserReport, List[CorrelationMapping] (distilled)
Output: AnalysisResult
Components: GPTAgent
Backend Log Processing:
- Parses CloudWatch JSON logs and extracts inner "message" field
- Removes JSON metadata: level, request_id, elapsed, extra, position, etc.
- Converts: {"level":"INFO","message":"Request failed"} → "Request failed"
- 40-50% reduction in token usage
- Focuses GPT on actual application log content vs. infrastructure metadata
Analysis Dimensions:
- Issue Classification: "bug" | "feature_request" | "neither"
- Confidence Level: 0.0-1.0
- Root Cause Analysis
- Technical Limitations
- Actionable Recommendations
Fallback: Rule-based classification when GPT unavailable
```

---

## 📤 OUTPUT SPECIFICATION

### 1. **Primary Output: Triage Report**
```python
TriageReport {
    user_report: UserReport
    frontend_errors: List[LogError]
    backend_logs: List[BackendLogEntry]
    analysis: AnalysisResult
    processed_at: datetime
}
```

### 2. **Analysis Result Structure**
```python
AnalysisResult {
    issue_type: str           # "bug" | "feature_request" | "neither"
    confidence: float         # 0.0-1.0
    root_cause: str | None    # Technical explanation for bugs
    related_limitations: str | None  # Technical constraints for features
    recommendations: List[str] # Actionable next steps
    summary: str             # 2-3 sentence overview
}
```

### 3. **Formatted Analysis Summary**
```
📋 BUG ANALYSIS REPORT
==================================================

🗣️ User Feedback: "App keeps crashing when I try to load content"
👤 User: @testuser (ID: 12345)
📱 Platform: iOS - 18.5
🔧 App Version: 1.31.0
🌍 Environment: prod

📊 ANALYSIS RESULTS
==================================================

🎯 Issue Type: BUG
🎲 Confidence: 90.0%
📝 Summary: Frontend errors indicate bad state handling...
🔍 Root Cause: Multiple 'Bad state: No element' errors...

💡 RECOMMENDATIONS
------------------------------
1. Fix empty collection handling
2. Ensure Firebase initialization
3. Review app initialization sequence

📊 LOG SUMMARY
------------------------------
Frontend Errors: 16
Backend Logs: 9
```

### 4. **CSV Correlation Export**
```csv
frontend_line_number,frontend_timestamp,frontend_error_type,frontend_message,frontend_request_ids,backend_timestamp,backend_message,backend_log_group,backend_log_stream,backend_request_id,matched_request_id,correlation_method,time_diff_seconds
7045,1753828239576,EXPLICIT_ERROR,[AudioDownloadManager] Error,"efb9a61e89dd4382bf6207fce3632714,abc123,def456",2025-07-30T06:30:39.699000,{"level": "INFO"...},/ecs/app-backend-api/prod,ecs/sekai-backend-api-prod/...,086b1f72-2e5f-4fa7-808a-50e2c8f1454d,efb9a61e89dd4382bf6207fce3632714,request_id_match,
```

### 5. **System Health Status**
```python
HealthStatus {
    components: {
        "downloader": "healthy" | "degraded" | "unhealthy",
        "scanner": "healthy" | "degraded" | "unhealthy",
        "cloudwatch": "healthy" | "degraded" | "unhealthy",
        "gpt_agent": "healthy" | "degraded" | "unhealthy"
    },
    configuration: {
        "openai_configured": bool,
        "aws_configured": bool,
        "cloudwatch_accessible": bool
    },
    last_check: datetime
}
```

---

## 🔄 DATA FLOW DIAGRAM

```
User Report Input
       ↓
┌─────────────────┐
│ Input Validation│
│ & Parsing       │
└─────────────────┘
       ↓
┌─────────────────┐     Frontend Log URL
│ Log Download    │ ←─────────────────────
│                 │
└─────────────────┘
       ↓
┌─────────────────┐     Error Patterns
│ Error Detection │ ←─────────────────
│ & Scanning      │
└─────────────────┘
       ↓
┌─────────────────┐     CloudWatch API
│ Backend Log     │ ←─────────────────
│ Correlation     │
└─────────────────┘
       ↓
┌─────────────────┐
│ Correlation     │
│ Mapping         │
└─────────────────┘
       ↓
┌─────────────────┐     OpenAI API
│ GPT Analysis    │ ←─────────────────
│                 │
└─────────────────┘
       ↓
┌─────────────────┐
│ Report          │
│ Generation      │
└─────────────────┘
       ↓
Multiple Output Formats
- Triage Report
- CSV Export
- Formatted Summary
- Health Status
```

---

## 🏭 COMPONENT ARCHITECTURE

### **Core Components**

#### **1. BugAnalyzer (Orchestrator)**
- **Responsibility**: Main system coordinator
- **Dependencies**: All subsystem components
- **Interface**: Public API for analysis requests
- **Error Handling**: Graceful degradation with fallbacks

#### **2. LogDownloader**
- **Responsibility**: Fetch logs from external sources
- **Protocols**: HTTP/HTTPS, S3
- **Features**: Timeout handling, retry logic
- **Security**: URL validation, size limits

#### **3. LogScanner**
- **Responsibility**: Pattern-based error detection
- **Algorithms**: Regex matching, context extraction
- **Patterns**: 15+ error pattern types
- **Optimization**: Compiled regex, line-by-line processing

#### **4. CloudWatchFinder**
- **Responsibility**: Backend log correlation
- **AWS Integration**: CloudWatch Logs API
- **Correlation Logic**: 
  - Tier 1: Request ID matching
  - Tier 2: Time window + error patterns
- **Performance**: Limited results, deduplication

#### **5. GPTAgent**
- **Responsibility**: AI-powered analysis
- **Model**: GPT-4o with structured prompts
- **Input**: Correlation mappings (not raw lists)
- **Output**: Structured JSON analysis
- **Fallback**: Rule-based classification

---

## 🔧 CONFIGURATION MATRIX

| Component | Required Config | Optional Config | Default Values |
|-----------|----------------|-----------------|----------------|
| **GPTAgent** | OPENAI_API_KEY | GPT_MODEL | gpt-4o |
| **CloudWatch** | AWS credentials | LOG_GROUP, REGION | us-east-1 |
| **Scanner** | - | CONTEXT_LINES | 10 |
| **Correlation** | - | TIME_WINDOW, MAX_CORRELATIONS | 2min, 3 |
| **Downloader** | - | TIMEOUT | 30s |

---

## 📊 PERFORMANCE CHARACTERISTICS

### **Processing Limits**
- **Frontend Errors**: Unlimited detection
- **Backend Correlations**: Max 3 per frontend error
- **Time Window**: ±2 minutes default
- **Context Lines**: 10 lines before/after errors
- **Log Size**: No hard limit (timeout-based)

### **Correlation Confidence Levels**
1. **High Confidence**: Exact request ID match
2. **Medium Confidence**: Time window + error patterns
3. **Low Confidence**: Time window only
4. **No Correlation**: Frontend error only

### **Fallback Mechanisms**
- **GPT Unavailable**: Rule-based classification
- **AWS Unavailable**: Frontend-only analysis
- **Download Failed**: Analysis with provided data
- **Invalid Input**: Detailed error messages

---

## 🛡️ ERROR HANDLING STRATEGY

### **Input Validation Errors**
- **Invalid UserReport**: ValueError with field details
- **Malformed URLs**: HTTP validation errors
- **Missing Config**: Configuration warnings

### **Processing Errors**
- **Download Failures**: Retry with exponential backoff
- **CloudWatch Errors**: Graceful degradation to frontend-only
- **GPT API Errors**: Automatic fallback to rule-based analysis
- **Timeout Errors**: Partial results with warnings

### **Output Guarantees**
- **Always Returns**: Valid TriageReport or detailed error
- **Never Crashes**: Comprehensive exception handling
- **Partial Success**: Useful results even with component failures
- **Audit Trail**: Complete logging of all operations

---

## 🔮 EXTENSIBILITY POINTS

### **Input Sources**
- Additional log formats (JSON, XML)
- Real-time streaming logs
- Multiple log file support
- Database integration

### **Error Detection**
- Machine learning-based pattern detection
- Custom regex patterns
- Language-specific error handling
- Performance metric analysis

### **Correlation Methods**
- Session ID correlation
- User journey tracking
- Geographic correlation
- Custom correlation algorithms

### **Analysis Engines**
- Alternative AI models
- Ensemble analysis
- Domain-specific analyzers
- Confidence aggregation

### **Output Formats**
- REST API endpoints
- Real-time dashboards
- Integration webhooks
- Custom report templates


### **Other Suggestions**
- Append common errors into a list, skip processing
- 
- Add processing for image reviews
---

## 📈 METRICS & MONITORING

### **System Metrics**
- Processing time per stage
- Success/failure rates
- API call latencies
- Resource utilization

### **Business Metrics**
- Issue classification accuracy
- User satisfaction correlation
- False positive rates
- Resolution time improvement

### **Quality Metrics**
- Correlation precision/recall
- GPT analysis consistency
- Error detection coverage
- Recommendation effectiveness

---

## 🎯 CONCLUSION

The Bug Analysis Agent implements a robust IPO framework that transforms user feedback into actionable insights through intelligent log correlation and AI analysis. The system's modular architecture ensures scalability, reliability, and extensibility while maintaining high performance and accuracy in issue classification and root cause analysis.

**Key Strengths:**
- ✅ Comprehensive correlation between frontend and backend logs
- ✅ AI-powered analysis with intelligent fallbacks
- ✅ Structured output formats for multiple use cases
- ✅ Robust error handling and graceful degradation
- ✅ Highly configurable and extensible architecture

**Primary Use Cases:**
- 🎯 Customer support ticket triage
- 🎯 Automated bug report classification
- 🎯 Root cause analysis for app crashes
- 🎯 Feature request identification and prioritization
- 🎯 Development team workflow optimization 