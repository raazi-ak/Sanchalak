#!/bin/bash

# Sanchalak Docker Build Script
set -e

echo "🏗️  Building Sanchalak Docker Images..."

# Build all services
echo "📦 Building Telegram Bot..."
docker build -t sanchalak-telegram-bot ./components/telegram-bot -f ./components/telegram-bot/dockerfiles/Dockerfile

echo "📦 Building Orchestrator..."
docker build -t sanchalak-orchestrator ./components/orchestrator -f ./components/orchestrator/dockerfiles/Dockerfile

echo "📦 Building EFR Database..."
docker build -t sanchalak-efr-db ./components/efr-db -f ./components/efr-db/dockerfiles/Dockerfile

echo "📦 Building Form Filler..."
docker build -t sanchalak-form-filler ./components/form-filler -f ./components/form-filler/dockerfiles/Dockerfile

echo "📦 Building Status Tracker..."
docker build -t sanchalak-status-tracker ./components/status-tracker -f ./components/status-tracker/dockerfiles/Dockerfile

echo "📦 Building Monitoring..."
docker build -t sanchalak-monitoring ./components/monitoring -f ./components/monitoring/dockerfiles/Dockerfile

echo "✅ All images built successfully!"

# Show images
echo "📋 Built images:"
docker images | grep sanchalak 