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

# 3. Start the complete system (infrastructure + services)
./scripts/start-all.ps1

# 4. Access the system
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

# 2. Setup environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 3. Make scripts executable
chmod +x scripts/*.sh

# 4. Start infrastructure first
docker-compose up -d postgres redis kafka zookeeper qdrant prometheus grafana

# 5. Wait 30 seconds, then start services
docker-compose up -d context-broker journal-parser knowledge-system api-gateway
```

**📚 For detailed startup options, see [scripts/README.md](scripts/README.md)**

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
**AI:** Google Gemini API  
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

```bash
# Start development environment
./scripts/dev.sh

# Run tests
./scripts/test.sh

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Clean everything (including volumes)
./scripts/clean.sh
```

---

## 📚 Documentation

- [API Documentation](docs/API.md)
- [Architecture Deep Dive](docs/ARCHITECTURE.md)
- [Local Setup Guide](docs/LOCAL_SETUP.md)
- [Contributing Guidelines](docs/CONTRIBUTING.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

---

## 🔐 Security

⚠️ **Before deploying to production:**

- Change all default passwords in `.env`
- Enable HTTPS/TLS
- Configure proper CORS settings
- Set up secrets management (Vault, AWS Secrets Manager)
- Enable database encryption at rest
- Review and configure rate limiting
- Set up proper authentication/authorization

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

## 🙏 Acknowledgments

- Google Gemini for AI capabilities
- FastAPI for the excellent async framework
- Apache Kafka for reliable messaging
- The open-source community

---

## 📞 Support

- 📧 Email: support@plos.dev
- 💬 Discord: [Join our server](https://discord.gg/plos)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/plos/issues)

---

**Built with ❤️ for personal productivity**
