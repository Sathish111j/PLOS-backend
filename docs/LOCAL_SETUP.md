# PLOS Local Development Setup Guide

Complete guide to setting up PLOS on your local machine.

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **Docker Desktop** (v24.0+)
  - [Download for Windows](https://docs.docker.com/desktop/install/windows-install/)
  - [Download for Mac](https://docs.docker.com/desktop/install/mac-install/)
  - [Download for Linux](https://docs.docker.com/desktop/install/linux-install/)

- **Git** (v2.30+)

- **Google Gemini API Key**
  - Sign up at [Google AI Studio](https://aistudio.google.com/)
  - Generate an API key

### Optional
- **Python 3.11+** (for local development without Docker)
- **Node.js 18+** (for frontend development)

---

## Step-by-Step Setup

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd LifeOSbackend
```

### 2. Configure Environment

```bash
# Copy the environment template
cp .env.example .env

# Edit .env with your favorite editor
nano .env  # or vim, code, notepad++, etc.
```

**Required changes in `.env`:**

```env
# Add your Gemini API key (REQUIRED)
GEMINI_API_KEY=your-actual-api-key-here

# Optional: Change default passwords for production
POSTGRES_PASSWORD=your-secure-password
REDIS_PASSWORD=your-secure-password
```

### 3. Run Initial Setup

```bash
# Make scripts executable (Linux/Mac)
chmod +x scripts/*.sh

# Run setup script
./scripts/setup.sh
```

This script will:
- ✅ Check Docker installation
- ✅ Create `.env` file (if not exists)
- ✅ Build Docker images
- ✅ Start infrastructure services (PostgreSQL, Redis, Kafka)
- ✅ Run database migrations
- ✅ Create Kafka topics

**Expected output:**
```
==========================================
  PLOS - Initial Setup
==========================================

✓ Docker and Docker Compose found
✓ .env file created
🏗️  Building Docker images...
...
✅ Setup Complete!
```

### 4. Start Development Environment

```bash
./scripts/dev.sh
```

This will start all services in Docker containers.

**Services started:**
- PostgreSQL (port 5432)
- Redis (port 6379)
- Kafka + Zookeeper (port 9092)
- API Gateway (port 8000)
- Context Broker (port 8001)
- All other microservices
- Frontend (port 3000)
- Monitoring (Grafana, Prometheus, Jaeger)

### 5. Verify Setup

Open your browser and visit:

| Service | URL | Notes |
|---------|-----|-------|
| **Frontend** | http://localhost:3000 | Main application |
| **API Gateway** | http://localhost:8000 | API entry point |
| **API Docs** | http://localhost:8000/docs | Interactive API documentation |
| **Context Broker** | http://localhost:8001/health | Health check |
| **Grafana** | http://localhost:3001 | Monitoring (admin/admin) |
| **Prometheus** | http://localhost:9090 | Metrics |
| **Kafka UI** | http://localhost:8080 | Kafka management |
| **Jaeger** | http://localhost:16686 | Distributed tracing |

**Test API Gateway:**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "api-gateway",
  "version": "0.1.0"
}
```

---

## Development Workflow

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f context-broker

# Last 50 lines, follow
docker-compose logs --tail=50 -f journal-parser
```

### Stopping Services

```bash
# Stop all services (preserves data)
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

### Restarting a Single Service

```bash
# Restart context broker
docker-compose restart context-broker

# Rebuild and restart
docker-compose up -d --build context-broker
```

### Database Access

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres -d plos

# Run SQL query
docker-compose exec postgres psql -U postgres -d plos -c "SELECT * FROM users LIMIT 5;"

# View tables
docker-compose exec postgres psql -U postgres -d plos -c "\dt"
```

### Redis Access

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli -a redis

# Check keys
docker-compose exec redis redis-cli -a redis KEYS "*"

# Get specific key
docker-compose exec redis redis-cli -a redis GET "context:user_id_here"
```

### Kafka Management

```bash
# List topics
docker-compose exec kafka kafka-topics --list --bootstrap-server kafka:9092

# Describe topic
docker-compose exec kafka kafka-topics --describe --topic journal_entries --bootstrap-server kafka:9092

# Consume messages (from beginning)
docker-compose exec kafka kafka-console-consumer --bootstrap-server kafka:9092 --topic parsed_entries --from-beginning
```

---

## Troubleshooting

### Services Won't Start

**Issue:** Containers fail to start

**Solution:**
```bash
# Check Docker daemon
docker ps

# View specific service logs
docker-compose logs postgres

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up -d
```

### Port Already in Use

**Issue:** `Error: port 8000 already in use`

**Solution:**
```bash
# Find process using port
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Kill process or change port in .env
API_GATEWAY_PORT=8080
```

### Database Connection Error

**Issue:** Services can't connect to PostgreSQL

**Solution:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Kafka Not Ready

**Issue:** Consumers can't connect to Kafka

**Solution:**
```bash
# Wait for Kafka to fully start (can take 30-60 seconds)
sleep 30

# Check Kafka logs
docker-compose logs kafka

# Recreate topics
docker-compose exec kafka bash /infrastructure/kafka/init-topics.sh
```

### Out of Memory

**Issue:** Docker containers killed due to memory

**Solution:**
```bash
# Increase Docker memory limit
# Docker Desktop > Settings > Resources > Memory
# Recommended: 8GB minimum

# Or reduce running services
docker-compose up -d postgres redis kafka context-broker
```

### Cannot Build Images

**Issue:** `failed to solve: no space left on device`

**Solution:**
```bash
# Clean Docker system
docker system prune -a

# Remove unused volumes
docker volume prune
```

---

## Development Tips

### Hot Reload

Python services support hot reload:
- Edit files in `services/*/src/`
- Changes auto-reload (no restart needed)

Frontend supports hot reload:
- Edit files in `frontend/src/`
- Browser auto-refreshes

### Environment Variables

To change environment variables:
1. Edit `.env` file
2. Restart services: `docker-compose down && docker-compose up -d`

### Adding New Dependencies

For Python services:
```bash
# Edit requirements.txt in service directory
# e.g., services/context-broker/requirements.txt

# Rebuild service
docker-compose build context-broker
docker-compose up -d context-broker
```

### Running Tests

```bash
./scripts/test.sh
```

---

## Clean Up

### Remove All Data

```bash
./scripts/clean.sh
```

This will:
- Stop all containers
- Remove all volumes (⚠️ **deletes all data**)
- Remove Docker images

### Partial Cleanup

```bash
# Stop services only
docker-compose down

# Remove volumes only
docker-compose down -v

# Remove specific volume
docker volume rm plos_postgres_data
```

---

## Next Steps

1. ✅ Setup complete
2. 📖 Read [Architecture Documentation](ARCHITECTURE.md)
3. 🔌 Explore [API Documentation](API.md)
4. 💻 Start building features
5. 🤝 See [Contributing Guidelines](CONTRIBUTING.md)

---

## Need Help?

- 📧 Email: support@plos.dev
- 💬 Discord: [Join server](https://discord.gg/plos)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/plos/issues)

---

**Happy coding! 🚀**
