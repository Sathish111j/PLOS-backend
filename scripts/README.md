# PLOS Backend Scripts

## Quick Start

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

## Script Reference

### Windows PowerShell Scripts (Primary)

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `start-all.ps1` | Start complete system (infrastructure + services) | First startup, after reboot |
| `start-infrastructure.ps1` | Start only infrastructure (postgres, redis, kafka, etc.) | Manual control, debugging |
| `start-services.ps1` | Start only application services | After code changes |
| `stop.ps1` | Stop all services | End of day, clean state |
| `stop.ps1 -CleanVolumes` | Stop and delete all data | Fresh start needed |
| `seed.ps1` | Populate database with initial data | Optional - run after start-all.ps1 if needed |
| `verify-infrastructure.ps1` | Comprehensive verification (6 tests) | Check system health |
| `lint.ps1` | Run code linting | Before commits |
| `lint.ps1 -Fix` | Auto-fix linting issues | Fix formatting |

### Linux/Mac Bash Scripts

| Script | Purpose | Notes |
|--------|---------|-------|
| `setup.sh` | First-time setup | Creates .env, checks Docker |
| `dev.sh` | Start development environment | Equivalent to start-all.ps1 |
| `verify.sh` | Service verification | Health checks for all services |
| `clean.sh` | Clean up containers and data | Equivalent to stop.ps1 -CleanVolumes |
| `test.sh` | Run tests | Runs pytest suite |

---

## Detailed Usage

### start-all.ps1
Complete system startup with proper sequencing and health checks:
1. Starts infrastructure (postgres, redis, kafka, zookeeper, qdrant, prometheus, grafana, kafka-ui)
2. Verifies infrastructure health (7 tests)
3. Starts application services (context-broker, journal-parser, knowledge-system, api-gateway)
4. Verifies services health (health endpoints)
5. Database is automatically initialized via init.sql

### start-infrastructure.ps1
Starts only the infrastructure layer:
- PostgreSQL (database)
- Redis (cache)
- Kafka + Zookeeper (messaging)
- Qdrant (vector database)
- Prometheus + Grafana (monitoring)

Use when:
- You only need databases/tools
- Debugging infrastructure issues

### start-services.ps1
Starts only application services:
1. Verifies infrastructure is running
2. Builds service images (if code changed)
3. Starts all 4 services

Use when:
- Infrastructure already running
- After code changes
- After fixing a service bug

### stop.ps1
Gracefully stops all services.

```powershell
# Stop but keep data
./scripts/stop.ps1

# Stop and DELETE ALL DATA (fresh start)
./scripts/stop.ps1 -CleanVolumes
```

Use `-CleanVolumes` when:
- Need fresh database
- Corrupted data
- Testing from scratch

### verify-infrastructure.ps1
Comprehensive 6-step verification:

1. PostgreSQL - Connection
2. Redis - Connection, memory usage
3. Zookeeper - Process status, Kafka connection
4. Kafka - Topics, message queue
5. Qdrant - Collections, vector DB
6. Prometheus - Health status
7. Grafana - Dashboard availability

Output:
- "ALL TESTS PASSED" = Everything working
- "PASSED WITH WARNINGS" = Working but needs attention
- "FAILED" = Issues need fixing

---

## Local Setup Process

### Prerequisites
- Docker Desktop installed and running
- PowerShell (Windows) or Bash (Linux/Mac)
- At least 8GB RAM available
- Ports 5432, 6379, 9092, 2181, 6333, 9090, 3333, 8080, 8082, 8000-8003 available

### Complete Setup Steps

1. **Clone Repository**
   ```bash
   git clone https://github.com/Sathish111j/PLOS-backend.git
   cd PLOS-backend
   ```

2. **Start Complete System**
   ```powershell
   # Windows (Recommended)
   ./scripts/start-all.ps1
   
   # Linux/Mac
   chmod +x scripts/*.sh
   ./scripts/dev.sh
   ```

3. **Verify Everything Works**
   ```powershell
   ./scripts/verify-infrastructure.ps1
   ```

4. **Access Services**
   - API Gateway: http://localhost:8000
   - Kafka UI: http://localhost:8080
   - Grafana: http://localhost:3333
   - Metabase: http://localhost:8082

### Manual Step-by-Step Setup

If you need more control:

1. **Start Infrastructure Only**
   ```powershell
   ./scripts/start-infrastructure.ps1
   ```

2. **Verify Infrastructure Health**
   ```powershell
   ./scripts/verify-infrastructure.ps1
   ```

3. **Start Application Services**
   ```powershell
   ./scripts/start-services.ps1
   ```

4. **Initialize Database (Optional)**
   ```powershell
   ./scripts/seed.ps1
   ```

### Troubleshooting

- **Services won't start**: Check Docker Desktop is running
- **Port conflicts**: Stop other services using those ports
- **Out of memory**: Increase Docker memory allocation to 8GB+
- **Database issues**: Run `./scripts/stop.ps1 -CleanVolumes` to reset

### Stopping Services

```powershell
# Stop all services
./scripts/stop.ps1

# Stop and delete all data (fresh start)
./scripts/stop.ps1 -CleanVolumes
```

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

### Fresh Start
```powershell
./scripts/stop.ps1 -CleanVolumes
./scripts/start-all.ps1
```

---

## Troubleshooting

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

## Why Two Sets? (PowerShell + Bash)

**PowerShell (Windows):**
- More features (health checks, colors, verifications)
- Better error handling
- Recommended for development on Windows

**Bash (Linux/Mac):**
- Cross-platform compatibility
- Simpler, faster execution
- Good for CI/CD pipelines

Both work - use what fits your OS.

---

**Last Updated:** January 1, 2026
**Status:** Production Ready
**Verified:** All scripts working correctly with proper sequencing
