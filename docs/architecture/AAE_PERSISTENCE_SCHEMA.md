# AAE Persistence Schema Reference

## Overview
This document defines the durable relational persistence schema for the AI Automation Engineer (AAE) platform, implemented using PostgreSQL 16 dialect standards and managed via Alembic migrations.

The persistence layer strictly maps to the pure domain model (`app/domain/`) through isolated Data Mappers (`app/db/mappers/`) and Repositories (`app/db/repositories/`), preventing ORM leaks into business logic.

---

## 1. Table Summary

| Table Name | Aggregate / Concept | Primary Key | Soft / Hard Delete / Immutability |
| :--- | :--- | :--- | :--- |
| `projects` | Project Aggregate Root | UUID | Hard Delete (RESTRICT if children exist) |
| `requirements` | Requirement Aggregate Root | UUID | Hard Delete (CASCADE to items) |
| `requirement_items` | Requirement Item Entity | UUID | CASCADE on parent Requirement deletion |
| `specifications` | Specification Aggregate Root | UUID | Hard Delete (RESTRICT from workflows) |
| `specification_versions` | Specification Version Entity | UUID | Immutable when APPROVED |
| `workflows` | Workflow Aggregate Root | UUID | Hard Delete (RESTRICT from deployments/executions) |
| `workflow_versions` | Workflow Version Entity | UUID | Immutable when APPROVED/DEPLOYED |
| `executions` | Execution Aggregate Root | UUID | Append-only / Read-only history |
| `approvals` | Approval Entity | UUID | State machine / Single-use consumption |
| `deployments` | Deployment Entity | UUID | Append-only deployment audit record |
| `failure_records` | Diagnostic Failure Record | UUID | RESTRICT (preserves failure history; prevents orphan execution deletion) |
| `diagnostic_findings` | Diagnostic Finding Item | UUID | RESTRICT (preserves diagnostic findings) |
| `repair_attempts` | Repair Attempt Entity | UUID | Append-only repair execution record |
| `audit_events` | Audit Trail Aggregate | UUID | Strictly APPEND-ONLY (No UPDATE/DELETE) |

---

## 2. Table Specifications

### 2.1 `projects`
Stores high-level workspace/project containers.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `name`: VARCHAR(255), NOT NULL, UNIQUE (`uq_projects_name`)
  - `description`: TEXT, NULL
  - `created_at`: TIMESTAMPTZ, NOT NULL
  - `updated_at`: TIMESTAMPTZ, NOT NULL
- **Relationships & Constraints**:
  - Outbound to: `requirements` (RESTRICT), `specifications` (RESTRICT), `workflows` (RESTRICT).
- **Indexes**:
  - `ix_projects_name` (BTREE on `name`)

### 2.2 `requirements`
Stores the aggregate root for gathered user requirements.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `project_id`: UUID (FK `projects.id`, ON DELETE RESTRICT), NOT NULL
  - `original_request`: TEXT, NOT NULL
  - `created_by`: VARCHAR(100), NOT NULL default `user`
  - `version`: INTEGER, NOT NULL default 1
  - `assumptions`: JSONB / JSON, NOT NULL default `[]`
  - `ambiguities`: JSONB / JSON, NOT NULL default `[]`
  - `conflicts`: JSONB / JSON, NOT NULL default `[]`
  - `created_at`: TIMESTAMPTZ, NOT NULL
- **Relationships & Constraints**:
  - Has many `requirement_items` (CASCADE delete orphan).

### 2.3 `requirement_items`
Discrete categorized requirements derived from raw user requests.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `requirement_id`: UUID (FK `requirements.id`, ON DELETE CASCADE), NOT NULL
  - `type`: VARCHAR(50), NOT NULL
  - `description`: TEXT, NOT NULL
  - `confidence`: VARCHAR(50), NOT NULL
  - `risk`: VARCHAR(50), NOT NULL default `LOW`
  - `notes`: TEXT, NULL
- **Indexes**:
  - `ix_requirement_items_requirement_id`

### 2.4 `specifications`
Functional automation specification aggregate root.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `project_id`: UUID (FK `projects.id`, ON DELETE RESTRICT), NOT NULL
  - `requirement_id`: UUID (FK `requirements.id`, ON DELETE RESTRICT), NOT NULL
  - `status`: VARCHAR(50), NOT NULL default `DRAFT`
  - `current_version_number`: INTEGER, NOT NULL default 1
  - `created_at`: TIMESTAMPTZ, NOT NULL
  - `updated_at`: TIMESTAMPTZ, NOT NULL
- **Relationships**:
  - Has many `specification_versions` (CASCADE delete orphan, ordered by version_number).

