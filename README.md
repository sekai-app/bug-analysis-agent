# 🔍 Bug Analysis Agent

**User Review-Driven Log Triage & Analysis System**

An intelligent system that automatically analyzes user feedback by correlating it with frontend and backend logs to determine if issues are bugs, feature requests, or neither. Built for mobile app debugging and user support optimization.

## ✨ Features

- **📥 Multi-format Input**: Ingests structured user reports with logs
- **🧲 Automatic Log Download**: Fetches frontend logs from S3 or HTTP endpoints
- **🔍 Smart Error Detection**: Scans logs for error patterns with context extraction
- **🔗 Backend Correlation**: Links frontend errors with AWS CloudWatch backend logs
- **🧠 AI-Powered Analysis**: Uses GPT-4o for root cause analysis and classification
- **📊 Comprehensive Reporting**: Generates detailed triage reports with recommendations
- **🌐 Web Interface**: Modern Streamlit UI with FastAPI backend for easy access

## 🌐 Web Interface

The system includes a complete web interface for easy interaction:

### Features
- **🎨 Streamlit Frontend**: User-friendly web UI for submitting reports and viewing results
- **⚡ FastAPI Backend**: RESTful API server for processing analysis requests  
- **📊 Real-time Monitoring**: Live system health status and component monitoring
- **🔄 Async Processing**: Submit long-running analyses and track progress
- **📄 Export Options**: Download results and CSV correlation data
- **📱 Responsive Design**: Works on desktop, tablet, and mobile devices
- **⚙️ Configurable Context Windows**: Separate controls for general context and request ID scanning

### Quick Start (Web Interface)

```bash
# Install dependencies (includes web interface packages)
pip install -r requirements.txt

# Start both backend and frontend (easiest method)
python run_system.py
```

**Access Points:**
- **Frontend UI**: http://localhost:8501
- **API Documentation**: http://localhost:8000/docs
- **Backend API**: http://localhost:8000

### Manual Startup

For development or debugging, start services separately:

```bash
# Terminal 1: Start API Backend
python start_backend.py

# Terminal 2: Start Frontend UI  
python start_frontend.py
```

## 🚀 CLI Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd bug_analysis_agent

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp environment.example .env

# Edit .env with your API keys
nano .env
```

Required configuration:
- `OPENAI_API_KEY`: Your OpenAI API key for GPT analysis
- `AWS_ACCESS_KEY_ID` & `AWS_SECRET_ACCESS_KEY`: For CloudWatch integration (optional)

### 3. Run Demo

```bash
# Run with sample data
python main.py

# Or analyze custom reports
python main.py custom
```

## 📋 Usage

### Basic Analysis

```python
from bug_analysis_agent.analyzer import BugAnalyzer

# Initialize analyzer
analyzer = BugAnalyzer(
    openai_api_key="your-key",
    aws_region="us-east-1",
    cloudwatch_log_group="/aws/lambda/your-service"
)

# Analyze user report
report_data = {
    "username": "@user123",
    "user_id": "12345",
    "platform": "iOS",
    "os_version": "18.5",
    "app_version": "1.31.0",
    "log_url": "https://logs.example.com/app.log",
    "env": "prod",
    "feedback": "App crashes when I try to login"
}

# Get analysis with CSV export
result = analyzer.quick_analyze(report_data, generate_csv=True)
print(result)

# Or get just the triage report and export CSV separately
triage_report = analyzer.analyze_report(report_data)
csv_file = analyzer.export_correlations_to_csv(triage_report, "my_analysis.csv")

# Configure correlation limits to reduce noise (optional)
triage_report = analyzer.analyze_report(
    report_data,
    max_correlations_per_error=5  # Allow up to 5 backend correlations per frontend error
)
print(f"CSV exported to: {csv_file}")
```

### Full Pipeline Analysis

```python
# Get detailed triage report
triage_report = analyzer.analyze_report(
    report_data,
    context_lines=10,
    time_window_minutes=2
)

# Access individual components
print(f"Issue Type: {triage_report.analysis.issue_type}")
print(f"Confidence: {triage_report.analysis.confidence}")
print(f"Frontend Errors: {len(triage_report.frontend_errors)}")
print(f"Backend Logs: {len(triage_report.backend_logs)}")
```

## 🏗️ Architecture

### Component Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Report   │───▶│   LogDownloader  │───▶│   LogScanner    │
│                 │    │                  │    │                 │
│ • User feedback │    │ • Downloads logs │    │ • Error pattern │
│ • Metadata      │    │ • S3/HTTP URLs   │    │   detection     │
│ • Log URLs      │    │ • Timeout handle │    │ • Context extract│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐             │
│   GPT Analysis  │◀───│CloudWatchFinder  │◀────────────┘
│                 │    │                  │
│ • Issue classify│    │ • Backend logs   │
│ • Root cause    │    │ • Request ID     │
│ • Recommendations│   │   correlation    │
└─────────────────┘    └──────────────────┘
```

### Data Flow

1. **📥 Ingest**: Parse user report with metadata and log URL
2. **🧲 Download**: Fetch frontend logs from provided URL
3. **🔍 Scan**: Detect error patterns and extract context (±10 lines)
4. **🔗 Correlate**: Find matching backend logs in CloudWatch by:
   - Request ID correlation
   - Timestamp-based matching (±2 minute window)
   - Error pattern matching
5. **🧠 Analyze**: GPT-4o analyzes all data to determine:
   - Issue type (bug/feature_request/neither)
   - Root cause analysis
   - Actionable recommendations

## 🔧 Components

### LogDownloader
- Downloads logs from S3 or HTTP URLs
- Handles encoding issues and timeouts
- Validates log URL formats

