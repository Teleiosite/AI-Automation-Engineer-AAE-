# AI AUTOMATION ENGINEER
## System Architecture

**Product:** AI Automation Engineer  
**Codename:** AAE  
**Owner:** Teleiocraft Solutions  
**Document:** AAE Architecture  
**Version:** 1.0  
**Status:** Architecture Baseline  

**Depends On:**
- AI Automation Engineer Master Product Requirements Document
- N8N_CAPABILITY_MAP.md
- N8N_CONTROL_SURFACE.md
- AAE_REQUIREMENT_TRANSLATION_SPEC.md
- AAE_AGENT_SPECIFICATION.md

---

# 1. Architecture Purpose

This document defines the technical architecture of the AI Automation Engineer (AAE).

The architecture translates the product requirements and agent specification into a concrete software system capable of:

- receiving automation requirements
- translating requirements into structured specifications
- checking provider capabilities
- planning automation implementations
- constructing workflows
- validating workflows
- executing tests
- inspecting executions
- diagnosing failures
- proposing repairs
- applying authorised repairs
- re-testing
- requesting approval
- deploying approved changes
- monitoring automations
- maintaining an audit trail

The architecture must support the initial n8n implementation while avoiding unnecessary coupling between the AAE core and n8n.

---

# 2. Architectural Principle

AAE must be built as an **engineering control system around automation providers**, not as a chatbot that directly manipulates n8n.

The fundamental architecture is:

```text
User
  ↓
AAE API
  ↓
AAE Agent Orchestrator
  ↓
Agent State / Engineering Context
  ↓
Provider-Neutral Tool Layer
  ↓
Automation Provider Interface
  ↓
n8n Adapter
  ↓
n8n Runtime
```

Supporting systems surround the core:

```text
                    ┌───────────────────┐
                    │      User         │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │     AAE API       │
                    └─────────┬─────────┘
                              │
                              ▼
              ┌─────────────────────────────┐
              │     AAE Agent Orchestrator  │
              └──────────────┬──────────────┘
                             │
       ┌─────────────────────┼──────────────────────┐
       │                     │                      │
       ▼                     ▼                      ▼
 Requirement             Planning              Validation
 Engine                  Engine                 Engine
       │                     │                      │
       └─────────────────────┼──────────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Provider Tool Layer  │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Provider Interface   │
                  └──────────┬───────────┘
                             │
                             ▼
                     ┌───────────────┐
                     │ n8n Adapter   │
                     └───────┬───────┘
                             │
                    ┌────────┴─────────┐
                    │                  │
                    ▼                  ▼
               n8n REST API         Webhooks
```

---

# 3. Architectural Goals

AAE architecture must optimise for:

1. correctness
2. safety
3. auditability
4. testability
5. provider independence
6. maintainability
7. observability
8. controlled autonomy
9. capability truthfulness
10. future extensibility

The architecture must not optimise primarily for:

- maximum agent autonomy
- minimum code
- maximum AI usage
- maximum workflow generation speed

---

# 4. Technology Baseline

Initial implementation:

| Layer | Technology |
|---|---|
| Primary language | Python |
| API framework | FastAPI |
| Database | PostgreSQL |
| ORM / database layer | SQLAlchemy |
| Validation | Pydantic |
| Agent orchestration | Python application layer |
| Automation provider | n8n |
| Initial provider adapter | n8n Adapter |
| API communication | HTTP/REST |
| Testing | pytest |
| Containerisation | Docker |
| Logging | Structured JSON logging |
| Authentication | Application-level authentication |
| Secrets | Environment/secret manager |
| Migrations | Alembic |

The exact AI model provider is intentionally not hard-coded into the architecture.

AAE should support a model abstraction layer.

---

# 5. High-Level Components

The initial AAE system consists of:

```text
AAE API
Agent Orchestrator
Requirement Engine
Specification Manager
Planning Engine
Workflow Builder
Validation Engine
Testing Engine
Diagnosis Engine
Repair Engine
Approval Engine
Deployment Engine
Monitoring Engine
Capability Registry
Provider Tool Layer
n8n Adapter
AI Model Gateway
State Manager
Audit Service
Security Policy Engine
Database
Observability Layer
```

---

# 6. Component Responsibilities

## 6.1 AAE API

The API is the external interface to AAE.

Responsibilities:

- receive user requests
- expose project information
- expose agent runs
- expose specifications
- expose workflow information
- expose validation results
- expose test results
- expose approvals
- expose deployment status
- expose monitoring information

