#!/bin/bash
# Sanchalak Monorepo Setup Script

echo "🌾 Setting up Sanchalak Monorepo..."

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
npm install

# Install concurrently for running both servers
echo "📦 Installing concurrently..."
npm install concurrently --save

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend && npm install && cd ..

# Create environment files if they don't exist
if [ ! -f .env.local ]; then
    echo "🔧 Creating frontend environment file..."
    cp .env.local.example .env.local 2>/dev/null || echo "NEXT_PUBLIC_GRAPHQL_URL=http://localhost:3001/graphql
NEXT_PUBLIC_BACKEND_URL=http://localhost:3001" > .env.local
fi

if [ ! -f backend/.env ]; then
    echo "🔧 Creating backend environment file..."
    echo "# Azure Speech Service Configuration
AZURE_SPEECH_KEY=your-azure-speech-key-here
AZURE_SPEECH_REGION=your-azure-region-here

# Server Configuration  
PORT=3001
NODE_ENV=development

# CORS Configuration
CORS_ORIGIN=http://localhost:3000

# File Upload Configuration
MAX_FILE_SIZE=25000000
UPLOAD_DIR=./public/audio" > backend/.env
fi

echo "✅ Setup complete!"
echo ""
echo "🚀 Next steps:"
echo "1. Configure your Azure Speech Service keys in backend/.env"
echo "2. Run 'npm run dev:all' to start both frontend and backend"
echo "3. Open http://localhost:3000 in your browser"
echo ""
echo "📚 Available commands:"
echo "  npm run dev          - Start frontend only"
echo "  npm run dev:backend  - Start backend only" 
echo "  npm run dev:all      - Start both frontend and backend"
echo "  npm run build:all    - Build both projects"
echo "  npm run start:all    - Start both in production mode"