### 2.5 `specification_versions`
Versioned immutable specifications.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `specification_id`: UUID (FK `specifications.id`, ON DELETE RESTRICT), NOT NULL
  - `version_number`: INTEGER, NOT NULL
  - `structured_content`: JSONB / JSON, NOT NULL default `{}`
  - `is_approved`: BOOLEAN, NOT NULL default false
  - `created_at`: TIMESTAMPTZ, NOT NULL
- **Constraints**:
  - `uq_specification_versions_number`: UNIQUE (`specification_id`, `version_number`)
- **Indexes**:
  - `idx_spec_versions_lookup` (`specification_id`, `version_number`)

### 2.6 `workflows`
Executable workflow container mapped to n8n provider artifacts.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `project_id`: UUID (FK `projects.id`, ON DELETE RESTRICT), NOT NULL
  - `name`: VARCHAR(255), NOT NULL
  - `environment`: VARCHAR(50), NOT NULL default `development`
  - `status`: VARCHAR(50), NOT NULL default `DRAFT` (`DRAFT`, `ACTIVE`, `INACTIVE`, `ARCHIVED`)
  - `current_version_id`: UUID (FK `workflow_versions.id`, ON DELETE SET NULL, deferrable), NULL
  - `created_at`: TIMESTAMPTZ, NOT NULL
  - `updated_at`: TIMESTAMPTZ, NOT NULL
- **Indexes**:
  - `ix_workflows_project_id`
  - `ix_workflows_status`

### 2.7 `workflow_versions`
Versioned immutable workflow definition payloads.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `workflow_id`: UUID (FK `workflows.id`, ON DELETE CASCADE), NOT NULL
  - `version_number`: INTEGER, NOT NULL
  - `specification_version_id`: UUID, NOT NULL
  - `definition`: JSONB / JSON, NOT NULL default `{}`
  - `status`: VARCHAR(50), NOT NULL default `DRAFT` (`DRAFT`, `VALIDATED`, `TESTED`, `APPROVED`, `DEPLOYED`, `SUPERSEDED`)
  - `change_reason`: TEXT, NOT NULL default `Initial version`
  - `created_by`: VARCHAR(100), NOT NULL default `agent`
  - `provider_version_id`: VARCHAR(255), NULL
  - `created_at`: TIMESTAMPTZ, NOT NULL
- **Constraints**:
  - `uq_workflow_versions_number`: UNIQUE (`workflow_id`, `version_number`)
- **Indexes**:
  - `idx_wf_versions_lookup` (`workflow_id`, `version_number`)

### 2.8 `executions`
Runtime execution tracking. Contains embedded `ExecutionResult` fields directly to avoid 1-to-1 table overhead.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `workflow_id`: UUID (FK `workflows.id`, ON DELETE RESTRICT), NOT NULL
  - `workflow_version_id`: UUID (FK `workflow_versions.id`, ON DELETE RESTRICT), NOT NULL
  - `status`: VARCHAR(50), NOT NULL default `QUEUED`
  - `trigger_type`: VARCHAR(50), NOT NULL default `MANUAL`
  - `started_at`: TIMESTAMPTZ, NOT NULL
  - `finished_at`: TIMESTAMPTZ, NULL
  - `correlation_id`: VARCHAR(255), NULL
  - `result_technical_status`: VARCHAR(50), NULL
  - `result_semantic_status`: VARCHAR(50), NULL
  - `result_duration_ms`: FLOAT, NULL
  - `result_output_data`: JSONB / JSON, NULL
  - `result_error_message`: TEXT, NULL
  - `result_error_details`: JSONB / JSON, NULL
- **Indexes**:
  - `idx_executions_workflow` (`workflow_id`, `workflow_version_id`)
  - `idx_executions_correlation_id` (`correlation_id`)

### 2.9 `approvals`
Human-in-the-loop and security deployment gate authorization records.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `target_type`: VARCHAR(50), NOT NULL
  - `target_id`: UUID, NOT NULL
  - `target_version`: INTEGER, NOT NULL
  - `action`: VARCHAR(50), NOT NULL default `deploy`
  - `actor`: VARCHAR(100), NOT NULL
  - `environment`: VARCHAR(50), NOT NULL default `production`
  - `status`: VARCHAR(50), NOT NULL default `PENDING`
  - `created_at`: TIMESTAMPTZ, NOT NULL
  - `decided_at`: TIMESTAMPTZ, NULL
  - `expires_at`: TIMESTAMPTZ, NULL
  - `consumed_at`: TIMESTAMPTZ, NULL
  - `consumed_by_action_id`: UUID, NULL
- **Indexes**:
  - `idx_approvals_target` (`target_type`, `target_id`, `target_version`)
  - `ix_approvals_status`

