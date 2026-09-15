# ADR 0005: Pure Domain Boundaries and Framework Isolation

## Status
ACCEPTED

## Context
Per the AAE Architecture and Phase 1 Plan Review Corrections, the core domain model must represent business automation concepts without coupling to persistence engines (PostgreSQL/SQLAlchemy), API frameworks (FastAPI), serialization libraries (Pydantic), provider adapters (n8n), or AI model SDKs.

## Decision
1. **Zero External Framework Dependencies in Domain**:
   `app/domain/` uses exclusively the Python standard library (`dataclasses`, `enum`, `uuid`, `datetime`, `typing`).
   Pydantic, SQLAlchemy, Alembic, FastAPI, and httpx are prohibited from being imported anywhere inside `app/domain/`.

2. **Domain Entities vs. Value Objects**:
   - Entities (`Project`, `Requirement`, `Specification`, `SpecificationVersion`, `Workflow`, `WorkflowVersion`, `Execution`, `Approval`, `Deployment`, `RepairAttempt`, `AuditEvent`) maintain explicit UUID identity.
   - Value Objects (`RequirementItem`, `ExecutionResult`, `FailureRecord`, `DiagnosticFinding`, `AgentStateTransition`) are immutable (`frozen=True`).

3. **Separation of Operational and Maturity Statuses**:
   - `WorkflowStatus` (`DRAFT`, `ACTIVE`, `INACTIVE`, `ARCHIVED`) governs provider container state.
   - `WorkflowVersionStatus` (`DRAFT`, `VALIDATED`, `TESTED`, `APPROVED`, `DEPLOYED`, `SUPERSEDED`) governs engineering maturity.
   - `AgentState` governs task orchestration.

4. **Capability Limitation Placement**:
   `CapabilityLimitationError` remains at the provider boundary (`app/providers/base.py`) and is not placed in the core domain error hierarchy.

## Consequences
- Complete architectural purity and independence from database, provider, or UI shifts.
- Fast, reproducible, pure in-memory testing without mocks or daemon dependencies.
- AST-level isolation tests guarantee no accidental framework leaks into domain code.
