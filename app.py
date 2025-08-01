#!/usr/bin/env python3
"""
Streamlit frontend for Bug Analysis Agent
"""

import streamlit as st
import requests
import json
import time
import os
from datetime import datetime
from typing import Dict, Any, Optional

# API Configuration
# API_BASE_URL = "http://localhost:8000"
API_BASE_URL = "http://3.238.204.247:8000"


def check_api_health() -> bool:
    """Check if the API is available"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def get_api_health_details() -> Optional[Dict]:
    """Get detailed health information from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def submit_analysis(analysis_data: Dict[str, Any]) -> Optional[Dict]:
    """Submit analysis request to API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/analyze/sync",
            json=analysis_data,
            timeout=120  # Allow more time for analysis
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.Timeout:
        st.error("Request timed out. The analysis is taking longer than expected.")
        return None
    except Exception as e:
        st.error(f"Error communicating with API: {e}")
        return None


def submit_async_analysis(analysis_data: Dict[str, Any]) -> Optional[Dict]:
    """Submit async analysis request to API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/analyze",
            json=analysis_data,
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Error communicating with API: {e}")
        return None


def get_analysis_status(analysis_id: str) -> Optional[Dict]:
    """Get analysis status from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/analyze/{analysis_id}", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except:
        return None


def main():
    st.set_page_config(
        page_title="Bug Analysis Agent",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("🔍 Bug Analysis Agent")
    st.markdown("**User Review-Driven Log Triage & Analysis System**")

    # Check API health
    if not check_api_health():
        st.error("⚠️ API server is not available. Please start the FastAPI server first.")
        st.code("python api.py")
        st.stop()

    # Sidebar with system status
    with st.sidebar:
        st.header("📊 System Status")
        
        health_data = get_api_health_details()
        if health_data:
            status_emoji = "✅" if health_data["status"] == "healthy" else "⚠️"
            st.metric("API Status", f"{status_emoji} {health_data['status'].title()}")
            
            st.subheader("Components")
            for component, status in health_data["components"].items():
                emoji = "✅" if status == "ok" else "⚠️" if status == "unavailable" else "❌"
                st.text(f"{emoji} {component}: {status}")
            
            st.caption(f"Last checked: {datetime.fromisoformat(health_data['timestamp'].replace('Z', '+00:00')).strftime('%H:%M:%S')}")
        else:
            st.error("❌ Unable to get health status")

    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["🚀 New Analysis", "📋 Analysis History", "ℹ️ About"])

    with tab1:
        st.header("Submit Bug Report for Analysis")
        
        # Sample reports for easy testing
        sample_reports = {
            "Custom Report": {
                "username": "@chiyoED_67",
                "user_id": "2856398",
                "platform": "iOS",
                "os_version": "18.5 (22F76)",
                "app_version": "1.31.0",
                "log_url": "https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.31.0_prod_20250730T004620Z.log",
                "env": "prod",
                "feedback": "could u make all characters speak"
            },
            "UI Issues - @DjCyberZonex": {
                "username": "@DjCyberZonex",
                "user_id": "566286",
                "platform": "Android",
                "os_version": "R16NW.J400MUBS2ASC2",
                "app_version": "1.32.1",
                "log_url": "https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.32.1_prod_20250730T222525Z.log",
                "env": "prod",
                "feedback": "hi, i DjCyberzonex, user number is 566286. i have 2 issue and problem hoy must fix and adress.\n\n1: my follower icon and sekai roleplay is not showing, its bug.\n\n2: bring back the ability to make naked generated characters, because when i try to make a sexy beautiful succubus queen, this stupid message says 'something when wrong, please try againg later' every single time, its annoying.\n\ni cant do anything, fix it."
            },
            "Black Screen Issues - @kioro": {
                "username": "@kioro",
                "user_id": "1634229", 
                "platform": "Android",
                "os_version": "S3RQS32.20-42-10-1-3-17",
                "app_version": "1.32.1",
                "log_url": "https://sekai-app-log.s3.us-east-1.amazonaws.com/Sekai_v1.32.1_prod_20250730T170424Z.log",
                "env": "prod",
                "feedback": "each time I finish an episode it turns into a black screen, I have my episodes but I can only see the if I click the arrow and then go back to my episode. My notifications is also a black screen, and then another problem with my episodes is that whenever I look at the episodes the numbers on the episodes are all wrong and they do fix themselves eventually but it's just annoying"
            }
        }
        
        # Sample selection
        st.subheader("📝 Choose a Sample Report or Create Custom")
        selected_sample = st.selectbox(
            "Select a sample report to analyze:",
            list(sample_reports.keys()),
            help="Choose a predefined report or 'Custom Report' to enter your own data"
        )
        
        with st.form("bug_report_form"):
            col1, col2 = st.columns(2)
            
            # Get selected sample data
            sample_data = sample_reports[selected_sample]
            
            with col1:
                st.subheader("User Information")
                username = st.text_input("Username", value=sample_data["username"], help="User's username or handle")
                user_id = st.text_input("User ID", value=sample_data["user_id"], help="Unique user identifier")
                
                # Set platform index based on sample data
                platform_options = ["iOS", "Android", "Web"]
                platform_index = platform_options.index(sample_data["platform"]) if sample_data["platform"] in platform_options else 0
                platform = st.selectbox("Platform", platform_options, index=platform_index, help="Platform where the issue occurred")
                
                os_version = st.text_input("OS Version", value=sample_data["os_version"], help="Operating system version")
                app_version = st.text_input("App Version", value=sample_data["app_version"], help="Application version")
                
            with col2:
                st.subheader("Report Details")
                log_url = st.text_input(
                    "Log URL", 
                    value=sample_data["log_url"],
                    help="URL to the log file"
                )
                
                # Set environment index based on sample data
                env_options = ["prod", "staging", "dev"]
                env_index = env_options.index(sample_data["env"]) if sample_data["env"] in env_options else 0
                env = st.selectbox("Environment", env_options, index=env_index, help="Environment where the issue occurred")
                
                feedback = st.text_area(
                    "User Feedback", 
                    value=sample_data["feedback"],
                    height=150,
                    help="Description of the issue or feature request"
                )
            
            st.subheader("Analysis Options")
            col3, col4 = st.columns(2)
            with col3:
                context_lines = st.number_input("Context Lines", min_value=1, max_value=50, value=10, 
                                              help="Number of log lines to include around each error for general context")
                request_id_context_lines = st.number_input("Request ID Context Lines", min_value=1, max_value=50, value=5,
                                                          help="Number of lines to scan around errors for request IDs")
                time_window = st.number_input("Time Window (minutes)", min_value=1, max_value=2880, value=10,  # 10 minutes default
                                            help="Time window for correlating backend logs")
            with col4:
                generate_csv = st.checkbox("Generate CSV Report", value=True, 
                                         help="Generate CSV file with correlation data")
                analysis_mode = st.radio("Analysis Mode", ["Synchronous", "Asynchronous"],
                                        help="Sync: wait for results, Async: submit and check later")

            submitted = st.form_submit_button("🔍 Analyze Bug Report", type="primary")

        if submitted:
            # Validate inputs
            if not all([username, user_id, platform, os_version, app_version, log_url, env, feedback]):
                st.error("Please fill in all required fields")
                st.stop()

            # Prepare analysis data
            analysis_data = {
                "username": username,
                "user_id": user_id,
                "platform": platform,
                "os_version": os_version,
                "app_version": app_version,
                "log_url": log_url,
                "env": env,
                "feedback": feedback,
                "context_lines": context_lines,
                "request_id_context_lines": request_id_context_lines,
                "time_window_minutes": time_window,
                "generate_csv": generate_csv
            }

            if analysis_mode == "Synchronous":
                with st.spinner("🔄 Analyzing bug report... This may take a few minutes."):
                    result = submit_analysis(analysis_data)
                
                if result:
                    st.success("✅ Analysis completed!")
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.subheader("📊 Analysis Results")
                        if result.get("result"):
                            st.text_area("Analysis Summary", result["result"], height=400)
                        else:
                            st.error("No analysis result returned")
                    
                    with col2:
                        st.subheader("📋 Analysis Details")
                        st.text(f"Analysis ID: {result.get('analysis_id', 'N/A')}")
                        st.text(f"Status: {result.get('status', 'N/A')}")
                        st.text(f"Created: {result.get('created_at', 'N/A')}")
                        st.text(f"Completed: {result.get('completed_at', 'N/A')}")
                        
                        # CSV Download Button
                        if result.get("csv_file"):
                            csv_filename = os.path.basename(result["csv_file"])
                            csv_url = f"{API_BASE_URL}/download-csv/{csv_filename}"
                            
                            st.success("📄 CSV correlation report generated!")
                            
                            # Direct download button using streamlit's download_button
                            try:
                                csv_response = requests.get(csv_url)
                                if csv_response.status_code == 200:
                                    st.download_button(
                                        label="📥 Download CSV Report",
                                        data=csv_response.content,
                                        file_name=csv_filename,
                                        mime="text/csv",
                                        key="download_csv_sync",
                                        help="Download the detailed correlation data as CSV"
                                    )
                                else:
                                    st.error("Failed to fetch CSV file")
                                    st.markdown(f"📄 [Download CSV Report (fallback)]({csv_url})")
                            except Exception as e:
                                st.error(f"Error fetching CSV: {e}")
                                st.markdown(f"📄 [Download CSV Report (fallback)]({csv_url})")
                        
                        if result.get("error"):
                            st.error(f"Error: {result['error']}")

            else:  # Asynchronous
                with st.spinner("🚀 Submitting analysis request..."):
                    result = submit_async_analysis(analysis_data)
                
                if result:
                    st.success("✅ Analysis submitted!")
                    st.info(f"Analysis ID: {result['analysis_id']}")
                    st.info("Check the 'Analysis History' tab to monitor progress.")
                    
                    # Store in session state for tracking
                    if 'analysis_jobs' not in st.session_state:
                        st.session_state.analysis_jobs = []
                    st.session_state.analysis_jobs.append(result['analysis_id'])

    with tab2:
        st.header("📋 Analysis History")
        
        # Show jobs from session state
        if 'analysis_jobs' in st.session_state and st.session_state.analysis_jobs:
            st.subheader("Your Analysis Jobs")
            
            for job_id in st.session_state.analysis_jobs:
                with st.expander(f"Analysis: {job_id}"):
                    if st.button(f"Refresh Status", key=f"refresh_{job_id}"):
                        st.rerun()
                    
                    job_status = get_analysis_status(job_id)
                    if job_status:
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            st.text(f"Status: {job_status.get('status', 'Unknown')}")
                            st.text(f"Created: {job_status.get('created_at', 'N/A')}")
                            if job_status.get('completed_at'):
                                st.text(f"Completed: {job_status.get('completed_at', 'N/A')}")
                        
                        with col2:
                            if job_status.get('status') == 'completed' and job_status.get('result'):
                                st.download_button(
                                    "📄 Download Results",
                                    data=job_status['result'],
                                    file_name=f"analysis_{job_id}.txt",
                                    mime="text/plain"
                                )
                            
                            # CSV Download for async jobs
                            if job_status.get('csv_file'):
                                csv_filename = os.path.basename(job_status['csv_file'])
                                csv_url = f"{API_BASE_URL}/download-csv/{csv_filename}"
                                
                                st.info("📄 CSV correlation report available")
                                
                                try:
                                    csv_response = requests.get(csv_url)
                                    if csv_response.status_code == 200:
                                        st.download_button(
                                            label="📥 Download CSV Report",
                                            data=csv_response.content,
                                            file_name=csv_filename,
                                            mime="text/csv",
                                            key=f"download_csv_{job_id}",
                                            help="Download the detailed correlation data as CSV"
                                        )
                                    else:
                                        st.error("Failed to fetch CSV file")
                                        st.markdown(f"📄 [Download CSV Report (fallback)]({csv_url})")
                                except Exception as e:
                                    st.error(f"Error fetching CSV: {e}")
                                    st.markdown(f"📄 [Download CSV Report (fallback)]({csv_url})")
                        
                        if job_status.get('result'):
                            st.subheader("Results")
                            st.text_area("Analysis Result", job_status['result'], height=300, key=f"result_{job_id}")
                        
                        if job_status.get('error'):
                            st.error(f"Error: {job_status['error']}")
                    else:
                        st.warning("Unable to get status for this analysis")
        else:
            st.info("No analysis jobs yet. Submit a report in the 'New Analysis' tab.")

        # Manual status check
        st.subheader("🔍 Check Analysis Status")
        analysis_id_input = st.text_input("Enter Analysis ID")
        if st.button("Get Status") and analysis_id_input:
            job_status = get_analysis_status(analysis_id_input)
            if job_status:
                st.json(job_status)
            else:
                st.error("Analysis not found or API error")

    with tab3:
        st.header("ℹ️ About Bug Analysis Agent")
        
        st.markdown("""
        ### 🎯 Purpose
        This system performs automated analysis of user bug reports by:
        - Downloading and scanning frontend application logs
        - Correlating with backend CloudWatch logs
        - Using GPT-4 for intelligent analysis and recommendations
        
        ### 🏗️ Architecture
        - **Frontend**: Streamlit web interface (this app)
        - **Backend**: FastAPI REST API server
        - **Analysis Engine**: Automated log scanning and correlation
        - **AI**: GPT-powered issue classification and recommendations
        
        ### 🚀 How to Use
        1. Choose a sample report or select "Custom Report" to enter your own data
        2. Review and modify the bug report details as needed
        3. Choose analysis options (context lines, time window, etc.)
        4. Submit for analysis (sync or async)
        5. Review the results and download CSV correlation data
        
        ### 📝 Available Sample Reports
        - **UI Issues**: Real user report about follower icons and character generation problems
        - **Black Screen Issues**: User experiencing display problems with episodes and notifications
        - **Custom Report**: Default template for creating your own analysis
        
        ### 📊 Features
        - **Health Monitoring**: Real-time system component status
        - **Async Processing**: Submit long-running analyses in background
        - **CSV Export**: Download correlation data for further analysis
        - **Error Correlation**: Link frontend and backend errors automatically
        - **Sample Reports**: Pre-loaded real user reports for testing and demonstration
        
        ### 🔧 Technical Details
        - **Frontend Logs**: Downloaded from S3 URLs
        - **Backend Logs**: Retrieved from AWS CloudWatch
        - **AI Analysis**: GPT-4 powered insights and recommendations
        - **Export**: CSV files with detailed correlation data
        - **Configurable Context**: Adjustable context windows for both general log analysis and request ID scanning
        """)

        # API Documentation link
        st.subheader("🔗 API Documentation")
        st.markdown(f"[View FastAPI Docs]({API_BASE_URL}/docs)")
        
        # Quick API test
        if st.button("🧪 Test API Connection"):
            try:
                response = requests.get(f"{API_BASE_URL}/")
                if response.status_code == 200:
                    st.success("✅ API connection successful!")
                    st.json(response.json())
                else:
                    st.error(f"❌ API returned status {response.status_code}")
            except Exception as e:
                st.error(f"❌ Connection failed: {e}")


if __name__ == "__main__":
    main() 