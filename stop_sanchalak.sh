#!/bin/bash

# Sanchalak Stop Script
# Stops all servers: EFR, Scheme, Chat API, and Frontend

echo "🛑 Stopping SANCHALAK Services..."
echo "================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${2}${1}${NC}"
}

# Function to kill process on port
kill_port() {
    if lsof -ti:$1 > /dev/null 2>&1; then
        print_status "🔄 Stopping service on port $1..." $YELLOW
        lsof -ti:$1 | xargs kill -9 2>/dev/null || true
        sleep 1
        print_status "✅ Service on port $1 stopped" $GREEN
    else
        print_status "ℹ️  No service running on port $1" $YELLOW
    fi
}

# Stop all services
kill_port 3000  # Frontend
kill_port 8003  # Chat API
kill_port 8002  # Scheme Server
kill_port 8001  # EFR Server

# Clean up PID files if they exist
if [ -d "logs" ]; then
    rm -f logs/*.pid
    print_status "🧹 Cleaned up PID files" $GREEN
fi

echo ""
print_status "✅ All SANCHALAK services stopped!" $GREEN 