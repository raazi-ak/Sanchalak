#!/bin/bash

# Sanchalak Docker Shell Access Script

if [ $# -eq 0 ]; then
    echo "🐚 Sanchalak Container Shell Access"
    echo ""
    echo "Usage: $0 <service-name>"
    echo ""
    echo "Available services:"
    echo "  • telegram-bot"
    echo "  • orchestrator" 
    echo "  • efr-db"
    echo "  • form-filler"
    echo "  • status-tracker"
    echo "  • monitoring"
    echo "  • mongo"
    echo ""
    echo "Example: $0 telegram-bot"
    exit 1
fi

SERVICE=$1
CONTAINER_NAME="sanchalak-$SERVICE"

# Check if container exists and is running
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo "❌ Container $CONTAINER_NAME is not running"
    echo "🔄 Starting services first..."
    docker-compose up -d
    sleep 5
fi

echo "🐚 Accessing shell for $SERVICE..."

# Special case for mongo
if [ "$SERVICE" = "mongo" ]; then
    docker exec -it $CONTAINER_NAME mongosh -u admin -p sanchalak123 --authenticationDatabase admin
else
    docker exec -it $CONTAINER_NAME /bin/bash
fi 