The API must not contain core agent reasoning.

---

# 7. Agent Orchestrator

The Agent Orchestrator is the central control component.

Responsibilities:

- manage agent state
- coordinate engineering phases
- invoke appropriate engines
- enforce state transitions
- enforce approval gates
- manage retries
- handle escalation
- maintain Agent Run context
- coordinate tool calls

Conceptually:

```text
User Request
     ↓
Agent Orchestrator
     ├── Requirement Engine
     ├── Planning Engine
     ├── Workflow Builder
     ├── Validation Engine
     ├── Testing Engine
     ├── Diagnosis Engine
     ├── Repair Engine
     ├── Approval Engine
     └── Deployment Engine
```

The orchestrator is responsible for **control**, not for implementing every specialist function itself.

---

# 8. Requirement Engine

The Requirement Engine implements:

`AAE_REQUIREMENT_TRANSLATION_SPEC.md`

Responsibilities:

- analyse natural language
- extract requirements
- classify requirements
- identify ambiguity
- identify conflicts
- identify assumptions
- identify risks
- identify required capabilities
- generate structured specification
- determine whether clarification is necessary

It must not directly create or deploy workflows.

---

# 9. Specification Manager

The Specification Manager stores and controls structured automation specifications.

Responsibilities:

- create specifications
- version specifications
- store assumptions
- store clarifications
- record approval
- detect superseded versions
- provide authoritative specification to downstream components

The approved specification becomes the implementation contract.

---

# 10. Planning Engine

The Planning Engine converts an approved specification into an implementation plan.

Example:

```text
Specification
     ↓
Implementation Plan
     ↓
Workflow Design
     ↓
Node/Component Plan
     ↓
Test Plan
```

The planning engine must check capabilities before selecting provider-specific mechanisms.

---

# 11. Workflow Builder

The Workflow Builder constructs the automation implementation.

Responsibilities:

- generate workflow structure
- configure nodes
- configure connections
- create expressions
- configure error paths
- produce provider-specific workflow representation

The Workflow Builder should operate through a provider abstraction rather than embedding n8n API calls directly into the agent.

---

# 12. Validation Engine

The Validation Engine performs pre-execution validation.

Two primary modes:

```text
Structural Validation
Semantic Validation
```

Structural validation determines whether the implementation is technically valid.

Semantic validation determines whether the implementation matches the approved specification.

---

# 13. Testing Engine

The Testing Engine executes controlled tests and evaluates results.

Responsibilities:

- generate test cases
- execute test cases
- capture execution IDs
- inspect execution results
- evaluate expected outputs
- distinguish technical success from semantic success
- run regression tests
- produce test reports

The Testing Engine must never assume:

```text
execution status = success
```

means:

```text
business requirement = satisfied
```

---

# 14. Diagnosis Engine

The Diagnosis Engine analyses failed executions.

Input:

```text
Workflow
Workflow Version
Execution
Execution Data
Error
Execution Path
Test Expectation
```

Output:

```text
Failure Classification
Observed Evidence
Root Cause Hypothesis
Confidence
Affected Component
Recommended Repair
```

Diagnosis must distinguish evidence from hypothesis.

---

# 15. Repair Engine

The Repair Engine creates controlled workflow modifications.

Responsibilities:

- analyse diagnosis
- create repair proposal
- classify risk
- identify affected components
- generate replacement workflow/version
- request approval where required
- apply authorised repair
- trigger validation and testing

The Repair Engine must not operate as unrestricted self-modifying code.

---

# 16. Approval Engine

The Approval Engine controls human authorisation.

Responsibilities:

- determine whether approval is required
- create approval requests
- record approval decisions
- associate approval with specification version
- associate approval with workflow version
- enforce approval before deployment

Approval must be explicit.

Silence must never be interpreted as approval.

---

# 17. Deployment Engine

The Deployment Engine manages controlled deployment.

Responsibilities:

- verify target environment
- verify approved version
- verify validation
- verify tests
- verify security requirements
- deploy
- record deployment
- verify deployment result
- initiate rollback where authorised and supported

---

# 18. Monitoring Engine

The Monitoring Engine observes deployed automations.

Initial monitoring should support:

- execution failures
- repeated failures
- abnormal error rates
- workflow inactivity
- authentication failures
- provider failures
- abnormal execution volume

Future monitoring may include business-level metrics.

---

# 19. Capability Registry

