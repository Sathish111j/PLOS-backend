# Monitoring Infrastructure

This folder contains Prometheus configuration used by docker-compose.

## Files

- prometheus.yml
  Scrape configuration for infrastructure and services.

## Usage

Monitoring services (Prometheus, Grafana) are behind the `monitoring` Docker Compose profile. To start them:

```bash
docker compose --profile monitoring up -d
```
