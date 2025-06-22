# 🚀 Sanchalak Production Docker Setup

## ✅ What We've Built

### 🏗️ Clean Architecture
- **Separated Code from Config**: `src/` contains only source code, `dockerfiles/` contains Docker configurations
- **Microservices Architecture**: Each component is independently containerized
- **Production Ready**: All services have health checks, logging, and monitoring

### 📦 Components Created

```
components/
├── telegram-bot/       # Main bot service
├── orchestrator/       # AI processing hub  
├── efr-db/            # Farmer database
├── form-filler/       # Government forms
├── status-tracker/    # Application tracking
└── monitoring/        # System monitoring
```

### 🛠️ Management Scripts
- `./scripts/build.sh` - Build all Docker images
- `./scripts/run.sh` - Start all services
- `./scripts/shell.sh [service]` - Access container shells

## 🚀 Quick Start

### 1. Environment Setup
```bash
# Copy environment template
cp env.example .env

# Edit with your bot token
nano .env
```

### 2. Build and Run
```bash
# Build all images
./scripts/build.sh

# Start all services  
./scripts/run.sh
```

### 3. Verify Services
```bash
# Check all services are running
docker-compose ps

# Check health endpoints
curl http://localhost:8000/health  # Orchestrator
curl http://localhost:8001/health  # EFR DB
curl http://localhost:8002/health  # Form Filler
curl http://localhost:8003/health  # Status Tracker
```

## 🐚 Container Shell Access

```bash
# Access any service shell
./scripts/shell.sh telegram-bot
./scripts/shell.sh orchestrator
./scripts/shell.sh mongo

# Run commands inside containers
./scripts/shell.sh telegram-bot
> python3 bot.py --help
> tail -f logs/bot.log
> python3 -c "import bot; print('Bot loaded')"
```

## 📊 Service Ports

| Service | Port | Description |
|---------|------|-------------|
| Telegram Bot | 8080 | Bot health endpoint |
| Orchestrator | 8000 | AI processing API |
| EFR Database | 8001 | Farmer records API |
| Form Filler | 8002 | Government forms API |
| Status Tracker | 8003 | Application status API |
| Monitoring | 8084 | System monitoring |
| MongoDB | 27017 | Database |

## 🔍 Monitoring & Logs

### Real-time Monitoring
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f telegram-bot
docker-compose logs -f orchestrator

# Access monitoring dashboard
curl http://localhost:8084/health
```

### Health Checks
All services have built-in health checks:
- **Interval**: 30 seconds
- **Timeout**: 10 seconds
- **Retries**: 3 attempts

## 🔧 Development Workflow

### Making Code Changes
```bash
# 1. Edit code in components/[service]/src/
# 2. Rebuild specific service
docker-compose build telegram-bot
docker-compose up -d telegram-bot

# 3. View logs to verify
docker-compose logs -f telegram-bot
```

### Database Operations
```bash
# Access MongoDB shell
./scripts/shell.sh mongo

# Inside MongoDB
> use sanchalak
> db.users.find()
> db.sessions.find()
```

## 🏭 Production Deployment

### Environment Variables
Required in `.env`:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=secure_password
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### SSL Configuration (Optional)
```bash
# For HTTPS in production
mkdir -p nginx/ssl/
cp your_cert.pem nginx/ssl/cert.pem
cp your_key.pem nginx/ssl/key.pem
```

### Scaling Services
```bash
# Scale telegram bot instances
docker-compose up -d --scale telegram-bot=3

# Scale orchestrator for heavy AI processing
docker-compose up -d --scale orchestrator=2
```

## 🔄 Backup & Recovery

### Database Backup
```bash
# Backup MongoDB
docker exec sanchalak-mongo mongodump --out /data/backup

# Copy backup to host
docker cp sanchalak-mongo:/data/backup ./backup/
```

### Volume Backup
```bash
# Backup persistent data
docker run --rm -v sanchalak_mongo-data:/data -v $(pwd):/backup alpine tar czf /backup/mongo-backup.tar.gz /data
```

## 🛠️ Troubleshooting

### Service Won't Start
```bash
# Check logs
docker-compose logs [service-name]

# Rebuild image
docker-compose build [service-name]
docker-compose up -d [service-name]
```

### Database Connection Issues
```bash
# Check MongoDB connection
./scripts/shell.sh mongo

# Verify connection string
./scripts/shell.sh telegram-bot
> python3 -c "import os; print(os.getenv('MONGODB_URI'))"
```

### Port Conflicts
```bash
# Check port usage
lsof -i :8000
lsof -i :8001

# Modify ports in docker-compose.yml if needed
```

## 📋 Essential Commands

### Daily Operations
```bash
# Start services
./scripts/run.sh

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart specific service
docker-compose restart telegram-bot
```

### Maintenance
```bash
# Clean up unused images
docker system prune -a

# Update base images
docker-compose pull

# Rebuild all images
./scripts/build.sh
```

## 🎯 Production Benefits

### ✅ Advantages of This Setup

1. **Clean Separation**: Code and configuration are separated
2. **Easy Scaling**: Each service can be scaled independently
3. **Easy Debugging**: Direct shell access to any container
4. **Production Ready**: Health checks, logging, monitoring built-in
5. **Easy Deployment**: Single command deployment
6. **Easy Maintenance**: Individual service updates without affecting others

### 🔧 Container Management

```bash
# Individual service management
docker-compose build telegram-bot
docker-compose up -d telegram-bot
docker-compose restart telegram-bot
docker-compose logs -f telegram-bot

# Full system management
docker-compose up -d        # Start all
docker-compose down         # Stop all
docker-compose restart      # Restart all
docker-compose ps           # Status all
```

## 🚀 Ready for Production!

This Docker setup provides:
- ✅ **Clean Architecture**: Separated concerns
- ✅ **Easy Management**: Simple scripts for all operations
- ✅ **Production Ready**: Health checks, monitoring, logging
- ✅ **Scalable**: Independent service scaling
- ✅ **Maintainable**: Easy updates and debugging

**Next Steps**: Deploy to your production server and start serving farmers! 🌾 