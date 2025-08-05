#!/usr/bin/env python3
"""
FastAPI backend for Bug Analysis Agent
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
import os

from bug_analysis_agent.analyzer import BugAnalyzer
from bug_analysis_agent.config import Config
from bug_analysis_agent.webhook import WebhookSender


# Request/Response Models
class AnalysisRequest(BaseModel):
    username: str
    user_id: str
    platform: str
    os_version: str
    app_version: str
    log_url: HttpUrl
    env: str
    feedback: str
    context_lines: int = 10
    request_id_context_lines: int = 5
    time_window_minutes: int = 10  # 10 minutes default
    generate_csv: bool = True


class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    csv_file: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str
    components: Dict[str, str]
    timestamp: datetime


# Global analyzer instance
analyzer = None
webhook_sender = None
analysis_jobs = {}  # Store analysis jobs by ID


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup analyzer"""
    global analyzer, webhook_sender
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize analyzer
    try:
        analyzer = BugAnalyzer(
            openai_api_key=Config.OPENAI_API_KEY,
            aws_region=Config.AWS_REGION,
            cloudwatch_log_group=Config.CLOUDWATCH_LOG_GROUP,
            gpt_model=Config.GPT_MODEL
        )
        logging.info("BugAnalyzer initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize analyzer: {e}")
        analyzer = None
    
    # Initialize webhook sender
    try:
        webhook_sender = WebhookSender()
        logging.info("Webhook sender initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize webhook sender: {e}")
        webhook_sender = None
    
    yield
    
    # Cleanup
    logging.info("Shutting down API server")


