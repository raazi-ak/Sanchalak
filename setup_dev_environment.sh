#!/bin/bash

# Sanchalak Development Environment Setup Script
# This script sets up a complete development environment for the Sanchalak project

set -e  # Exit on any error

echo "🚀 Setting up Sanchalak Development Environment"
echo "=============================================="

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

# Check if Python 3.8+ is installed
check_python() {
    print_status "Checking Python version..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
        PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            print_success "Python $PYTHON_VERSION found"
            PYTHON_CMD="python3"
        else
            print_error "Python 3.8+ required, found $PYTHON_VERSION"
            exit 1
        fi
    elif command -v python &> /dev/null; then
        PYTHON_VERSION=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MAJOR=$(python -c 'import sys; print(sys.version_info[0])')
        PYTHON_MINOR=$(python -c 'import sys; print(sys.version_info[1])')
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            print_success "Python $PYTHON_VERSION found"
            PYTHON_CMD="python"
        else
            print_error "Python 3.8+ required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python not found. Please install Python 3.8+"
        exit 1
    fi
}

# Check if pip is installed
check_pip() {
    print_status "Checking pip..."
    if command -v pip3 &> /dev/null; then
        print_success "pip3 found"
        PIP_CMD="pip3"
    elif command -v pip &> /dev/null; then
        print_success "pip found"
        PIP_CMD="pip"
    else
        print_error "pip not found. Please install pip"
        exit 1
    fi
}

# Create virtual environment
create_venv() {
    print_status "Creating virtual environment..."
    if [ -d "dev_venv" ]; then
        print_warning "Virtual environment already exists. Removing old one..."
        rm -rf dev_venv
    fi
    
    $PYTHON_CMD -m venv dev_venv
    print_success "Virtual environment created"
}

# Activate virtual environment
activate_venv() {
    print_status "Activating virtual environment..."
    source dev_venv/bin/activate
    print_success "Virtual environment activated"
}

# Upgrade pip
upgrade_pip() {
    print_status "Upgrading pip..."
    $PIP_CMD install --upgrade pip
    print_success "pip upgraded"
}

# Install requirements
install_requirements() {
    print_status "Installing production requirements..."
    $PIP_CMD install -r requirements.txt
    
    print_status "Installing development requirements..."
    $PIP_CMD install -r requirements-dev.txt
    
    print_success "All requirements installed"
}

# Install spaCy model
install_spacy_model() {
    print_status "Installing spaCy English model..."
    python -m spacy download en_core_web_sm
    print_success "spaCy model installed"
}

# Create .env file if it doesn't exist
setup_env() {
    print_status "Setting up environment variables..."
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# Sanchalak Environment Configuration

# Database Configuration
MONGODB_URI=mongodb://localhost:27017/sanchalak
POSTGRES_URI=postgresql://localhost:5432/sanchalak

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# API Keys (replace with your actual keys)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_API_KEY=your_google_api_key_here

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/sanchalak.log

# Admin Key
ADMIN_KEY=thisisourhardworksopleasedontcopy

# Development Settings
ENVIRONMENT=development
EOF
        print_success ".env file created"
    else
        print_warning ".env file already exists"
    fi
}

# Create logs directory
create_logs_dir() {
    print_status "Creating logs directory..."
    mkdir -p logs
    print_success "Logs directory created"
}

# Install pre-commit hooks
setup_pre_commit() {
    print_status "Setting up pre-commit hooks..."
    pre-commit install
    print_success "Pre-commit hooks installed"
}

# Test installation
test_installation() {
    print_status "Testing installation..."
    
    # Test Python imports
    python -c "
import fastapi
import uvicorn
import pydantic
import langchain
import torch
import transformers
import streamlit
import sqlalchemy
import redis
import pymongo
print('✅ All core packages imported successfully')
"
    
    print_success "Installation test passed"
}

# Display next steps
show_next_steps() {
    echo ""
    echo "🎉 Setup Complete!"
    echo "=================="
    echo ""
    echo "Next steps:"
    echo "1. Activate the virtual environment:"
    echo "   source dev_venv/bin/activate"
    echo ""
    echo "2. Update your .env file with actual API keys"
    echo ""
    echo "3. Start the development servers:"
    echo "   ./start_sanchalak.sh"
    echo ""
    echo "4. Or start individual services:"
    echo "   ./start_efr_server.sh"
    echo "   ./start_chat_server.sh"
    echo "   ./start_chat_frontend.sh"
    echo ""
    echo "5. Run tests:"
    echo "   pytest"
    echo ""
    echo "6. Check code quality:"
    echo "   black src/"
    echo "   flake8 src/"
    echo "   mypy src/"
    echo ""
    echo "Documentation:"
    echo "- Main README: SANCHALAK_README.md"
    echo "- CLI Chat: src/schemabot/CLI_CHAT_README.md"
    echo "- GraphQL API: src/schemabot/GRAPHQL_API.md"
    echo ""
}

# Main execution
main() {
    check_python
    check_pip
    create_venv
    activate_venv
    upgrade_pip
    install_requirements
    install_spacy_model
    setup_env
    create_logs_dir
    setup_pre_commit
    test_installation
    show_next_steps
}

# Run main function
main 