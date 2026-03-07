# Redis Infrastructure

This folder contains Redis configuration used by docker-compose.

## Files

- redis.conf
  Redis runtime configuration for the container.

## Configuration

The Redis instance is configured with:
- **maxmemory**: 512mb
- **maxmemory-policy**: allkeys-lru (evict least recently used keys)
- **appendonly**: yes (enable AOF persistence)