The Capability Registry records what the automation provider can actually support.

Example:

```text
Capability:
create_workflow

Status:
VERIFIED

Provider:
n8n

Environment:
local-development

Evidence:
runtime verification

Last Verified:
timestamp
```

Capability status:

```text
VERIFIED
DOCUMENTED
ENVIRONMENT_DEPENDENT
VERSION_DEPENDENT
PLAN_DEPENDENT
PERMISSION_DEPENDENT
UNKNOWN
UNSUPPORTED
```

The registry is a critical control component.

---

# 20. Provider Tool Layer

The Provider Tool Layer presents provider-neutral tools to the agent.

Initial logical tools:

```text
get_instance_info
list_workflows
get_workflow
create_workflow
update_workflow
execute_workflow
list_executions
get_execution
validate_workflow
get_node_metadata
```

Future:

```text
retry_execution
activate_workflow
deactivate_workflow
security_audit
delete_workflow
```

The tool layer must enforce:

- input validation
- permission checks
- risk checks
- audit logging
- provider routing
- error normalisation

---

# 21. Automation Provider Interface

The provider interface isolates AAE Core from specific automation platforms.

```python
class AutomationProvider:
    def list_workflows(self):
        ...

    def get_workflow(self, workflow_id):
        ...

    def create_workflow(self, workflow):
        ...

    def update_workflow(self, workflow_id, workflow):
        ...

    def activate_workflow(self, workflow_id):
        ...

    def deactivate_workflow(self, workflow_id):
        ...

    def delete_workflow(self, workflow_id):
        ...

    def execute_workflow(self, workflow_id, input_data):
        ...

    def list_executions(self, workflow_id=None):
        ...

    def get_execution(self, execution_id):
        ...

    def retry_execution(self, execution_id):
        ...

    def get_node_information(self, node_type):
        ...

    def validate_workflow(self, workflow):
        ...

    def get_instance_information(self):
        ...

    def run_security_audit(self, workflow_id):
        ...
```

Not every method is currently verified for n8n.

The interface may therefore contain capabilities that are initially:

```text
UNKNOWN
UNSUPPORTED
NOT_IMPLEMENTED
```

The architecture must not pretend that the interface itself proves provider support.

---

# 22. n8n Adapter

The n8n Adapter implements the provider interface for n8n.

Responsibilities:

- n8n authentication
- n8n REST calls
- webhook execution mechanisms
- n8n workflow representation
- n8n execution representation
- n8n error handling
- n8n-specific capability checks
- normalisation of n8n responses

Architecture:

```text
AAE Core
   ↓
AutomationProvider
   ↓
N8NAdapter
   ↓
n8n API / Webhook / Approved Mechanism
```

n8n-specific implementation must remain inside this boundary wherever practical.

---

# 23. Important n8n Architecture Constraint

AAE must **not depend on `/openapi.json` being available from n8n**.

The current verified environment returned Editor HTML from:

```text
GET /openapi.json
```

rather than an OpenAPI specification.

Therefore:

```text
n8n OpenAPI specification
        ↓
NOT A FOUNDATIONAL DEPENDENCY
```

AAE instead uses:

```text
Provider Adapter
+
Capability Registry
+
Official Documentation
+
Runtime Verification
```

This prevents the architecture from depending on an unavailable interface.

---

# 24. AI Model Gateway

The AI Model Gateway isolates the rest of AAE from a specific LLM provider.

Conceptual interface:

```python
class ModelProvider:
    def generate(self, request):
        ...

    def structured_output(self, request, schema):
        ...

    def analyse(self, request):
        ...
```

The gateway should support:

- model selection
- structured output
- token limits
- timeout
- retry policy
- model logging
- cost tracking
- provider fallback where appropriate

The model should not directly receive unrestricted credentials or privileged system state.

---

# 25. AI Reasoning Boundary

The architecture must enforce:

```text
AI Model
   ↓
Proposal
   ↓
Policy / Validation
   ↓
Tool Layer
   ↓
Execution
```

Not:

```text
AI Model
   ↓
Direct System Access
```

This is one of the most important security and reliability boundaries in AAE.

---

# 26. Agent State Store

Agent state must be persisted outside the LLM context.

The state store tracks:

- Agent Run
- current state
- specification
- workflow
- workflow version
- tests
- execution IDs
- diagnosis
- repairs
- approvals
- deployment
- monitoring

The LLM's conversation context is not the authoritative state store.

