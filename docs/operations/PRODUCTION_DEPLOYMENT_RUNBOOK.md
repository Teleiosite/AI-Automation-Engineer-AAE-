# AI Automation Engineer (AAE) — Production Deployment Runbook

**Product:** AI Automation Engineer (AAE)  
**Version:** 0.1.0-prod  
**Status:** PRODUCTION READY  
**Classification:** Operational Governance & Deployment Guide  

---

## 1. System Architecture & Prerequisites

The AI Automation Engineer (AAE) is a production-grade autonomous agent system architected under strict Clean Architecture / Hexagonal Architecture principles. 

### Infrastructure Prerequisites
- **Host OS:** Linux (Ubuntu 22.04+ / Debian 12+) or Windows Server 2022+ with Docker Desktop/Engine
- **Container Runtime:** Docker Engine 24.0+ & Docker Compose v2.20+
- **Database:** PostgreSQL 16+ (tested against PostgreSQL 16.15-alpine)
- **External Orchestrator:** n8n 1.0+ / 2.0+ (verified against n8n 2.38.7 on Node v24.21.0)
- **Networking:** Local/Internal VPC network with isolated ports:
  - `5432`: PostgreSQL (internal service network only)
  - `5678`: n8n Server (internal service network only)
  - `8000`: AAE Production API (reverse-proxy / TLS terminator ingress)

```
       +-------------------------------------------------------------+
       |                     Reverse Proxy / Ingress                 |
       |                        (TLS Termination)                    |
       +------------------------------+------------------------------+
                                      | HTTP :8000
                                      v
       +-------------------------------------------------------------+
       |             AAE Production Container (aae:production)       |
       |  - Non-root user: aae (UID 10001)                           |
       |  - FastUvicorn / FastAPI (Production Settings)              |
       |  - Strict Security Middlewares & Header Hardening           |
       +--------------+------------------------------+---------------+
                      |                              |
      SQLAlchemy      |                              | HTTP REST / Webhooks
      psycopg3        v                              v (X-N8N-API-KEY)
+-------------------------------+      +-------------------------------+
|     PostgreSQL 16 Server      |      |          n8n 2.38.7           |
| (14-Table Normalized Schema)  |      |   Workflow Execution Engine   |
+-------------------------------+      +-------------------------------+
```

---

## 2. Configuration & Environment Variables

All production configurations are loaded strictly from environment variables or a secured production `.env` file validated via `pydantic-settings`.

### Production Environment Variables Reference

| Variable | Type | Default / Example | Description |
| :--- | :--- | :--- | :--- |
| `AAE_ENVIRONMENT` | `string` | `production` | Enables production security mode (suppresses `/docs`, enables security headers). |
| `AAE_SECRET_KEY` | `string` | *(64-hex token)* | High-entropy production signing secret (minimum 32 characters; default insecure keys rejected at startup). |
| `DATABASE_URL` | `string` | `postgresql+psycopg://aae:secret@postgres:5432/aae_prod` | PostgreSQL connection DSN using psycopg 3 driver. |
| `DB_POOL_SIZE` | `integer` | `20` | Database connection pool size. |
| `DB_MAX_OVERFLOW` | `integer` | `10` | Maximum pool overflow connections. |
| `DB_POOL_TIMEOUT` | `integer` | `30` | Connection checkout timeout in seconds. |
| `N8N_BASE_URL` | `string` | `http://n8n:5678` | Base URL for the n8n orchestration instance. |
| `N8N_API_KEY` | `string` | *(n8n API Key)* | API Key for authenticating with n8n REST API (`X-N8N-API-KEY`). |
| `N8N_TIMEOUT_SECONDS`| `float` | `30.0` | Request timeout for n8n API calls. |
| `LOG_LEVEL` | `string` | `INFO` | Logging verbosity (`INFO` or `WARNING` in production). |
| `RATE_LIMIT_ENABLED` | `boolean` | `true` | Enables in-memory sliding window rate limiting. |
| `RATE_LIMIT_MAX_REQUESTS` | `integer` | `100` | Maximum requests per rate-limit window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `integer` | `60` | Duration of rate-limit window in seconds. |

---

## 3. Database Migration Procedures

AAE uses Alembic to manage zero-loss schema migrations across its 14-table persistence structure.

### Pre-Deployment Migration Check
Verify database connectivity and check the current migration head:
```bash
# Inspect current applied revision
alembic current

# Check pending heads
alembic heads
```

### Apply Migrations (Upgrade to Head)
Execute the migration runner prior to launching updated service containers:
```bash
# Run migrations to head
alembic upgrade head
```

### Rollback Migration (Downgrade)
In the event of an operational issue requiring schema regression:
```bash
# Rollback single revision
alembic downgrade -1

# Rollback to clean baseline (disaster recovery only)
alembic downgrade base
```

---

## 4. Container Deployment & Startup

### Building the Production Image
Build the hardened multi-stage Docker image:
```bash
docker build -t aae:production .
```

### Running with Docker Compose (Production Profile)
Launch the full production stack:
```bash
# Validate compose syntax
docker compose -f docker-compose.prod.yml config

# Launch services in background
docker compose -f docker-compose.prod.yml up -d
```

### Verification & Health Checking
The container includes a native healthcheck probe executing `curl -f http://localhost:8000/health || exit 1`.

Verify service health from the host:
```bash
# 1. Check container health status
docker inspect --format '{{.State.Health.Status}}' aae-app

# 2. Check HTTP liveness endpoint
curl -s -i http://localhost:8000/health

# 3. Check HTTP readiness endpoint (verifies DB and n8n connectivity)
curl -s http://localhost:8000/ready
```

Expected `/ready` payload:
```json
{
  "status": "ready",
  "database": "connected",
  "n8n": "connected"
}
```

---

## 5. Zero-Downtime Rolling Deployment Procedure

For production clusters (Kubernetes or Docker Swarm / blue-green instances):
1. **Pre-Flight:** Run unit and integration tests against staging.
2. **Database:** Execute `alembic upgrade head` (all migrations are backward-compatible).
3. **Deploy New Replicas:** Launch new container instances with `aae:production`.
4. **Health Probe:** Poll `/ready` until 3 consecutive HTTP 200 responses are received.
5. **Traffic Shift:** Switch ingress router/reverse-proxy traffic to new container pool.
6. **Drain & Terminate:** Gracefully stop previous container generation (`SIGTERM` with 30s timeout).

---

## 6. Emergency Rollback Runbook

If a critical fault or data degradation occurs during or post-deployment:
1. **Reroute Traffic:** Immediately point ingress proxy back to the previous stable release.
2. **Stop Current App:** Stop the malfunctioning container pool (`docker stop aae-app`).
3. **Database Schema Assessment:**
   - If the new code did not alter column types or drop constraints, keep the current schema.
   - If a schema downgrade is strictly required:
     ```bash
     alembic downgrade -1
     ```
4. **Approval & State Safety:** AAE enforces cryptographic state hashing and append-only audit trails. All approvals consumed during the incident remain in `CONSUMED` status to guarantee no duplicate execution occurs upon rollback.
5. **Post-Incident Analysis:** Collect container logs and inspect `/health` and audit trails.
