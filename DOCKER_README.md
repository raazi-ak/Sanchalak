# Sanchalak Docker Production Setup

## 🏗️ Architecture Overview

```
Sanchalak/
├── components/                    # All microservices
│   ├── telegram-bot/
│   │   ├── src/                  # Source code only
│   │   └── dockerfiles/          # Docker configurations
│   ├── orchestrator/
│   │   ├── src/
│   │   └── dockerfiles/
│   ├── efr-db/
│   │   ├── src/
│   │   └── dockerfiles/
│   ├── form-filler/
│   │   ├── src/
│   │   └── dockerfiles/
│   ├── status-tracker/
│   │   ├── src/
│   │   └── dockerfiles/
│   └── monitoring/
│       ├── src/
│       └── dockerfiles/
├── scripts/                      # Management scripts
├── docker-compose.yml           # Main orchestration
└── env.example                  # Environment template
```

## 🚀 Quick Start

### 1. Setup Environment
```bash
# Copy environment template
cp env.example .env

# Edit with your configuration
nano .env
```

### 2. Build & Run
```bash
# Build all images
./scripts/build.sh

# Start all services
./scripts/run.sh
```

### 3. Access Services
- **Telegram Bot**: http://localhost:8080
- **Orchestrator**: http://localhost:8000  
- **EFR Database**: http://localhost:8001
- **Form Filler**: http://localhost:8002
- **Status Tracker**: http://localhost:8003
- **Monitoring**: http://localhost:8084
- **MongoDB**: localhost:27017

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
```

## 📊 Service Management

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f telegram-bot
docker-compose logs -f orchestrator
```

### Service Status
```bash
# Check all services
docker-compose ps

# Service health
curl http://localhost:8000/health  # Orchestrator
curl http://localhost:8001/health  # EFR DB
```

### Restart Services
```bash
# Restart specific service
docker-compose restart telegram-bot

# Restart all
docker-compose restart
```

## 🔧 Development Workflow

### 1. Code Changes
```bash
# Make changes in components/[service]/src/
# Rebuild specific service
docker-compose build telegram-bot
docker-compose up -d telegram-bot
```

### 2. Database Operations
```bash
# Access MongoDB
./scripts/shell.sh mongo

# Inside MongoDB shell
> use sanchalak
> db.users.find()
> db.sessions.find()
```

### 3. Debugging
```bash
# View real-time logs
docker-compose logs -f telegram-bot

# Access container for debugging
./scripts/shell.sh telegram-bot
> python3 -c "import bot; print('Bot loaded')"
```

## 🏭 Production Deployment

### 1. Environment Variables
```bash
# Required in .env
TELEGRAM_BOT_TOKEN=your_bot_token
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=secure_password
ENVIRONMENT=production
```

### 2. SSL Configuration
```bash
# Place SSL certificates
mkdir -p nginx/ssl/
cp your_cert.pem nginx/ssl/cert.pem
cp your_key.pem nginx/ssl/key.pem
```

### 3. Production Run
```bash
# Start with production config
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 📦 Docker Volumes

### Data Persistence
- `mongo-data`: MongoDB data
- `form-data`: Form templates
- `bot-uploads`: User uploaded files
- `orchestrator-uploads`: Processing files

### Logs
- `bot-logs`: Telegram bot logs
- `orchestrator-logs`: AI processing logs
- `efr-logs`: Database service logs
- `monitoring-logs`: System monitoring logs

## 🔍 Monitoring & Health Checks

### Built-in Health Checks
All services have automatic health checks:
- **Interval**: 30 seconds
- **Timeout**: 10 seconds  
- **Retries**: 3 attempts

### Monitoring Dashboard
```bash
# Access monitoring service
curl http://localhost:8084/health

# View monitoring logs
docker-compose logs -f monitoring
```

## 🛠️ Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check logs
docker-compose logs [service-name]

# Rebuild image
docker-compose build [service-name]
docker-compose up -d [service-name]
```

#### Database Connection Issues
```bash
# Check MongoDB
./scripts/shell.sh mongo

# Verify connection string
docker-compose exec telegram-bot python3 -c "
import os
print(os.getenv('MONGODB_URI'))
"
```

#### Port Conflicts
```bash
# Check port usage
lsof -i :8000
lsof -i :8001

# Modify ports in docker-compose.yml
```

### Performance Optimization

#### Resource Limits
```yaml
# Add to docker-compose.yml
services:
  telegram-bot:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
```

#### Log Rotation
```bash
# Configure log rotation
docker-compose logs --tail=100 -f telegram-bot
```

## 🔄 Backup & Recovery

### Database Backup
```bash
# Backup MongoDB
docker exec sanchalak-mongo mongodump --out /data/backup

# Copy backup
docker cp sanchalak-mongo:/data/backup ./backup/
```

### Volume Backup
```bash
# Backup all volumes
docker run --rm -v sanchalak_mongo-data:/data -v $(pwd):/backup alpine tar czf /backup/mongo-backup.tar.gz /data
```

## 📋 Commands Reference

### Essential Commands
```bash
# Build all images
./scripts/build.sh

# Start services
./scripts/run.sh

# Access shell
./scripts/shell.sh [service-name]

# View logs
docker-compose logs -f [service-name]

# Stop all services
docker-compose down

# Clean up
docker-compose down -v  # Removes volumes
docker system prune -a  # Clean all unused images
```

### Development Commands
```bash
# Hot reload (rebuild and restart)
docker-compose build telegram-bot && docker-compose up -d telegram-bot

# Scale services
docker-compose up -d --scale telegram-bot=2

# Update single service
docker-compose pull mongo
docker-compose up -d mongo
```

## 🎯 Next Steps

1. **SSL Setup**: Configure HTTPS for production
2. **Load Balancing**: Add multiple bot instances
3. **Monitoring**: Integrate Prometheus/Grafana
4. **CI/CD**: Automated deployment pipeline
5. **Security**: Implement secrets management

---

**🚀 Ready for Production!** This Docker setup provides a clean, scalable, and maintainable architecture for the Sanchalak system. 