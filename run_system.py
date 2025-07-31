#!/usr/bin/env python3
"""
Script to start both backend and frontend simultaneously
"""

import subprocess
import sys
import time
import signal
import os
from multiprocessing import Process

def start_backend():
    """Start the FastAPI backend"""
    print("🚀 Starting Backend API Server...")
    os.system(f"{sys.executable} start_backend.py")

def start_frontend():
    """Start the Streamlit frontend"""
    # Wait a bit for backend to start
    time.sleep(3)
    print("🎨 Starting Frontend...")
    os.system(f"{sys.executable} start_frontend.py")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n👋 Shutting down Bug Analysis Agent...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🔍 Bug Analysis Agent - Complete System Startup")
    print("=" * 50)
    print("🚀 Backend API: http://localhost:8000")
    print("🎨 Frontend UI: http://localhost:8501")
    print("📚 API Docs: http://localhost:8000/docs")
    print("=" * 50)
    print("\nStarting both services...")
    print("Press Ctrl+C to stop both services")
    print("-" * 50)
    
    try:
        # Start backend in a separate process
        backend_process = Process(target=start_backend)
        backend_process.start()
        
        # Start frontend in a separate process
        frontend_process = Process(target=start_frontend)
        frontend_process.start()
        
        # Wait for both processes
        backend_process.join()
        frontend_process.join()
        
    except KeyboardInterrupt:
        print("\n👋 Stopping all services...")
        if 'backend_process' in locals():
            backend_process.terminate()
        if 'frontend_process' in locals():
            frontend_process.terminate()
    except Exception as e:
        print(f"❌ Error: {e}")
        if 'backend_process' in locals():
            backend_process.terminate()
        if 'frontend_process' in locals():
            frontend_process.terminate() 