#!/bin/bash

# PM-KISAN Chat Frontend Startup Script (Next.js)

echo "🌾 PM-KISAN Chat System"
echo "========================"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install npm first."
    exit 1
fi

# Navigate to frontend directory
cd src/schemabot/frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start the frontend
echo "🚀 Starting Next.js Chat Frontend..."
echo "📱 Frontend URL: http://localhost:3000"
echo "🔗 EFR Server URL: http://localhost:8001"
echo "🔗 Scheme Server URL: http://localhost:8002"
echo "🔗 Chat API URL: http://localhost:8003"
echo ""
echo "💡 Make sure all servers are running before using the frontend!"
echo "   1. EFR Server: ./start_efr_server.sh"
echo "   2. Scheme Server: cd src/scheme_server && python scheme_backend.py"
echo "   3. Chat API: ./start_chat_server.sh"
echo ""
echo "Press Ctrl+C to stop the frontend"
echo "=" * 60

npm run dev 