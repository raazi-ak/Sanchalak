#!/bin/bash

# Sanchalak Cleanup Script
# This script provides options to clean up the entire Docker environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -v, --volumes       Remove Docker volumes (WARNING: This will delete all data!)"
    echo "  -i, --images        Remove Docker images"
    echo "  -n, --networks      Remove Docker networks"
    echo "  -c, --cache         Clear Docker build cache"
    echo "  -a, --all           Remove everything (volumes, images, networks, cache)"
    echo "  --force             Skip confirmation prompts"
    echo ""
    echo "Examples:"
    echo "  $0                  # Basic cleanup (stop containers)"
    echo "  $0 -i               # Stop containers and remove images"
    echo "  $0 -a               # Full cleanup (WARNING: Removes all data!)"
    echo "  $0 -v -i --force    # Remove volumes and images without confirmation"
}

# Default options
REMOVE_VOLUMES=false
REMOVE_IMAGES=false
REMOVE_NETWORKS=false
CLEAR_CACHE=false
FORCE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -v|--volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        -i|--images)
            REMOVE_IMAGES=true
            shift
            ;;
        -n|--networks)
            REMOVE_NETWORKS=true
            shift
            ;;
        -c|--cache)
            CLEAR_CACHE=true
            shift
            ;;
        -a|--all)
            REMOVE_VOLUMES=true
            REMOVE_IMAGES=true
            REMOVE_NETWORKS=true
            CLEAR_CACHE=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Confirmation function
confirm() {
    if [ "$FORCE" = true ]; then
        return 0
    fi
    
    echo -e "${YELLOW}$1${NC}"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

print_status "Starting Sanchalak cleanup process..."

# Step 1: Stop and remove containers
print_status "Stopping all containers..."
if docker-compose ps -q | grep -q .; then
    docker-compose down
    print_success "Containers stopped and removed"
else
    print_warning "No running containers found"
fi

# Step 2: Remove volumes if requested
if [ "$REMOVE_VOLUMES" = true ]; then
    if confirm "⚠️  WARNING: This will delete ALL data including databases, logs, and uploads!"; then
        print_status "Removing Docker volumes..."
        
        # Remove project volumes
        docker volume ls -q --filter name=sanchalak | while read volume; do
            if [ ! -z "$volume" ]; then
                docker volume rm "$volume" 2>/dev/null && print_success "Removed volume: $volume" || print_warning "Failed to remove volume: $volume"
            fi
        done
        
        # Remove any dangling volumes
        DANGLING_VOLUMES=$(docker volume ls -qf dangling=true)
        if [ ! -z "$DANGLING_VOLUMES" ]; then
            echo "$DANGLING_VOLUMES" | xargs docker volume rm 2>/dev/null && print_success "Removed dangling volumes"
        fi
        
        print_success "Volume cleanup completed"
    else
        print_warning "Volume removal skipped"
    fi
fi

# Step 3: Remove images if requested
if [ "$REMOVE_IMAGES" = true ]; then
    if confirm "This will remove all Sanchalak Docker images. Continue?"; then
        print_status "Removing Docker images..."
        
        # Remove project images
        SANCHALAK_IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep sanchalak)
        if [ ! -z "$SANCHALAK_IMAGES" ]; then
            echo "$SANCHALAK_IMAGES" | xargs docker rmi -f 2>/dev/null && print_success "Removed Sanchalak images"
        fi
        
        # Remove dangling images
        DANGLING_IMAGES=$(docker images -qf dangling=true)
        if [ ! -z "$DANGLING_IMAGES" ]; then
            echo "$DANGLING_IMAGES" | xargs docker rmi -f 2>/dev/null && print_success "Removed dangling images"
        fi
        
        print_success "Image cleanup completed"
    else
        print_warning "Image removal skipped"
    fi
fi

# Step 4: Remove networks if requested
if [ "$REMOVE_NETWORKS" = true ]; then
    print_status "Removing Docker networks..."
    
    # Remove project networks
    SANCHALAK_NETWORKS=$(docker network ls --format "{{.Name}}" | grep sanchalak)
    if [ ! -z "$SANCHALAK_NETWORKS" ]; then
        echo "$SANCHALAK_NETWORKS" | xargs docker network rm 2>/dev/null && print_success "Removed Sanchalak networks"
    fi
    
    print_success "Network cleanup completed"
fi

# Step 5: Clear build cache if requested
if [ "$CLEAR_CACHE" = true ]; then
    if confirm "This will clear Docker build cache. Continue?"; then
        print_status "Clearing Docker build cache..."
        docker builder prune -af
        print_success "Build cache cleared"
    else
        print_warning "Cache clearing skipped"
    fi
fi

# Step 6: Clean up any remaining Docker resources
print_status "Cleaning up remaining Docker resources..."
docker system prune -f
print_success "System cleanup completed"

# Final status
print_success "🎉 Cleanup process completed!"

# Show what was cleaned
echo ""
print_status "Summary of actions performed:"
echo "  ✅ Stopped and removed containers"
[ "$REMOVE_VOLUMES" = true ] && echo "  ✅ Removed volumes and data"
[ "$REMOVE_IMAGES" = true ] && echo "  ✅ Removed Docker images"
[ "$REMOVE_NETWORKS" = true ] && echo "  ✅ Removed Docker networks"
[ "$CLEAR_CACHE" = true ] && echo "  ✅ Cleared build cache"
echo "  ✅ Cleaned up system resources"

echo ""
print_status "To restart the system, run: ./scripts/run.sh" 