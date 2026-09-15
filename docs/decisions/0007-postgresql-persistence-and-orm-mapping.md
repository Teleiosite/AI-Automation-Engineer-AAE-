# ADR 0007: PostgreSQL Persistence and ORM Mapping Architecture

## Status
ACCEPTED

## Context
Phase 1 established a pure domain model in `app/domain/` with zero external dependencies, verified via AST-level isolation tests. Phase 2 introduces durable persistence using PostgreSQL 16 and SQLAlchemy 2.0. The persistence layer must support durable relational storage, version concurrency, atomic state transitions, and Alembic migrations while strictly preserving the integrity and isolation of the pure domain model.

## Decision
1. **Explicit Data Mapper Pattern**:
   - SQLAlchemy ORM models (`app/db/models/`) are strictly isolated from domain models (`app/domain/models/`).
   - Bidirectional mappers (`app/db/mappers/`) explicitly convert between domain entities/value objects and ORM persistence models.
   - Domain models never inherit from SQLAlchemy `Base`, nor do they contain database-specific decorators or foreign key references.

2. **Repository Abstraction**:
   - All persistence interactions occur via repository interfaces (`app/db/repositories/`).
   - Repositories accept and return pure domain entities, completely encapsulating SQLAlchemy `Session`, ORM models, and dialect-specific queries.

3. **Domain Model Immutability and State Transitions**:
   - Deployed workflow versions and approved specifications are verified for immutability at the repository level (`ImmutableArtifactError`).
   - Audit events are strictly append-only; the `AuditRepository` does not expose `update` or `delete` methods.

4. **Timestamp and Dialect Normalization**:
   - All timestamps are enforced as UTC-aware (`datetime.now(timezone.utc)`), with mapper-level defensive normalization via `ensure_utc`.
   - JSON payloads use `JSON().with_variant(JSONB, "postgresql")` to guarantee native PostgreSQL JSONB indexing and compatibility across SQLite test suites.

## Consequences
- The domain layer remains 100% pure standard library Python, free of database and ORM leaks.
- Database schema changes require updates to ORM models, migrations, and mappers without altering core business rules.
- Test suites can run in-memory and against file-based SQLite engines while remaining 100% compatible with production PostgreSQL 16 DDL.
