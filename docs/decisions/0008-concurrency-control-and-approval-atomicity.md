# ADR 0008: Concurrency Control and Approval Consumption Atomicity

## Status
ACCEPTED

## Context
Deploying automation workflows to production requires strict safety guarantees:
1. Approval tokens must be single-use and cannot be replayed across multiple concurrent deployments.
2. Concurrent workflow version allocation must never yield duplicate committed version numbers for the same aggregate.
3. Deployment authorization transactions must be atomic: if deployment record creation fails or conditions are not met, the entire transaction rolls back and the approval remains active.

## Decision
1. **Single-Winner Conditional Update for Approvals**:
   - Approvals are consumed using a conditional SQL update:
     ```sql
     UPDATE approvals
     SET status = 'CONSUMED',
         consumed_at = :now,
         consumed_by_action_id = :action_id
     WHERE id = :approval_id AND status = 'ACTIVE'
     ```
   - If rowcount is 0, the repository raises `StaleApprovalError`, rejecting concurrent or replay attempts immediately.

2. **Atomic Version Number Allocation**:
   - `WorkflowRepository.create_version_atomic` executes parent row locking via `with_for_update()` in PostgreSQL.
   - A database unique constraint `uq_workflow_versions_number` (`workflow_id`, `version_number`) enforces uniqueness at the database engine level, rejecting race conditions with `IntegrityError`.
   - Gap-free version numbering is explicitly not required; failed/rolled-back transactions leave gaps, but duplicate committed versions are impossible.

3. **Unit of Work Transaction Boundary**:
   - Deployment authorization and execution creation are encapsulated within `UnitOfWork`.
   - `authorize_and_create_deployment(...)` verifies `AgentState.APPROVED`, validates target version match against approval, consumes the approval atomically, records the deployment, updates workflow status, and records an immutable audit event in a single database transaction.

## Consequences
- Race conditions during concurrent deployments are eliminated; exactly one deployment succeeds per active approval.
- Concurrency control operates at both the application logic level (conditional update, state checks) and the database engine level (unique constraints, row locking).
- Rollbacks leave approvals intact for subsequent valid retries if transient errors occur prior to commit.
