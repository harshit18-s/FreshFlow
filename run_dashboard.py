"""
FreshFlow AI — Standalone Headless Dashboard Launcher
=====================================================
Configures python paths and launches Streamlit application programmatically
in headless mode on port 8501.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add project root directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ["PYTHONPATH"] = str(ROOT_DIR)

def main():
    app_path = ROOT_DIR / "src" / "dashboard" / "app.py"
    
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port=8501",
        "--server.headless=true",
        "--server.address=0.0.0.0",
        "--browser.gatherUsageStats=false"
    ]
    
    print("Starting FreshFlow AI Control Tower on http://localhost:8501...")
    subprocess.run(cmd, cwd=str(ROOT_DIR))

if __name__ == "__main__":
    main()
