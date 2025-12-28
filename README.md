# PLOS - Personal Life Operating System

🧠 **Your Complete Personal Life Management Platform**

An intelligent, context-aware system for managing your entire life - journals, health, knowledge, goals, and calendar - powered by AI.

---

## 🚀 Quick Start

### Windows PowerShell (Recommended)

```powershell
# 1. Clone and navigate
git clone <your-repo-url>
cd LifeOSbackend

# 2. Copy and configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 3. Start the complete system (infrastructure → services)
./scripts/start-all.ps1

# 4. Verify everything works
./scripts/verify-infrastructure.ps1

# 5. Access the system
# API Gateway:    http://localhost:8000
# Context Broker: http://localhost:8001/health
# Journal Parser: http://localhost:8002/health
# Knowledge:      http://localhost:8003/health
# Kafka UI:       http://localhost:8080
# Grafana:        http://localhost:3333 (admin/admin)
# Prometheus:     http://localhost:9090
# Qdrant:         http://localhost:6333/dashboard
```

### Linux/Mac

```bash
# 1. Clone and navigate
git clone <your-repo-url>
cd LifeOSbackend

# 2. First-time setup
./scripts/setup.sh
# Edit .env and add your GEMINI_API_KEY

# 3. Start development environment (infrastructure → services)
./scripts/dev.sh

# 4. Verify services
./scripts/verify.sh
```

**📚 For detailed options and troubleshooting, see [scripts/README.md](scripts/README.md)**

---

## 📋 Features

- ✍️ **Journal Management** - Free-form journaling with AI-powered extraction
- 🏥 **Health Tracking** - Mood, sleep, nutrition, exercise tracking
- 📚 **Knowledge System** - Personal wiki with semantic search
- 🎯 **Goals & Tasks** - Intelligent task management with AI scheduling
- 📅 **Smart Calendar** - Energy-based time blocking
- 🤖 **AI Agents** - Personalized insights, motivation, and reflection
- 📊 **Pattern Detection** - Correlation analysis and predictions
- 🔔 **Smart Notifications** - Multi-channel with intelligent scheduling

---

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
┌──────▼──────┐
│ API Gateway │ (Kong)
└──────┬──────┘
       │
  ┌────┴────┬─────────────┬──────────┐
  │         │             │          │
┌─▼─┐  ┌───▼───┐  ┌──────▼─┐  ┌────▼────┐
│CTX│  │Journal│  │Knowledge│  │Goals/Cal│
└─┬─┘  └───┬───┘  └────┬───┘  └────┬────┘
  │        │           │           │
  └────────┴───────┬───┴───────────┘
                   │
            ┌──────▼──────┐
            │    Kafka    │
            └──────┬──────┘
                   │
     ┌─────────────┼─────────────┐
     │             │             │
┌────▼────┐  ┌────▼────┐  ┌─────▼─────┐
│Extractors│  │Correlation│ │AI Agents│
└────┬────┘  └────┬────┘  └─────┬─────┘
     │             │             │
     └─────────────┴─────────────┘
                   │
         ┌─────────▼─────────┐
         │ PostgreSQL+Redis  │
         └───────────────────┘
```

---

## 🛠️ Tech Stack

**Backend:** Python 3.11+, FastAPI, PostgreSQL, TimescaleDB  
**Messaging:** Apache Kafka  
**Cache:** Redis  
**AI:** Google Gemini 2.5 (Flash, Pro, Embeddings)  
**Frontend:** React 18, TypeScript, Vite, Tailwind CSS  
**DevOps:** Docker, Docker Compose, Prometheus, Grafana  

---

## 📂 Project Structure

```
plos/
├── docker-compose.yml          # All services orchestration
├── .env.example                # Environment template
├── services/                   # Microservices (10+)
│   ├── api-gateway/
│   ├── context-broker/
│   ├── journal-parser/
│   ├── knowledge-system/
│   ├── extractors/             # 6 parallel extractors
│   ├── agents/                 # 4 AI agents
│   └── ...
├── infrastructure/             # Database, Kafka, Redis configs
├── shared/                     # Shared libraries & models
├── frontend/                   # React frontend
├── scripts/                    # Development scripts
└── docs/                       # Documentation
```

---

## 🧪 Development

```powershell
# Windows - Start everything
./scripts/start-all.ps1

# Or start infrastructure only
./scripts/start-infrastructure.ps1

# Then services separately
./scripts/start-services.ps1

# Verify system health
./scripts/verify-infrastructure.ps1

# View logs
docker-compose logs -f [service-name]

# Stop services (keep data)
./scripts/stop.ps1

# Clean everything (delete data)
./scripts/stop.ps1 -CleanVolumes
```

```bash
# Linux/Mac - Start everything
./scripts/dev.sh

# Verify services
./scripts/verify.sh

# Clean everything
./scripts/clean.sh
```

**💡 See [scripts/README.md](scripts/README.md) for all options**

---


## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed guidelines.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---


**Built with ❤️ for personal productivity**
