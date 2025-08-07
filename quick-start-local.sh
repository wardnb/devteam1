#!/bin/bash

echo "🤖 Quick Start - Local Development Setup"
echo "========================================"

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "Please run this script from the autonomous-dev-team directory"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if Redis is running
echo "Checking Redis..."
if ! pgrep -x "redis-server" > /dev/null; then
    echo "⚠️  Redis is not running. Starting Redis in background..."
    redis-server --daemonize yes --port 6379
    sleep 2
fi

# Check if Ollama is running
echo "Checking Ollama..."
if ! pgrep -x "ollama" > /dev/null; then
    echo "⚠️  Ollama is not running. Please start it manually:"
    echo "   ollama serve"
    echo ""
    echo "Then pull required models:"
    echo "   ollama pull llama3.1:8b"
    echo "   ollama pull codellama:13b"
    echo ""
    read -p "Press Enter when Ollama is running..."
fi

# Start the autonomous dev team
echo ""
echo "🚀 Starting Autonomous Development Team..."
echo "=========================================="
echo ""
echo "Available modes:"
echo "1. Interactive CLI (recommended for first run)"
echo "2. Example project"
echo "3. Web interface"
echo ""

read -p "Choose mode (1-3): " choice

case $choice in
    1)
        echo "Starting interactive CLI..."
        python main.py --mode interactive
        ;;
    2)
        echo "Starting example project..."
        python main.py --mode example
        ;;
    3)
        echo "Starting web interface on http://localhost:8000..."
        python -m uvicorn web_interface:app --host 0.0.0.0 --port 8000 --reload
        ;;
    *)
        echo "Invalid choice. Starting interactive CLI..."
        python main.py --mode interactive
        ;;
esac