---

# 27. PostgreSQL Data Model

Initial core entities:

```text
projects
agent_runs
requirements
specifications
specification_versions
assumptions
clarifications
workflow_plans
workflow_versions
test_cases
test_runs
executions
diagnoses
repair_proposals
approvals
deployments
capabilities
audit_events
monitoring_events
```

Potential relationships:

```text
Project
  └── Agent Runs
        ├── Requirements
        ├── Specifications
        ├── Workflow Plans
        ├── Workflow Versions
        ├── Tests
        ├── Executions
        ├── Diagnoses
        ├── Repairs
        ├── Approvals
        ├── Deployments
        └── Audit Events
```

---

# 28. Agent Run Model

Each engineering task receives a unique Agent Run ID.

Example:

```text
AAE-RUN-2026-000001
```

The run records:

```text
id
project_id
request
current_state
environment
provider
started_at
completed_at
status
error
```

All significant actions reference the Agent Run.

---

# 29. Specification Model

A specification record should include:

```text
id
project_id
agent_run_id
version
status
original_request
objective
trigger
inputs
actions
conditions
outputs
integrations
failure_handling
security_requirements
success_criteria
assumptions
unknowns
risk_level
created_at
approved_at
approved_by
```

---

# 30. Workflow Version Model

Workflow versions should track:

```text
workflow_id
version_id
provider
provider_workflow_id
specification_version
definition
environment
status
created_at
created_by
```

Workflow definitions should be stored carefully to avoid accidental credential exposure.

---

# 31. Test Model

A test case contains:

```text
test_id
specification_id
workflow_version_id
name
purpose
input
expected_output
expected_status
risk_level
```

A test run contains:

```text
test_run_id
test_id
execution_id
actual_output
result
started_at
completed_at
error
```

---

# 32. Execution Model

Execution records should include:

```text
execution_id
provider
workflow_id
workflow_version_id
environment
status
started_at
completed_at
trigger
error
raw_reference
```

Large execution payloads should not necessarily be stored indefinitely in PostgreSQL.

Retention policy should be configurable.

---

# 33. Diagnosis Model

Diagnosis should include:

```text
diagnosis_id
execution_id
failure_category
observed_evidence
root_cause_hypothesis
confidence
affected_node
recommended_action
risk_level
created_at
```

The system should explicitly distinguish:

```text
Evidence
```

from:

```text
Hypothesis
```

---

# 34. Repair Model

Repair records:

```text
repair_id
diagnosis_id
workflow_version_before
workflow_version_after
change_summary
risk_level
approval_required
approval_id
validation_result
test_result
status
```

---

# 35. Approval Model

Approval records:

```text
approval_id
agent_run_id
specification_version
workflow_version
environment
action
requested_at
approved_at
approved_by
decision
comments
```

---

# 36. Audit Architecture

Every important mutation should produce an audit event.

Examples:

```text
workflow_created
workflow_updated
workflow_activated
workflow_deactivated
workflow_deleted
execution_started
repair_proposed
repair_applied
approval_requested
approval_granted
deployment_started
deployment_completed
rollback_started
rollback_completed
```

Audit records should be append-oriented.

AAE should not allow normal agent operations to silently rewrite historical audit records.

---

# 37. Security Policy Engine

The Security Policy Engine evaluates whether actions are permitted.

Input:

```text
Action
User
Agent
Target
Environment
Risk
Capability
Approval
```

Output:

```text
ALLOW
DENY
REQUIRE_APPROVAL
REQUIRE_CLARIFICATION
```

Example:

```text
Delete production workflow
        ↓
High/Critical Risk
        ↓
Approval Required
```

---

# 38. Permission Architecture

AAE should use least privilege.

Conceptual roles:

```text
Viewer
Engineer
Approver
Administrator
System
```

Example:

```text
Viewer
→ inspect

Engineer
→ build/test

Approver
→ approve deployment

Administrator
→ manage system/security
```

Exact permissions should be defined in the security policy document.

---

# 39. Environment Architecture

AAE should support environment separation:

```text
Development
     ↓
Test
     ↓
Staging
     ↓
Production
```

Not every deployment needs all four environments.

However, the architecture must support environment-specific credentials and provider connections.

---

# 40. Deployment Architecture

Preferred flow:

```text
AAE
 ↓
Validate
 ↓
Test
 ↓
Security Check
 ↓
Approval
 ↓
Deployment Engine
 ↓
Provider Adapter
 ↓
Target Environment
 ↓
Deployment Verification
```