### 2.10 `deployments`
Immutable deployment records resulting from atomic approval consumption.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `workflow_id`: UUID (FK `workflows.id`, ON DELETE RESTRICT), NOT NULL
  - `workflow_version_number`: INTEGER, NOT NULL
  - `approval_id`: UUID (FK `approvals.id`, ON DELETE RESTRICT), NOT NULL
  - `target_environment`: VARCHAR(50), NOT NULL
  - `deployed_by`: VARCHAR(100), NOT NULL
  - `status`: VARCHAR(50), NOT NULL default `SUCCESS`
  - `rollback_target_version`: INTEGER, NULL
  - `metadata`: JSONB / JSON, NOT NULL default `{}`
  - `created_at`: TIMESTAMPTZ, NOT NULL
- **Indexes**:
  - `ix_deployments_workflow_id`
  - `ix_deployments_approval_id`

### 2.11 `failure_records` & `diagnostic_findings`
Persists failure traces and automated triage results.
- **`failure_records`**:
  - `id`: UUID (PK, default uuid4)
  - `execution_id`: UUID (FK `executions.id`, ON DELETE RESTRICT), NOT NULL
  - `category`: VARCHAR(50), NOT NULL
  - `severity`: VARCHAR(50), NOT NULL
  - `failed_component`: VARCHAR(255), NOT NULL
  - `message`: TEXT, NOT NULL
  - `technical_details`: JSONB / JSON, NULL
  - `timestamp`: TIMESTAMPTZ, NOT NULL
- **`diagnostic_findings`**:
  - `id`: UUID (PK, default uuid4)
  - `failure_id`: UUID (FK `failure_records.id`, ON DELETE RESTRICT), NOT NULL
  - `likely_cause`: TEXT, NOT NULL
  - `confidence`: VARCHAR(50), NOT NULL
  - `recommended_action`: TEXT, NOT NULL
  - `timestamp`: TIMESTAMPTZ, NOT NULL

### 2.12 `repair_attempts`
Automated repair execution attempts and validation outcomes.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `workflow_id`: UUID (FK `workflows.id`, ON DELETE RESTRICT), NOT NULL
  - `target_version_number`: INTEGER, NOT NULL
  - `failure_id`: UUID (FK `failure_records.id`, ON DELETE RESTRICT), NOT NULL
  - `diagnostic_id`: UUID (FK `diagnostic_findings.id`, ON DELETE RESTRICT), NOT NULL
  - `proposed_change`: JSONB / JSON, NOT NULL
  - `risk`: VARCHAR(50), NOT NULL default `LOW`
  - `status`: VARCHAR(50), NOT NULL default `PROPOSED`
  - `initiated_at`: TIMESTAMPTZ, NOT NULL
  - `completed_at`: TIMESTAMPTZ, NULL
- **Indexes**:
  - `idx_repair_attempts_workflow` (`workflow_id`)

### 2.13 `audit_events`
Append-only immutable audit trail for security, governance, and compliance.
- **Columns**:
  - `id`: UUID (PK, default uuid4)
  - `event_type`: VARCHAR(100), NOT NULL
  - `actor`: VARCHAR(255), NOT NULL
  - `target_type`: VARCHAR(100), NOT NULL
  - `target_id`: VARCHAR(255), NOT NULL
  - `correlation_id`: VARCHAR(255), NULL
  - `outcome`: VARCHAR(50), NOT NULL default `SUCCESS`
  - `metadata`: JSONB / JSON, NOT NULL default `{}`
  - `timestamp`: TIMESTAMPTZ, NOT NULL
- **Indexes**:
  - `idx_audit_events_target` (`target_type`, `target_id`)
  - `idx_audit_events_timestamp` (`timestamp`)
  - `idx_audit_events_correlation` (`correlation_id`)
  - `ix_audit_events_event_type` (`event_type`)
- **Immutability Enforcement**:
  - `AuditRepository` exposes only `append(...)` and read-only query methods (`get`, `list_for_target`, `list_recent`).
  - No `update` or `delete` methods exist.

---

## 3. JSONB Schema Contracts

| Table | Column | Expected Structure | Notes |
| :--- | :--- | :--- | :--- |
| `specification_versions` | `structured_content` | `Dict[str, Any]` | Functional specification graph definition (nodes, edges, policies) |
| `workflow_versions` | `definition` | `Dict[str, Any]` | Complete n8n workflow JSON structure |
| `executions` | `result_output_data` | `Optional[Dict[str, Any]]` | Execution output payloads |
| `executions` | `result_error_details` | `Optional[Dict[str, Any]]` | Structured error details and diagnostics context |
| `failure_records` | `technical_details` | `Optional[Dict[str, Any]]` | Stack trace and component diagnostic state |
| `repair_attempts` | `proposed_change` | `Dict[str, Any]` | Structural patch details and proposed repair steps |
| `deployments` | `metadata` | `Dict[str, Any]` | Deployment run metadata, hashes, commit tags |
| `audit_events` | `metadata` | `Dict[str, Any]` | Sanitized audit payload (redacted of secrets) |
