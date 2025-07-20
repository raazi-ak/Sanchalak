#!/bin/bash

echo "🚀 Starting Sanchalak Integrated UI with LangGraph Engine"
echo "=================================================="

# Function to cleanup background processes
cleanup() {
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $SCHEMABOT_PID 2>/dev/null
    exit 0
}

# Set trap to cleanup on exit
trap cleanup SIGINT SIGTERM

# Start the new UI backend (audio processing)
echo "🎵 Starting new UI backend (port 3001)..."
cd backend
npm run dev &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start the schemabot GraphQL server (LangGraph engine)
echo "🤖 Starting schemabot GraphQL server (port 8003)..."
cd ../schemabot/api
python graphql_server.py &
SCHEMABOT_PID=$!
cd ../../new_ui

# Wait a moment for schemabot to start
sleep 3

# Start the frontend
echo "🌐 Starting Next.js frontend (port 3000)..."
npm run dev

# Wait for user to stop
wait 