# Plan: Add Grafana + Loki Log Aggregation

## Context
The project runs a FastAPI app (uvicorn) and a custom Python polling worker, both containerized via docker-compose. Logs are emitted as structured JSON to stdout via structlog. There is no existing log aggregation. The goal is to add Grafana + Loki so logs from both services can be searched and visualized.

## Architecture
- **Loki**: log storage backend
- **Promtail**: log collector — reads Docker container stdout via the Docker socket, ships to Loki
- **Grafana**: visualization — pre-provisioned with Loki datasource

Promtail uses Docker service discovery to scrape only the `coderadar` and `worker` containers, parses the structlog JSON body to extract `level` and `logger` as Loki labels.

## Files Created

- `deploy/loki/loki-config.yml` — Loki monolithic mode, local TSDB v13 filesystem storage
- `deploy/promtail/promtail-config.yml` — Docker socket scraping, JSON pipeline, health-check drop
- `deploy/grafana/provisioning/datasources/loki.yml` — auto-provisioned Loki datasource

## docker-compose.yml Changes

Added three services (`loki`, `promtail`, `grafana`) and two volumes (`loki_data`, `grafana_data`).

Image versions:
- `grafana/loki:3.4.2`
- `grafana/promtail:3.4.2`
- `grafana/grafana:11.6.1`

## Verification

1. `docker compose up -d`
2. `curl http://localhost:3100/ready` → `ready`
3. Wait ~10s, then `curl http://localhost:3100/loki/api/v1/labels` → includes `service`, `level`
4. Open `http://localhost:3000`, login `admin/admin`
5. Explore → Loki → `{service="coderadar"}` → API logs appear
6. `{service="worker"}` → worker logs appear
7. `{service="coderadar", level="error"}` → error filtering works
