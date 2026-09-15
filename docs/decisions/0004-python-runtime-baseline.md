# ADR 0004: Python Runtime Baseline Selection and Verification

## Status
ACCEPTED

## Context
Per Phase 0 Plan Review Correction #6, the Python runtime baseline must be evaluated based on package compatibility, stability, and runtime verification, rather than blindly adopting whatever version happens to be present.

## Evaluation & Evidence

1. **Host Python Installation**:
   - Location: `C:\Python314\python.exe`
   - Version: `Python 3.14.6`
   - Pip version: `26.2.1`

2. **Package Compatibility Testing**:
   During Phase 0 bootstrap, installation of the core AAE stack was verified in a clean virtual environment:
   - `fastapi` 0.141.1 (pure Python wheel)
   - `uvicorn` 0.53.0 (pure Python wheel)
   - `pydantic` 2.13.5 with `pydantic-core` 2.46.5 (native `cp314-win_amd64` wheel)
   - `pydantic-settings` 2.15.0 (pure Python wheel)
   - `sqlalchemy` 2.0.52 with `greenlet` 3.5.6 (native `cp314-win_amd64` wheel)
   - `alembic` 1.20.0 (pure Python wheel)
   - `psycopg` 3.3.5 with `psycopg-binary` 3.3.5 (native `cp314-win_amd64` wheel)
   - `httpx` 0.28.1 (pure Python wheel)
   - `pytest` 9.1.1 (pure Python wheel)

All core dependencies installed with pre-compiled native binaries or pure wheels without requiring a local C compiler toolchain.

## Decision
1. The project dependency configuration in `pyproject.toml` specifies `requires-python = ">=3.11"`.
2. The current local development environment is verified to execute reliably on Python 3.14.6 using the installed `.venv`.
3. Standard Python packaging guidelines are followed to ensure cross-version compatibility across Python 3.11, 3.12, 3.13, and 3.14.

## Consequences
- The development environment is verified and reproducible.
- Dependencies are pinned with modern versions supporting Python 3.11+.
