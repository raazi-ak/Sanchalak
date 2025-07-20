@echo off
REM Sanchalak Monorepo Setup Script for Windows

echo 🌾 Setting up Sanchalak Monorepo...

REM Install frontend dependencies
echo 📦 Installing frontend dependencies...
call npm install

REM Install concurrently for running both servers  
echo 📦 Installing concurrently...
call npm install concurrently --save

REM Install backend dependencies
echo 📦 Installing backend dependencies...
cd backend && call npm install && cd ..

REM Create environment files if they don't exist
if not exist .env.local (
    echo 🔧 Creating frontend environment file...
    echo NEXT_PUBLIC_GRAPHQL_URL=http://localhost:3001/graphql> .env.local
    echo NEXT_PUBLIC_BACKEND_URL=http://localhost:3001>> .env.local
)

if not exist backend\.env (
    echo 🔧 Creating backend environment file...
    echo # Azure Speech Service Configuration> backend\.env
    echo AZURE_SPEECH_KEY=your-azure-speech-key-here>> backend\.env
    echo AZURE_SPEECH_REGION=your-azure-region-here>> backend\.env
    echo.>> backend\.env
    echo # Server Configuration>> backend\.env
    echo PORT=3001>> backend\.env
    echo NODE_ENV=development>> backend\.env
    echo.>> backend\.env
    echo # CORS Configuration>> backend\.env
    echo CORS_ORIGIN=http://localhost:3000>> backend\.env
    echo.>> backend\.env
    echo # File Upload Configuration>> backend\.env
    echo MAX_FILE_SIZE=25000000>> backend\.env
    echo UPLOAD_DIR=./public/audio>> backend\.env
)

echo ✅ Setup complete!
echo.
echo 🚀 Next steps:
echo 1. Configure your Azure Speech Service keys in backend\.env
echo 2. Run 'npm run dev:all' to start both frontend and backend
echo 3. Open http://localhost:3000 in your browser
echo.
echo 📚 Available commands:
echo   npm run dev          - Start frontend only
echo   npm run dev:backend  - Start backend only
echo   npm run dev:all      - Start both frontend and backend
echo   npm run build:all    - Build both projects
echo   npm run start:all    - Start both in production mode

pause
