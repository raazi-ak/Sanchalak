# 🌾 SANCHALAK - PM-KISAN Conversational AI System

A comprehensive conversational AI system for collecting farmer data for government schemes like PM-KISAN using LangGraph-powered intelligent conversations.

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+** with virtual environment `dev_venv`
- **Node.js 18+** and npm
- **Git** (for version control)

### One-Command Startup

```bash
# Start all services
./start_sanchalak.sh

# Stop all services  
./stop_sanchalak.sh
```

That's it! The system will automatically:
- ✅ Check prerequisites
- ✅ Activate Python virtual environment
- ✅ Clean up any existing processes
- ✅ Start all 4 services in correct order
- ✅ Wait for services to be ready
- ✅ Install frontend dependencies if needed
- ✅ Provide you with all access URLs

## 🏗️ System Architecture

### Services & Ports

| Service | Port | Purpose | API Docs |
|---------|------|---------|----------|
| **Frontend** | 3000 | Next.js Chat Interface | - |
| **EFR Server** | 8001 | Farmer Database (CRUD) | http://localhost:8001/docs |
| **Scheme Server** | 8002 | Scheme Definitions & Validation | http://localhost:8002/docs |
| **Chat API** | 8003 | LangGraph Conversation Engine | http://localhost:8003/docs |

### Data Flow
```
User → Frontend (3000) → Chat API (8003) → Scheme Server (8002) + EFR Server (8001)
```

## 🎯 Features

### 🤖 Conversational AI
- **LangGraph-powered** conversation flows
- **Multi-stage data collection** (Basic Info → Family → Exclusions → Special Provisions)
- **Progress tracking** with real-time updates
- **Quick options** for faster user interaction
- **Session management** with UUID-based sessions

### 🎨 Beautiful Frontend
- **Next.js + TypeScript** for modern web experience
- **Tailwind CSS** for responsive, beautiful UI
- **Real-time server status** monitoring
- **Auto-scrolling chat** interface
- **Progress visualization** with completion bars

### 🔧 Developer Features
- **Comprehensive logging** (logs/ directory)
- **Health check endpoints** for all services
- **API documentation** with Swagger UI
- **Hot reload** for development
- **Process management** with PID tracking

## 📊 Usage

1. **Start the system:**
   ```bash
   ./start_sanchalak.sh
   ```

2. **Open your browser:**
   - Go to http://localhost:3000
   - You'll see the PM-KISAN Chat Assistant

3. **Start a conversation:**
   - Click "🚀 Start Conversation" or type "Hello"
   - Follow the AI assistant through the data collection process
   - Use quick options or type responses naturally

4. **Monitor progress:**
   - See real-time progress bars in the sidebar
   - Track which stage you're currently in
   - View server status indicators

5. **Complete data collection:**
   - Finish all required fields across all stages
   - Download the collected farmer data as JSON
   - Data is automatically stored in the EFR database

## 📁 Project Structure

```
Sanchalak/
├── 🚀 start_sanchalak.sh          # Master startup script
├── 🛑 stop_sanchalak.sh           # Master stop script
├── 📁 src/
│   ├── 🗄️ efr_server/             # Farmer database API
│   ├── 📋 scheme_server/          # Scheme definitions API
│   ├── 🤖 schemabot/              # Chat conversation engine
│   │   ├── 🔗 api/                # FastAPI chat endpoints
│   │   ├── 🧠 core/               # LangGraph conversation logic
│   │   └── 🌐 frontend/           # Next.js chat interface
│   └── 🔄 translation/            # TTS/STT services (future)
├── 📊 logs/                       # Service logs
└── 🐍 dev_venv/                   # Python virtual environment
```

## 🔍 Monitoring & Debugging

### Logs
All services log to the `logs/` directory:
- `efr_server.log` - Farmer database operations
- `scheme_server.log` - Scheme validation and rules
- `chat_server.log` - Conversation engine activity
- `frontend.log` - Next.js frontend logs

### Health Checks
Each service provides health endpoints:
- http://localhost:8001/health (EFR)
- http://localhost:8002/health (Scheme)  
- http://localhost:8003/health (Chat)

### API Documentation
Interactive API docs available at:
- http://localhost:8001/docs (EFR API)
- http://localhost:8002/docs (Scheme API)
- http://localhost:8003/docs (Chat API)

## 🛠️ Development

### Adding New Features
1. **Backend**: Modify the respective server in `src/`
2. **Frontend**: Edit `src/schemabot/frontend/src/app/page.tsx`
3. **Conversation Flow**: Update `src/schemabot/core/conversation/`

### Hot Reload
All services support hot reload during development:
- Python services reload on file changes
- Next.js frontend has built-in hot reload

### Testing
- Use the developer mode in the frontend sidebar
- Check individual API endpoints with the Swagger docs
- Monitor logs in real-time: `tail -f logs/chat_server.log`

## 🔧 Troubleshooting

### Common Issues

1. **Port conflicts:**
   ```bash
   ./stop_sanchalak.sh  # Stop all services
   ./start_sanchalak.sh # Restart
   ```

2. **Virtual environment issues:**
   ```bash
   source dev_venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Frontend dependencies:**
   ```bash
   cd src/schemabot/frontend
   rm -rf node_modules package-lock.json
   npm install
   ```

4. **Service not responding:**
   - Check logs in `logs/` directory
   - Verify health endpoints
   - Restart individual services if needed

### Getting Help
- Check the logs first: `ls -la logs/`
- Verify all services are running: `lsof -i :3000,:8001,:8002,:8003`
- Review API documentation for endpoint details

## 🎉 Success!

When everything is working, you should see:
- ✅ All server status indicators green in the frontend
- ✅ Smooth conversation flow with the AI assistant
- ✅ Progress bars updating as you complete stages
- ✅ Quick options appearing for faster interaction
- ✅ Final farmer data collection and export

---

**Built with ❤️ for farmers and government schemes** 