---

# 41. Rollback Architecture

Where supported:

```text
Current Version
      ↓
Deploy New Version
      ↓
Verification
      ↓
Failure
      ↓
Previous Known-Good Version
```

Rollback capability must be provider-specific.

AAE must check capability status before promising automatic rollback.

---

# 42. Observability Architecture

AAE should expose:

```text
Logs
Metrics
Traces
Audit Events
Agent State
```

Initial implementation should prioritise structured logs and audit events.

Future implementation may add:

- OpenTelemetry
- metrics backend
- distributed tracing
- dashboards
- alerting

---

# 43. Error Architecture

Provider-specific errors should be normalised.

Example:

```text
n8n HTTP 401
        ↓
AUTHENTICATION_ERROR
```

```text
n8n HTTP 404
        ↓
RESOURCE_NOT_FOUND
```

```text
n8n HTTP 429
        ↓
RATE_LIMITED
```

```text
Workflow execution failure
        ↓
WORKFLOW_EXECUTION_ERROR
```

Normalised errors allow the core agent to remain provider-independent.

---

# 44. Error Envelope

Internal tool errors should follow a common structure:

```json
{
  "code": "AUTHENTICATION_ERROR",
  "message": "Provider authentication failed.",
  "provider": "n8n",
  "operation": "get_workflow",
  "retryable": false,
  "risk": "medium",
  "details": {}
}
```

Secrets must never appear in the error payload.

---

# 45. Request Flow

A normal automation request should follow:

```text
1. User submits request
        ↓
2. AAE creates Agent Run
        ↓
3. Requirement Engine analyses request
        ↓
4. Specification created
        ↓
5. Capability check
        ↓
6. Specification approval if required
        ↓
7. Planning Engine
        ↓
8. Workflow Builder
        ↓
9. Structural validation
        ↓
10. Semantic validation
        ↓
11. Test execution
        ↓
12. Result evaluation
        ↓
13. Approval
        ↓
14. Deployment
        ↓
15. Deployment verification
        ↓
16. Monitoring
```

---

# 46. Failure Flow

```text
Execution
   ↓
Failure
   ↓
Execution Inspection
   ↓
Diagnosis
   ↓
Root Cause Hypothesis
   ↓
Risk Classification
   ↓
Repair Proposal
   ↓
Approval if required
   ↓
Repair
   ↓
Validation
   ↓
Original Test
   ↓
Regression Tests
   ↓
Approval
   ↓
Deployment
```

---

# 47. Communication Boundaries

Components should communicate through explicit interfaces.

Example:

```text
Requirement Engine
        ↓
Specification Service

Specification Service
        ↓
Planning Engine

Planning Engine
        ↓
Workflow Builder

Workflow Builder
        ↓
Validation Engine

Validation Engine
        ↓
Testing Engine
```

This makes individual components independently testable.

---

# 48. Synchronous vs Asynchronous Processing

Simple operations may be synchronous.

Examples:

- retrieve workflow
- inspect specification
- validate small workflow

Long-running operations should be asynchronous.

Examples:

- workflow testing
- large execution inspection
- repair cycle
- deployment
- monitoring
- agent runs involving multiple tool calls

The API should return a job/run identifier for long-running operations.

---

# 49. Background Job Architecture

Future background processing may use:

```text
FastAPI
   ↓
Job Queue
   ↓
Worker
   ↓
Agent Orchestrator
```

The first implementation should avoid unnecessary infrastructure complexity.

A lightweight database-backed or process-based execution model may be sufficient for the MVP.

A dedicated queue can be introduced when workload requires it.

---

# 50. Concurrency Control

Before modifying a workflow:

```text
Read Current Version
        ↓
Check Version
        ↓
Plan Modification
        ↓
Write
```

If the version changed during the process:

```text
STOP
↓
REFRESH
↓
RECONCILE
```

AAE must not silently overwrite newer changes.

---

# 51. Idempotency Architecture

Important commands should support idempotency where appropriate.

Example:

```text
request_id
agent_run_id
operation_id
```

Repeated requests with the same idempotency key should not unintentionally create duplicate side effects.

---

# 52. Provider Adapter Contract

Every provider adapter should expose:

```text
Capability Discovery
Authentication
Resource Access
Resource Mutation
Execution
Execution Inspection
Validation
Security Operations
Error Normalisation
```

