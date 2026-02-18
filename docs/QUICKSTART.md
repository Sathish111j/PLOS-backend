# PLOS - Quick Start Guide

Get PLOS running in **5 minutes**.

---

## Prerequisites

- Docker Desktop installed  
- Git installed  
- Google Gemini API key (free at [Google AI Studio](https://aistudio.google.com/))

---

## Installation (3 Steps)

### 1. Clone & Setup

```bash
git clone <your-repo-url>
cd LifeOSbackend
cp .env.example .env
```

### 2. Add Your API Key

Edit `.env` and add your Gemini API key:

```env
GEMINI_API_KEY=your-key-here
```

### 3. Start Everything

```bash
# Make scripts executable (Linux/Mac)
chmod +x scripts/start/*.sh scripts/stop/*.sh scripts/verify/*.sh scripts/setup/*.sh scripts/test/*.sh

# Run setup (first time only)
./scripts/setup/setup.sh

# Start all services
./scripts/start/dev.sh
```

---

## Verify It's Working

Open in your browser:

| What | URL |
|------|-----|
| **Frontend** | http://localhost:3000 |
| **API Docs** | http://localhost:8000/docs |
| **Metabase** | http://localhost:8082 |
| **Health Check** | http://localhost:8001/health |

Or test with curl:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

---

## What's Running?

```bash
docker-compose ps
```

You should see:
- PostgreSQL (database)
- Redis (cache)
- Kafka (message queue)
- API Gateway
- Context Broker
- Frontend
- Monitoring tools

---

## Quick Commands

```bash
# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Start again
./scripts/start/dev.sh

# Clean everything
./scripts/stop/clean.sh
```

---

## Next Steps

1. Setup complete.
2. Read [Local Setup Guide](LOCAL_SETUP.md) for details
3. Learn about [Gemini Integration](GEMINI_INTEGRATION.md)
4. Explore [Architecture](ARCHITECTURE.md)
5. Start coding.

---

## Troubleshooting

**Services won't start?**
```bash
docker-compose logs
```

**Port already in use?**

Edit `.env` and change the port:
```env
API_GATEWAY_PORT=8080  # Instead of 8000
```

**Need to reset everything?**
```bash
./scripts/stop/clean.sh
./scripts/setup/setup.sh
```

---

## Need Help?

- [Full Documentation](.)
- [Report Issues](https://github.com/yourusername/plos/issues)
- [Join Discord](https://discord.gg/plos)

---

**Happy building!**