### LogScanner  
- Regex-based error pattern detection
- Extracts timestamps and request IDs
- Provides configurable context windows
- Supports custom error patterns

### CloudWatchFinder
- AWS CloudWatch integration
- Request ID correlation
- Time-window based searching
- Error pattern matching

### GPTAgent
- OpenAI GPT-4o integration
- Structured JSON response parsing
- Fallback analysis when unavailable
- Context-aware prompting

### BugAnalyzer
- Main orchestrator
- End-to-end pipeline execution
- Health monitoring
- Error handling and fallbacks

## 📊 Output Format

### CSV Export

The system automatically generates detailed CSV files showing frontend-backend log correlations:

```bash
# CSV file: logs/log_correlations_<user_id>_<timestamp>.csv
```

**CSV Columns:**
- `frontend_line_number`: Line number in frontend log
- `frontend_timestamp`: When the frontend error occurred  
- `frontend_error_type`: Type of error detected
- `frontend_message`: Complete error message
- `frontend_request_ids`: All request IDs found in context window (comma-separated)
- `backend_timestamp`: Corresponding backend log timestamp
- `backend_message`: Backend log message
- `backend_log_group`: AWS CloudWatch log group
- `backend_log_stream`: AWS CloudWatch log stream  
- `backend_request_id`: Request ID from backend
- `matched_request_id`: Which specific frontend request_id matched the backend log
- `correlation_method`: How logs were correlated:
  - `request_id_match`: Exact request ID match (high confidence)
  - `no_correlation`: Frontend error with no backend match
- `time_diff_seconds`: Time difference between frontend/backend logs

**Smart Correlation Logic:**
- **Complete Request ID Coverage**: Retrieves ALL backend logs matching any frontend request_id (no artificial limits)
- **Exact Matching Only**: Only `request_id_match` - no fuzzy or time-based correlations
- **CloudWatch Pagination**: Uses pagination to get complete results from CloudWatch (up to API limits)
- **Selective Limiting**: Only limits general error pattern searches (fallback), never exact matches
- **Per Frontend Error**: Backend logs deduplicated within each frontend error correlation
- **Global Deduplication**: Same backend message appears only once across entire CSV (default: enabled)
- **Message Normalization**: Whitespace normalized, handles invisible characters
- **Distilled GPT Input**: Backend JSON logs parsed to extract inner "message" field only (40-50% token reduction)

**Before**: Line 7045 → 40+ different backend messages (noise)
**After**: Line 7045 → Max 3 most relevant backend messages (signal)

### Analysis Result
```json
{
  "issue_type": "bug|feature_request|neither",
  "confidence": 0.85,
  "root_cause": "Network timeout in authentication service",
  "related_limitations": null,
  "recommendations": [
    "Investigate authentication service latency",
    "Add retry logic for network requests"
  ],
  "summary": "User experiencing login failures due to backend timeout"
}
```

### Complete Triage Report
```python
TriageReport(
    user_report=UserReport(...),
    frontend_errors=[LogError(...)],
    backend_logs=[BackendLogEntry(...)], 
    analysis=AnalysisResult(...),
    processed_at=datetime.now()
)
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key | None | Yes* |
| `GPT_MODEL` | GPT model to use | `gpt-4o` | No |
| `AWS_REGION` | AWS region | `us-east-1` | No |
| `AWS_ACCESS_KEY_ID` | AWS access key | None | No** |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | None | No** |
| `CLOUDWATCH_LOG_GROUP` | Default log group | None | No |
| `DEFAULT_CONTEXT_LINES` | Context lines around errors | `10` | No |
| `DEFAULT_TIME_WINDOW_MINUTES` | Backend correlation window | `2` | No |
| `LOG_DOWNLOAD_TIMEOUT` | Download timeout (seconds) | `30` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |

\* Required for GPT analysis. System will fall back to heuristic analysis if unavailable.  
\*\* Uses AWS default credential chain if not provided.

### Error Patterns

The system detects these error patterns by default:
- `[E]` - Explicit error markers
- `Exception:` - General exceptions
- `Error:` - Error messages
- `RangeError`, `TypeError`, `ReferenceError` - JavaScript errors
- `NetworkError` - Network failures
- `FATAL`, `CRITICAL` - Critical errors
- `crash`, `failed to`, `cannot`, `unable to` - Failure indicators

Add custom patterns:
```python
scanner = LogScanner()
scanner.add_custom_pattern(r'CUSTOM_ERROR', 'CUSTOM_TYPE')
```

## 🔒 Security

- API keys stored in environment variables
- AWS IAM role support for CloudWatch
- No sensitive data logged
- Timeout protection for external requests

## 🧪 Testing

```bash
# Run with demo data
python main.py

# Custom analysis
python main.py custom

# Test CSV export functionality
python test_csv_export.py

# Test backend log deduplication
python test_backend_deduplication.py

# Health check
from bug_analysis_agent.analyzer import BugAnalyzer
analyzer = BugAnalyzer()
health = analyzer.get_health_status()
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 🆘 Troubleshooting

### Common Issues

**"GPT agent initialization failed"**
- Check your `OPENAI_API_KEY` is valid
- Verify network connectivity to OpenAI API

**"CloudWatch connection test failed"**
- Verify AWS credentials are configured
- Check IAM permissions for CloudWatch Logs
- Ensure log group exists

**"Log download failed"**
- Verify log URL is accessible
- Check network connectivity
- Ensure URL points to a valid log file

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python main.py
```

## 🚀 Deployment

### Docker
```dockerfile
FROM python:3.9-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```

### AWS Lambda
The system can be packaged for serverless deployment with minor modifications to handle Lambda's execution model.

---

**Built with ❤️ for better user experience and faster debugging** 