# ADR 0006: Deterministic Agent Lifecycle and State Machine

## Status
ACCEPTED

## Context
Autonomous AI agents operating on real-world automation platforms must be constrained by deterministic state machines to prevent arbitrary code generation, unauthorized deployments, and unverified repairs.

## Decision

### 1. Authoritative 21-State Architecture
The AAE lifecycle consists of 17 active states and 4 terminal states strictly derived from `SKILLS/AAE Agent Specification.md` §4-5:
- Active: `INTAKE`, `ANALYSING`, `CLARIFICATION_REQUIRED`, `SPECIFICATION_READY`, `PLANNING`, `BUILDING`, `VALIDATING`, `TESTING`, `FAILED`, `DIAGNOSING`, `REPAIRING`, `RETESTING`, `READY_FOR_APPROVAL`, `APPROVED`, `DEPLOYING`, `DEPLOYED`, `MONITORING`.
- Terminal: `COMPLETED`, `BLOCKED`, `CANCELLED`, `FAILED_PERMANENTLY`.

### 2. Transition Matrix & Governance Invariants
- Direct shortcuts (e.g. `INTAKE → DEPLOYING`, `BUILDING → DEPLOYED`, `TESTING → DEPLOYED`) are prohibited and raise `InvalidStateTransitionError`.
- Terminal states are fail-closed: no transitions out of terminal states are permitted.

### 3. Approval Replay Protection
- `Approval` instances are bound to specific `target_type`, `target_id`, `target_version`, and `environment`.
- An approval is single-use and consumed upon deployment authorization via `approval.consume(action_id)`. Re-using a consumed approval raises `StaleApprovalError`.
- Approvals for Version N do not authorize Version N+1.

### 4. Cross-Aggregate Deployment Policy
Deployment authorization is decoupled into a stateless domain service: `DeploymentAuthorizationPolicy`. It coordinates `Deployment`, `Workflow`, `WorkflowVersion`, `Approval`, and `AgentState` without bloating entity aggregates.

## Consequences
- Impossible for an AI model or caller to bypass human-in-the-loop approval or testing stages.
- Replay attacks and stale deployment authorizations fail closed deterministically.
