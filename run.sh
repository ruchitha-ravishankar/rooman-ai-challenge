#!/usr/bin/env bash
# ==============================================================================
# VeriCite AI - One-Command Startup Script
# Rooman AI Challenge Submission
# ==============================================================================

set -e

echo "========================================================"
echo "   VeriCite AI: Research Agent with Strict Citations    "
echo "        Rooman AI Challenge - Selection Round           "
echo "========================================================"

# Step 1: Check Python installation
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "Error: Python 3 is required but not found in PATH."
        exit 1
    fi
fi

# Step 2: Virtual environment setup
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    $PYTHON_CMD -m venv .venv
fi

# Activate environment
source .venv/bin/activate

# Step 3: Install dependencies if not already installed
echo "Checking dependencies..."
pip install -r requirements.txt --quiet

# Step 4: Handle flags (CLI vs Web Server)
if [ "$1" == "--cli" ]; then
    echo "Starting interactive Terminal CLI..."
    python cli.py
elif [ "$1" == "--benchmark" ]; then
    echo "Running automated benchmark suite..."
    python cli.py --benchmark
elif [ "$1" == "--test" ]; then
    echo "Running pytest test suite..."
    pytest tests/ -v
else
    echo ""
    echo "Starting FastAPI Server & Web Workbench UI..."
    echo "Web Workbench URL: http://localhost:8000"
    echo "Interactive API Docs: http://localhost:8000/docs"
    echo "Press Ctrl+C to stop the server."
    echo ""
    uvicorn app.api.server:app --host 0.0.0.0 --port 8000
fi
