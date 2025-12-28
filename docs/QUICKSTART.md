# PLOS - Quick Start Guide

Get PLOS running in **5 minutes**! ⚡

---

## Prerequisites

✅ Docker Desktop installed  
✅ Git installed  
✅ Google Gemini API key (free at [Google AI Studio](https://aistudio.google.com/))

---

## Installation (3 Steps)

### 1️⃣ Clone & Setup

```bash
git clone <your-repo-url>
cd LifeOSbackend
cp .env.example .env
```

### 2️⃣ Add Your API Key

Edit `.env` and add your Gemini API key:

```env
GEMINI_API_KEY=your-key-here
```

### 3️⃣ Start Everything

```bash
# Make scripts executable (Linux/Mac)
chmod +x scripts/*.sh

# Run setup (first time only)
./scripts/setup.sh

# Start all services
./scripts/dev.sh
```

---

## Verify It's Working

Open in your browser:

| What | URL |
|------|-----|
| **Frontend** | http://localhost:3000 |
| **API Docs** | http://localhost:8000/docs |
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
- ✅ PostgreSQL (database)
- ✅ Redis (cache)
- ✅ Kafka (message queue)
- ✅ API Gateway
- ✅ Context Broker
- ✅ Frontend
- ✅ Monitoring tools

---

## Quick Commands

```bash
# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Start again
./scripts/dev.sh

# Clean everything
./scripts/clean.sh
```

---

## Next Steps

1. ✅ Setup complete!
2. 📖 Read [Local Setup Guide](LOCAL_SETUP.md) for details
3. 🤖 Learn about [Gemini Integration](GEMINI_INTEGRATION.md)
4. 🏗️ Explore [Architecture](ARCHITECTURE.md)
5. 💻 Start coding!

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
./scripts/clean.sh
./scripts/setup.sh
```

---

## Need Help?

- 📖 [Full Documentation](.)
- 🐛 [Report Issues](https://github.com/yourusername/plos/issues)
- 💬 [Join Discord](https://discord.gg/plos)

---

**Happy building! 🚀**
