# PLOS Backend Scripts

## 🎯 Quick Start

### Windows (Recommended)
```powershell
# Complete system startup
./scripts/start-all.ps1

# Or step by step:
./scripts/start-infrastructure.ps1  # Start databases, cache, etc.
./scripts/start-services.ps1        # Start application services

# Verify everything works
./scripts/verify-infrastructure.ps1

# Stop everything
./scripts/stop.ps1                  # Keep data
./scripts/stop.ps1 -CleanVolumes    # Delete all data
```

### Linux/Mac
```bash
# Make scripts executable (first time only)
chmod +x scripts/*.sh

# Setup (first time only)
./scripts/setup.sh

# Start development environment
./scripts/dev.sh

# Verify services
./scripts/verify.sh

# Clean up
./scripts/clean.sh
```

---

## 📁 Script Reference

### Windows PowerShell Scripts (Primary)

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `start-all.ps1` | Start complete system (infrastructure + services) | First startup, after reboot |
| `start-infrastructure.ps1` | Start only infrastructure (postgres, redis, kafka, etc.) | Manual control, debugging |
| `start-services.ps1` | Start only application services | After code changes |
| `stop.ps1` | Stop all services | End of day, clean state |
| `stop.ps1 -CleanVolumes` | Stop and delete all data | Fresh start needed |
| `verify-infrastructure.ps1` | Comprehensive verification (7 tests) | Check system health |

### Linux/Mac Bash Scripts (Alternative)

| Script | Purpose | Notes |
|--------|---------|-------|
| `setup.sh` | First-time setup | Creates .env, checks Docker |
| `dev.sh` | Start development environment | Equivalent to start-all.ps1 |
| `verify.sh` | Quick service verification | Basic health checks |
| `clean.sh` | Clean up containers and data | Equivalent to stop.ps1 -CleanVolumes |
| `test.sh` | Run tests (not implemented yet) | Placeholder for future tests |

### Deprecated (Do Not Use)

| Script | Status | Use Instead |
|--------|--------|-------------|
| `verify.ps1` | ❌ Outdated | `verify-infrastructure.ps1` |

---

## 🔍 Detailed Usage

### startup-all.ps1
Complete system startup with proper sequencing:
1. Starts infrastructure (postgres, redis, kafka, zookeeper, qdrant)
2. Waits for health checks (30-60 seconds)
3. Starts monitoring (prometheus, grafana, kafka-ui)
4. Builds application services
5. Starts application services (context-broker, journal-parser, knowledge-system, api-gateway)

**Output:**
- Shows status at each step
- Lists all access points
- Reports any failures

---

### start-infrastructure.ps1
Starts only the infrastructure layer:
- PostgreSQL (database)
- Redis (cache)
- Kafka + Zookeeper (messaging)
- Qdrant (vector database)
- Prometheus + Grafana (monitoring)

**Use when:**
- You only need databases/tools
- Debugging infrastructure issues
- Want manual control over service startup

---

### start-services.ps1
Starts only application services:
1. Verifies infrastructure is running
2. Builds service images (if code changed)
3. Starts all 4 services

**Use when:**
- Infrastructure already running
- After code changes
- After fixing a service bug

---

### stop.ps1
Gracefully stops all services.

**Options:**
```powershell
# Stop but keep data
./scripts/stop.ps1

# Stop and DELETE ALL DATA (fresh start)
./scripts/stop.ps1 -CleanVolumes
```

**Use `-CleanVolumes` when:**
- Need fresh database
- Corrupted data
- Testing from scratch

---

### verify-infrastructure.ps1
Comprehensive 7-step verification:

1. PostgreSQL - Connection, tables, test data
2. Redis - Connection, memory usage
3. Zookeeper - Process status, Kafka connection
4. Kafka - Topics, message queue
5. Qdrant - Collections, vector DB
6. Prometheus - Health status
7. Grafana - Dashboard availability

**Output:**
- "ALL TESTS PASSED" = Everything perfect ✅
- "PASSED WITH WARNINGS" = Working but needs attention ⚠️
- "FAILED" = Issues need fixing ❌

---

## 💡 Common Workflows

### Morning Startup
```powershell
cd C:\Users\[YOU]\Desktop\LifeOSbackend
./scripts/start-all.ps1
```

### After Code Changes
```powershell
# Services restart automatically (hot reload enabled)
# OR manually restart one service:
docker-compose restart journal-parser

# OR rebuild and restart:
./scripts/start-services.ps1
```

### Debugging Infrastructure
```powershell
# Stop services but keep infrastructure
docker-compose stop context-broker journal-parser knowledge-system api-gateway

# Check infrastructure
./scripts/verify-infrastructure.ps1

# View logs
docker-compose logs postgres
docker-compose logs kafka
```

### Fresh Start (Nuclear Option)
```powershell
./scripts/stop.ps1 -CleanVolumes
./scripts/start-all.ps1
```

---

## 🐛 Troubleshooting

### "Port already in use"
```powershell
# Find what's using the port
netstat -ano | findstr ":5432"

# Kill the process or change port in .env
```

### "Service won't start"
```powershell
# Check logs
docker-compose logs [service-name]

# Rebuild
docker-compose build [service-name]
docker-compose up -d [service-name]
```

### "Verification failed"
```powershell
# Run detailed check
./scripts/verify-infrastructure.ps1

# Check what's wrong
docker-compose ps
docker-compose logs
```

---

## 📚 Related Documentation

- [STARTUP_ARCHITECTURE.md](../docs/STARTUP_ARCHITECTURE.md) - Why we separate infrastructure and services
- [INFRASTRUCTURE_STABILITY.md](../docs/INFRASTRUCTURE_STABILITY.md) - Infrastructure verification report
- [DEVELOPER_GUIDE.md](../docs/DEVELOPER_GUIDE.md) - Complete development guide
- [QUICK_REFERENCE.md](../docs/QUICK_REFERENCE.md) - Developer quick reference

---

## 🎓 Understanding the Scripts

### Why Two Sets? (PowerShell + Bash)

**PowerShell (Windows):**
- More features (health checks, colors, verifications)
- Better error handling
- Recommended for development on Windows

**Bash (Linux/Mac):**
- Cross-platform compatibility
- Simpler, faster execution
- Good for CI/CD pipelines

**Both work!** Use what fits your OS.

---

## ✅ Maintenance

These scripts are **production-ready** and **do not need changes** unless:
- Adding new services to docker-compose.yml
- Changing port numbers
- Adding new infrastructure components

The scripts automatically:
- Detect service health
- Handle dependencies
- Restart on failure
- Preserve data

---

**Last Updated:** December 28, 2024  
**Status:** Production Ready ✅