# Create FastAPI app
app = FastAPI(
    title="Bug Analysis Agent API",
    description="API for User Review-Driven Log Triage & Analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def get_health():
    """Get system health status"""
    if analyzer is None:
        raise HTTPException(status_code=503, detail="Analyzer not initialized")
    
    try:
        # Get analyzer component health
        health_status = analyzer.get_health_status()
        
        # Add webhook status
        if webhook_sender:
            health_status['webhook'] = 'ok' if webhook_sender.enabled else 'disabled'
        else:
            health_status['webhook'] = 'unavailable'
        
        return HealthResponse(
            status="healthy",
            components=health_status,
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")


@app.post("/webhook/test")
async def test_webhook():
    """Test webhook connectivity"""
    if webhook_sender is None:
        raise HTTPException(status_code=503, detail="Webhook sender not initialized")
    
    if not webhook_sender.enabled:
        raise HTTPException(status_code=400, detail="Webhook not configured or disabled")
    
    try:
        success = webhook_sender.test_webhook()
        if success:
            return {"status": "success", "message": "Webhook test successful"}
        else:
            return {"status": "failed", "message": "Webhook test failed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook test error: {e}")


@app.post("/analyze", response_model=AnalysisResponse)
async def start_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """Start a new bug analysis (async)"""
    if analyzer is None:
        raise HTTPException(status_code=503, detail="Analyzer not initialized")
    
    # Generate analysis ID
    analysis_id = f"analysis_{request.user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    
    # Create job entry
    analysis_jobs[analysis_id] = AnalysisResponse(
        analysis_id=analysis_id,
        status="running",
        created_at=datetime.utcnow()
    )
    
    # Start background analysis
    background_tasks.add_task(run_analysis, analysis_id, request.dict())
    
    return analysis_jobs[analysis_id]


@app.post("/analyze/sync", response_model=AnalysisResponse)
async def analyze_sync(request: AnalysisRequest):
    """Run synchronous analysis (for testing/small requests)"""
    if analyzer is None:
        raise HTTPException(status_code=503, detail="Analyzer not initialized")
    
    analysis_id = f"sync_{request.user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    created_at = datetime.utcnow()
    
    try:
        # Convert to dict for analyzer
        report_data = request.dict()
        
        # Run analysis
        csv_file_path = None
        if request.generate_csv:
            triage_report = analyzer.analyze_report(
                report_data,
                context_lines=request.context_lines,
                request_id_context_lines=request.request_id_context_lines,
                time_window_minutes=request.time_window_minutes
            )
            result = analyzer.format_analysis_summary(triage_report)
            csv_file_path = analyzer.export_correlations_to_csv(triage_report)
        else:
            triage_report = analyzer.analyze_report(
                report_data,
                context_lines=request.context_lines,
                request_id_context_lines=request.request_id_context_lines,
                time_window_minutes=request.time_window_minutes
            )
            result = analyzer.format_analysis_summary(triage_report)
        
        completed_at = datetime.utcnow()
        
        # Send webhook notification
        if webhook_sender:
            try:
                webhook_sender.send_analysis_complete(
                    analysis_id=analysis_id,
                    status="completed",
                    result=result,
                    csv_file=csv_file_path,
                    user_id=request.user_id,
                    created_at=created_at,
                    completed_at=completed_at
                )
            except Exception as e:
                logging.warning(f"Failed to send webhook for analysis {analysis_id}: {e}")
        
        return AnalysisResponse(
            analysis_id=analysis_id,
            status="completed",
            result=result,
            csv_file=csv_file_path,
            created_at=created_at,
            completed_at=completed_at
        )
        
    except Exception as e:
        completed_at = datetime.utcnow()
        
        # Send webhook notification for failure
        if webhook_sender:
            try:
                webhook_sender.send_analysis_complete(
                    analysis_id=analysis_id,
                    status="failed",
                    error=str(e),
                    user_id=request.user_id,
                    created_at=created_at,
                    completed_at=completed_at
                )
            except Exception as webhook_error:
                logging.warning(f"Failed to send webhook for failed analysis {analysis_id}: {webhook_error}")
        
        return AnalysisResponse(
            analysis_id=analysis_id,
            status="failed",
            error=str(e),
            created_at=created_at,
            completed_at=completed_at
        )


@app.get("/analyze/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis_status(analysis_id: str):
    """Get analysis status and results"""
    if analysis_id not in analysis_jobs:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return analysis_jobs[analysis_id]


@app.get("/analyze")
async def list_analyses():
    """List all analyses"""
    return {
        "analyses": list(analysis_jobs.keys()),
        "count": len(analysis_jobs)
    }


@app.delete("/analyze/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """Delete analysis results"""
    if analysis_id not in analysis_jobs:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    del analysis_jobs[analysis_id]
    return {"message": "Analysis deleted"}


async def run_analysis(analysis_id: str, report_data: Dict[str, Any]):
    """Background task to run analysis"""
    try:
        # Run the analysis
        generate_csv = report_data.get('generate_csv', True)
        
        if generate_csv:
            triage_report = analyzer.analyze_report(
                report_data,
                context_lines=report_data.get('context_lines', 10),
                request_id_context_lines=report_data.get('request_id_context_lines', 5),
                time_window_minutes=report_data.get('time_window_minutes', 10)  # 10 minutes default
            )
            result = analyzer.format_analysis_summary(triage_report)
            csv_file_path = analyzer.export_correlations_to_csv(triage_report)
        else:
            result = analyzer.quick_analyze(report_data, generate_csv=False)
            csv_file_path = None
        
        # Update job status
        analysis_jobs[analysis_id].status = "completed"
        analysis_jobs[analysis_id].result = result
        analysis_jobs[analysis_id].csv_file = csv_file_path
        analysis_jobs[analysis_id].completed_at = datetime.utcnow()
        
        # Send webhook notification
        if webhook_sender:
            try:
                webhook_sender.send_analysis_complete(
                    analysis_id=analysis_id,
                    status="completed",
                    result=result,
                    csv_file=csv_file_path,
                    user_id=report_data.get('user_id'),
                    created_at=analysis_jobs[analysis_id].created_at,
                    completed_at=analysis_jobs[analysis_id].completed_at
                )
            except Exception as e:
                logging.warning(f"Failed to send webhook for analysis {analysis_id}: {e}")
        
    except Exception as e:
        # Update job with error
        analysis_jobs[analysis_id].status = "failed"
        analysis_jobs[analysis_id].error = str(e)
        analysis_jobs[analysis_id].completed_at = datetime.utcnow()
        
        # Send webhook notification for failure
        if webhook_sender:
            try:
                webhook_sender.send_analysis_complete(
                    analysis_id=analysis_id,
                    status="failed",
                    error=str(e),
                    user_id=report_data.get('user_id'),
                    created_at=analysis_jobs[analysis_id].created_at,
                    completed_at=analysis_jobs[analysis_id].completed_at
                )
            except Exception as webhook_error:
                logging.warning(f"Failed to send webhook for failed analysis {analysis_id}: {webhook_error}")


@app.get("/download-csv/{filename}")
async def download_csv(filename: str):
    """Download CSV file"""
    # Security: only allow files from logs directory and with .csv extension
    if not filename.endswith('.csv') or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = os.path.join("logs", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="CSV file not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='text/csv'
    )


@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "message": "Bug Analysis Agent API",
        "version": "1.0.0",
        "status": "running",
        "analyzer_available": analyzer is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 