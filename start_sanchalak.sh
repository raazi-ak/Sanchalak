#!/bin/bash

# Sanchalak Master Startup Script
# Starts all servers: EFR, Scheme, Chat API, and Frontend

echo "🌾 SANCHALAK - PM-KISAN Conversational AI System"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${2}${1}${NC}"
}

# Function to check if a port is in use
check_port() {
    lsof -ti:$1 > /dev/null 2>&1
}

# Function to kill process on port
kill_port() {
    if check_port $1; then
        print_status "🔄 Killing existing process on port $1..." $YELLOW
        lsof -ti:$1 | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

# Function to wait for server to be ready
wait_for_server() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "⏳ Waiting for $name to be ready..." $YELLOW
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s $url/health > /dev/null 2>&1; then
            print_status "✅ $name is ready!" $GREEN
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_status "❌ $name failed to start within timeout" $RED
    return 1
}

# Cleanup function
cleanup() {
    print_status "\n🛑 Shutting down all services..." $YELLOW
    kill_port 8001  # EFR Server
    kill_port 8002  # Scheme Server  
    kill_port 8003  # Chat API
    kill_port 3000  # Frontend
    print_status "✅ All services stopped" $GREEN
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

print_status "🔍 Checking prerequisites..." $BLUE

# Check Python virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    if [ -d "dev_venv" ]; then
        print_status "🐍 Activating Python virtual environment..." $YELLOW
        source dev_venv/bin/activate
    else
        print_status "❌ Virtual environment 'dev_venv' not found" $RED
        exit 1
    fi
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    print_status "❌ Node.js is not installed" $RED
    exit 1
fi

# Check npm
if ! command -v npm &> /dev/null; then
    print_status "❌ npm is not installed" $RED  
    exit 1
fi

print_status "✅ Prerequisites check passed" $GREEN
echo ""

# Kill any existing processes on our ports
print_status "🧹 Cleaning up existing processes..." $BLUE
kill_port 8001
kill_port 8002
kill_port 8003
kill_port 3000

echo ""
print_status "🚀 Starting Sanchalak Services..." $BLUE
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs

# 1. Start EFR Server (Port 8001)
print_status "1️⃣  Starting EFR Server (Port 8001)..." $PURPLE
cd src/efr_server
uvicorn main:app --host 0.0.0.0 --port 8001 > ../../logs/efr_server.log 2>&1 &
EFR_PID=$!
cd ../..

# 2. Start Scheme Server (Port 8002)  
print_status "2️⃣  Starting Scheme Server (Port 8002)..." $PURPLE
cd src/scheme_server
uvicorn scheme_backend:app --host 0.0.0.0 --port 8002 > ../../logs/scheme_server.log 2>&1 &
SCHEME_PID=$!
cd ../..

# 3. Start GraphQL Chat API Server (Port 8003)
print_status "3️⃣  Starting GraphQL Chat API Server (Port 8003)..." $PURPLE
cd src/schemabot
uvicorn api.graphql_server:app --host 0.0.0.0 --port 8003 > ../../logs/chat_server.log 2>&1 &
CHAT_PID=$!
cd ../..

# Wait for backend servers to be ready
echo ""
wait_for_server "http://localhost:8001" "EFR Server"
wait_for_server "http://localhost:8002" "Scheme Server"  
wait_for_server "http://localhost:8003" "GraphQL Chat API Server"

# 4. Install frontend dependencies if needed
print_status "4️⃣  Preparing Frontend..." $PURPLE
cd src/schemabot/frontend
if [ ! -d "node_modules" ]; then
    print_status "📦 Installing frontend dependencies..." $YELLOW
    npm install > ../../../logs/frontend_install.log 2>&1
fi

# 5. Start Frontend (Port 3000)
print_status "5️⃣  Starting Frontend (Port 3000)..." $PURPLE
npm run dev > ../../../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ../../..

# Wait a moment for frontend to start
sleep 5

echo ""
print_status "🎉 SANCHALAK IS READY!" $GREEN
echo ""
print_status "📊 SERVICE ENDPOINTS:" $CYAN
print_status "   🌐 Frontend:     http://localhost:3000" $CYAN
print_status "   🗄️  EFR Server:   http://localhost:8001" $CYAN  
print_status "   📋 Scheme Server: http://localhost:8002" $CYAN
print_status "   🤖 GraphQL Chat:  http://localhost:8003" $CYAN
echo ""
print_status "📚 API DOCUMENTATION:" $CYAN
print_status "   📖 EFR API Docs:    http://localhost:8001/docs" $CYAN
print_status "   📖 Scheme API Docs: http://localhost:8002/docs" $CYAN
print_status "   📖 GraphQL Docs:    http://localhost:8003/docs" $CYAN
print_status "   🎮 GraphQL Playground: http://localhost:8003/graphql" $CYAN
echo ""
print_status "📁 LOGS:" $CYAN
print_status "   📄 EFR Server:   logs/efr_server.log" $CYAN
print_status "   📄 Scheme Server: logs/scheme_server.log" $CYAN
print_status "   📄 Chat API:     logs/chat_server.log" $CYAN
print_status "   📄 Frontend:     logs/frontend.log" $CYAN
echo ""
print_status "💡 USAGE:" $YELLOW
print_status "   1. Open http://localhost:3000 in your browser" $YELLOW
print_status "   2. Start a conversation with the PM-KISAN assistant" $YELLOW
print_status "   3. Follow the conversational flow to collect farmer data" $YELLOW
print_status "   4. Try GraphQL Playground at http://localhost:8003/graphql" $YELLOW
print_status "   5. Press Ctrl+C to stop all services" $YELLOW
echo ""

# Store PIDs for cleanup
echo $EFR_PID > logs/efr_server.pid
echo $SCHEME_PID > logs/scheme_server.pid  
echo $CHAT_PID > logs/chat_server.pid
echo $FRONTEND_PID > logs/frontend.pid

# Keep script running and wait for interrupt
print_status "🔄 All services running. Press Ctrl+C to stop..." $BLUE
wait 