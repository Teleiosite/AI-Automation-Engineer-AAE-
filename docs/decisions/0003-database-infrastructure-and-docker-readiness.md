# ADR 0003: Database Infrastructure, SQLite Boundary, and Docker Service Readiness

## Status
ACCEPTED

## Context
1. **Architecture Requirement**: The AAE Architecture mandates PostgreSQL as the primary production and development database, managed via SQLAlchemy ORM and Alembic migrations.
2. **Local Environment Audit**:
   - Docker version 29.5.3 and Docker Compose v5.1.4 are installed on the Windows host.
   - Docker Desktop application is located at `C:\Program Files\Docker\Docker\Docker Desktop.exe`.
   - The underlying Windows service `com.docker.service` is currently stopped.
   - Standard non-elevated user processes cannot control Windows services (`Start-Service : Cannot open com.docker.service service on computer '.'`).
   - PostgreSQL is not installed as a local Windows service on port 5432.
   - Therefore, a live PostgreSQL database server is currently unavailable during this non-elevated execution session.

## Decision

### 1. Application Runtime Boundary: PostgreSQL Required
- Application runtime requires PostgreSQL.
- The application will **never** silently fall back to SQLite in production or standard local runtime mode.
- If PostgreSQL is unreachable upon startup or during operation:
  - Application startup records a structured error log.
  - The readiness endpoint `GET /ready` returns HTTP 503 / degraded status (`status: degraded`, `components: { database: { status: "unreachable" } }`).
  - Secrets and credentials must never be exposed in the error or health responses.

### 2. Isolated Automated Testing Boundary
- SQLite (in-memory or temporary file) is permitted **strictly and exclusively** within isolated unit tests where testing database session wiring or schema migration mechanics without external daemon dependencies is necessary.
- SQLite must never be exposed or configured as an application-level runtime engine.

### 3. Docker Service Environment Status
- We document the current environment state truthfully:
  ```text
  Docker installed: YES (v29.5.3)
  Docker service currently unavailable: YES (com.docker.service stopped, requires administrator elevation)
  PostgreSQL external dependency currently unavailable: YES
  ```
- All Phase 0 bootstrap foundations (SQLAlchemy setup, Alembic migration environment, `docker-compose.yml`, health checks, connection error handling) are implemented and verified.
- Full live database migration against PostgreSQL will be executed once Docker Desktop is launched with administrative elevation.

## Consequences
- Strict separation between production database requirements and test isolation.
- No silent, insecure runtime degradation to SQLite.
- Clear operational prerequisites documented for launching the database via Docker Compose.
