#!/bin/bash

# Start PM-KISAN Chat Data Extraction API Server

echo "🚀 Starting PM-KISAN Chat Data Extraction API Server..."

# Check if virtual environment exists
if [ ! -d "dev_venv" ]; then
    echo "❌ Virtual environment 'dev_venv' not found. Please set it up first."
    exit 1
fi

# Activate virtual environment
source dev_venv/bin/activate

# Install required dependencies if not already installed
echo "📦 Installing/updating dependencies..."
pip install fastapi uvicorn requests

# Start the server
echo "🌐 Starting server on http://localhost:8003"
echo "📖 API docs will be available at http://localhost:8003/docs"
echo "🛑 Press Ctrl+C to stop the server"
echo ""

python3 src/schemabot/run_chat_server.py 