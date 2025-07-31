#!/usr/bin/env python3
"""
Script to start the Streamlit frontend
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    print("🎨 Starting Bug Analysis Agent Frontend...")
    print("🌐 Frontend will be available at: http://localhost:8501")
    print("\nMake sure the API server is running first!")
    print("Press Ctrl+C to stop the frontend")
    print("-" * 50)
    
    try:
        # Run streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port=8501",
            "--server.address=0.0.0.0",
            "--server.headless=false"
        ])
    except KeyboardInterrupt:
        print("\n👋 Frontend stopped by user") 