The n8n adapter is the first implementation.

Future providers can implement the same interface.

---

# 53. Future Provider Expansion

Potential future architecture:

```text
                  AAE Core
                     │
          ┌──────────┼──────────┐
          │          │          │
          ▼          ▼          ▼
       n8n        Provider B  Provider C
      Adapter      Adapter     Adapter
          │          │          │
          ▼          ▼          ▼
         n8n       Platform    Platform
```

The AAE core should not require rewriting when another provider is introduced.

---

# 54. API Boundary

Initial API groups:

```text
/projects
/agent-runs
/requirements
/specifications
/workflows
/tests
/executions
/diagnoses
/repairs
/approvals
/deployments
/capabilities
/audit
/monitoring
```

The API should expose state and actions without exposing internal implementation details unnecessarily.

---

# 55. Example API Flow

Request:

```http
POST /agent-runs
```

Payload:

```json
{
  "project_id": "project-001",
  "request": "When a new customer submits the form, add them to the CRM and send a welcome message."
}
```

Response:

```json
{
  "agent_run_id": "AAE-RUN-2026-000001",
  "state": "ANALYSING"
}
```

The client can then inspect:

```http
GET /agent-runs/AAE-RUN-2026-000001
```

---

# 56. Internal Event Model

AAE should use domain events internally where beneficial.

Examples:

```text
RequirementReceived
SpecificationCreated
SpecificationApproved
WorkflowBuilt
ValidationCompleted
TestCompleted
ExecutionFailed
DiagnosisCreated
RepairProposed
RepairApproved
RepairApplied
DeploymentStarted
DeploymentCompleted
MonitoringAlertCreated
```

Events should make the lifecycle observable.

---

# 57. Architecture Boundary: What AAE Owns

AAE owns:

- requirements
- specifications
- planning
- workflow construction
- validation
- testing
- diagnosis
- repair policy
- approval flow
- deployment control
- audit
- capability registry
- agent state

---

# 58. Architecture Boundary: What n8n Owns

n8n owns:

- workflow execution
- node runtime
- provider integrations
- execution engine
- workflow runtime state
- provider-specific credentials
- provider-specific execution mechanisms

AAE controls n8n through the supported control surface.

AAE must not attempt to duplicate n8n's execution engine.

---

# 59. Architecture Boundary: What the LLM Owns

The LLM assists with:

- language understanding
- reasoning
- planning
- generation
- diagnosis
- repair proposals
- explanations

The LLM does not own:

- authorization
- security policy
- capability truth
- audit integrity
- deployment approval
- credential management
- deterministic validation

---

# 60. MVP Architecture

The first implementation should remain intentionally small.

MVP:

```text
                ┌─────────────┐
                │   FastAPI   │
                └──────┬──────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Agent Orchestr. │
              └───────┬─────────┘
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
 Requirement       Planning       Validation
 Engine             Engine          Engine
       │              │              │
       └──────────────┼──────────────┘
                      ▼
                Testing Engine
                      │
                      ▼
                Tool Layer
                      │
                      ▼
                 n8n Adapter
                      │
                      ▼
                    n8n

              ┌─────────────────┐
              │   PostgreSQL    │
              └─────────────────┘
```

The first MVP should not begin with:

- Kubernetes
- microservice explosion
- complex event infrastructure
- multiple automation providers
- autonomous production repair
- distributed multi-agent systems

Those may become appropriate later.

---

# 61. Recommended Repository Structure

Initial repository:

