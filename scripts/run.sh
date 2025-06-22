#!/bin/bash

# Sanchalak Docker Run Script
set -e

echo "🚀 Starting Sanchalak Services..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Copying from env.example..."
    cp env.example .env
    echo "📝 Please edit .env file with your configuration before running again."
    exit 1
fi

# Start services
echo "🔄 Starting all services..."
docker-compose up -d

echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo "🔍 Checking service health..."
docker-compose ps

echo "✅ Sanchalak is running!"
echo ""
echo "📊 Service URLs:"
echo "   • Telegram Bot Health: http://localhost:8080"
echo "   • Orchestrator: http://localhost:8000"
echo "   • EFR Database: http://localhost:8001"
echo "   • Form Filler: http://localhost:8002"
echo "   • Status Tracker: http://localhost:8003"
echo "   • Monitoring: http://localhost:8084"
echo "   • MongoDB: localhost:27017"
echo ""
echo "📝 To view logs: docker-compose logs -f [service-name]"
echo "🛑 To stop: docker-compose down" 