```text
aae/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── projects.py
│   │   ├── agent_runs.py
│   │   ├── specifications.py
│   │   ├── workflows.py
│   │   ├── tests.py
│   │   ├── executions.py
│   │   ├── approvals.py
│   │   └── deployments.py
│   │
│   ├── agent/
│   │   ├── orchestrator.py
│   │   ├── state_machine.py
│   │   └── context.py
│   │
│   ├── requirements/
│   │   ├── analyser.py
│   │   ├── extractor.py
│   │   └── specification.py
│   │
│   ├── planning/
│   │   └── planner.py
│   │
│   ├── workflows/
│   │   ├── builder.py
│   │   └── models.py
│   │
│   ├── validation/
│   │   ├── structural.py
│   │   └── semantic.py
│   │
│   ├── testing/
│   │   ├── runner.py
│   │   └── evaluator.py
│   │
│   ├── diagnosis/
│   │   └── engine.py
│   │
│   ├── repair/
│   │   └── engine.py
│   │
│   ├── approval/
│   │   └── service.py
│   │
│   ├── deployment/
│   │   └── service.py
│   │
│   ├── monitoring/
│   │   └── service.py
│   │
│   ├── capabilities/
│   │   ├── registry.py
│   │   └── models.py
│   │
│   ├── providers/
│   │   ├── interface.py
│   │   └── n8n/
│   │       ├── adapter.py
│   │       ├── client.py
│   │       ├── models.py
│   │       └── errors.py
│   │
│   ├── tools/
│   │   ├── registry.py
│   │   └── permissions.py
│   │
│   ├── ai/
│   │   ├── gateway.py
│   │   ├── prompts.py
│   │   └── models.py
│   │
│   ├── security/
│   │   ├── policy.py
│   │   └── redaction.py
│   │
│   ├── audit/
│   │   └── service.py
│   │
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│   │   └── migrations/
│   │
│   └── config.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── provider/
│   ├── agent/
│   ├── security/
│   └── evaluation/
│
├── docs/
│   ├── prd/
│   ├── architecture/
│   ├── agent-spec/
│   ├── security/
│   ├── testing/
│   ├── api/
│   ├── operations/
│   ├── decisions/
│   └── skills/
│
├── scripts/
├── docker/
├── .env.example
├── pyproject.toml
├── README.md
└── docker-compose.yml
```

---

# 62. Architectural Dependency Rules

Dependencies should point inward toward stable domain concepts.

Preferred:

```text
API
 ↓
Application Services
 ↓
Domain / Agent Logic
 ↓
Provider Interfaces
 ↓
Provider Adapters
```

Avoid:

```text
API
 ↓
n8n-specific code
 ↓
AI model
 ↓
database
```

The API should not directly manipulate n8n.

---

# 63. Testing Architecture

Testing must exist at multiple levels.

## Unit Tests

Test individual functions.

## Integration Tests

Test interactions between components.

## Provider Tests

Test the n8n adapter against the actual n8n environment.

## Agent Tests

Test state transitions and agent behaviour.

## Security Tests

Test permissions, secrets, destructive operations, and prompt injection.

## End-to-End Tests

Test:

```text
Request
→ Specification
→ Build
→ Validate
→ Test
→ Diagnose
→ Repair
→ Retest
```

---

# 64. Runtime Verification Requirement

Provider integrations must be tested against a real supported runtime.

Mocks alone are insufficient for capability verification.

For example:

```text
Mock says:
"activate_workflow works"

Runtime verification:
"activate_workflow actually works"
```

The second is what determines the capability classification.

---

# 65. Architecture Decision Records

Important architectural decisions should be recorded in:

```text
/docs/decisions/
```

Examples:

```text
ADR-001 Use FastAPI
ADR-002 Use PostgreSQL
ADR-003 Provider Adapter Architecture
ADR-004 Do Not Depend on n8n OpenAPI Endpoint
ADR-005 Human Approval for High-Risk Changes
ADR-006 Separate AI Reasoning From Execution
```

This prevents future implementation drift.

---

# 66. Initial Deployment Architecture

For development:

```text
Windows Development Machine
        │
        ├── AAE
        │    └── FastAPI
        │
        ├── PostgreSQL
        │
        └── n8n
```

For future production:

```text
                    Internet
                       │
                       ▼
                Reverse Proxy
                       │
                       ▼
                  AAE API
                       │
              ┌────────┴────────┐
              ▼                 ▼
          PostgreSQL        Agent Workers
                                  │
                                  ▼
                            Provider Adapter
                                  │
                                  ▼
                                 n8n
```

The exact cloud infrastructure should be defined later.

---

# 67. Scaling Strategy

AAE should initially use a modular monolith.

Recommended evolution:

```text
Stage 1
Modular Monolith
      ↓
Stage 2
Background Workers
      ↓
Stage 3
Dedicated Agent Workers
      ↓
Stage 4
Selective Service Separation
```

Microservices should be introduced only when there is a demonstrated operational need.

---

# 68. Data Ownership

AAE database owns:

- agent state
- specifications
- approvals
- tests
- diagnoses
- repairs
- deployment records
- audit records
- capability registry

n8n owns:

- actual workflow runtime
- execution runtime
- provider-specific runtime state

AAE should reference provider resources rather than attempting to become their authoritative runtime database.

---

# 69. Source of Truth

For business requirements:

```text
Approved Specification
```

For provider capabilities:

```text
Capability Registry + Runtime Evidence
```

For actual workflow state:

```text
Provider Runtime
```

For AAE engineering history:

```text
AAE Database + Audit Log
```

For deployment approval:

```text
Approval Record
```

No single database should be treated as the source of truth for every concern.

---

# 70. Architecture Invariants

The following must remain true:

1. AAE Core must not depend directly on n8n-specific implementation.
2. AI models must not have unrestricted system access.
3. Provider operations must pass through controlled tools.
4. Material changes must be traceable.
5. Approved specifications govern implementation.
6. Production changes require appropriate authorisation.
7. Unknown capabilities must remain unknown until verified.
8. Secrets must remain outside normal model context.
9. Tests must be independently evaluable.
10. Provider errors must be normalised.
11. Audit records must remain trustworthy.
12. Workflow versions must remain traceable.
13. The architecture must support future providers.
14. The MVP must remain operationally simple.
15. Security policy must be enforceable independently of the LLM.

---

# 71. Final Architecture

The complete conceptual architecture is:

```text
                         USER
                           │
                           ▼
                    ┌──────────────┐
                    │   AAE API    │
                    └──────┬───────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │   AGENT ORCHESTRATOR    │
              └────────────┬────────────┘
                           │
       ┌───────────────────┼────────────────────┐
       │                   │                    │
       ▼                   ▼                    ▼
 Requirement           Planning             AI Model
 Engine                Engine               Gateway
       │                   │                    │
       └───────────────────┼────────────────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ Workflow Builder │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ Validation Engine│
                  └────────┬─────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │ Testing Engine│
                   └───────┬───────┘
                           │
                    ┌──────┴──────┐
                    │             │
                  PASS          FAIL
                    │             │
                    │             ▼
                    │       Diagnosis Engine
                    │             │
                    │             ▼
                    │        Repair Engine
                    │             │
                    │             ▼
                    │          Retest
                    │
                    ▼
              Approval Engine
                    │
                    ▼
             Deployment Engine
                    │
                    ▼
             Monitoring Engine


     ┌────────────────────────────────────────────┐
     │             CONTROL PLANE                  │
     │                                            │
     │ Capability Registry                        │
     │ Security Policy Engine                     │
     │ Audit Service                              │
     │ State Manager                              │
     │ Permission System                           │
     └────────────────────────────────────────────┘


     ┌────────────────────────────────────────────┐
     │              DATA PLANE                    │
     │                                            │
     │ PostgreSQL                                 │
     │ n8n Provider Adapter                        │
     │ n8n Runtime                                │
     └────────────────────────────────────────────┘
```

---

# 72. Final Architectural Principle

AAE should be understood as two cooperating systems:

```text
                 AAE
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
   REASONING PLANE     CONTROL PLANE
        │                   │
        │                   ├── Security
        │                   ├── Permissions
        │                   ├── Validation
        │                   ├── Approval
        │                   ├── Audit
        │                   └── Capability Truth
        │
        ├── Understand
        ├── Plan
        ├── Diagnose
        └── Propose
```

The reasoning plane can be probabilistic.

The control plane must be deterministic wherever practical.

This separation is fundamental to making AAE a reliable engineering system rather than an unrestricted AI agent.

---

# 73. Architecture Completion Criteria

This architecture is considered implementation-ready when:

- component responsibilities are defined
- agent boundaries are defined
- provider boundaries are defined
- AI boundaries are defined
- state management is defined
- database responsibilities are defined
- approval flow is defined
- deployment flow is defined
- failure and repair flows are defined
- capability verification is defined
- security boundaries are defined
- audit requirements are defined
- testing layers are defined
- n8n integration boundary is defined
- MVP scope is defined
- future scaling path is defined

Implementation must not materially change this architecture without recording an architectural decision.

---

# 74. Next Architectural Documents

After this document, the remaining sequence is:

```text
07 AAE_SECURITY_POLICY.md
        ↓
08 AAE_AGENT_SKILLS
        ↓
09 AAE_EVALUATION_BENCHMARK.md
        ↓
10 CODEX_IMPLEMENTATION_PLAN.md
        ↓
11 CODEX IMPLEMENTATION
```

The next document, **AAE_SECURITY_POLICY.md**, will define the actual security rules that the architecture must enforce: authentication, authorisation, secrets, prompt injection, production protection, destructive actions, approval gates, audit integrity, isolation, data handling, and fail-closed behaviour.