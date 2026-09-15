# n8n Control Surface

**Project:** AI Automation Engineer (AAE)  
**Provider:** n8n  
**Tested Version:** 2.38.7  
**Environment:** Self-hosted n8n, Windows, local development  
**Instance:** `http://localhost:5678`  
**Document Status:** Architecture Baseline  
**Version:** 1.0  
**Date:** 13 September 2026

---

# 1. Purpose

This document defines the control surface through which the AI Automation Engineer (AAE) may inspect, construct, test, diagnose, modify, activate, deactivate, and otherwise interact with an n8n instance.

The document is intentionally separate from `N8N_CAPABILITY_MAP.md`.

The capability map answers:

> What capabilities exist?

The control surface answers:

> Through what mechanisms can AAE safely exercise those capabilities?

AAE must not expose raw n8n endpoints directly to the reasoning model.

Instead, AAE must provide a controlled provider adapter that translates provider-neutral engineering operations into verified n8n mechanisms.

---

# 2. Core Principle

AAE is not an n8n REST API wrapper.

The correct architecture is:

```text
User
  ↓
AAE Agent
  ↓
AAE Tool Interface
  ↓
Automation Provider Interface
  ↓
n8n Adapter
  ↓
Verified n8n Control Surface
  ↓
n8n Instance
```

The n8n adapter is responsible for determining how an operation is actually performed.

The agent should reason in terms of:

```text
get_workflow()
execute_workflow()
validate_workflow()
diagnose_execution()
update_workflow()
```

rather than:

```text
POST /api/v1/...
GET /api/v1/...
```

This abstraction prevents provider-specific implementation details from becoming embedded in the agent's reasoning.

---

# 3. Control Surface Layers

The n8n control surface is divided into the following layers:

```text
┌────────────────────────────────────────────┐
│              AAE Agent Layer               │
├────────────────────────────────────────────┤
│          AAE Tool Contract Layer           │
├────────────────────────────────────────────┤
│       Automation Provider Interface        │
├────────────────────────────────────────────┤
│             n8n Adapter                    │
├────────────────────────────────────────────┤
│ ┌────────────┐ ┌──────────┐ ┌────────────┐ │
│ │ REST API   │ │ Webhooks │ │ CLI/Other  │ │
│ └────────────┘ └──────────┘ └────────────┘ │
├────────────────────────────────────────────┤
│              n8n Instance                  │
└────────────────────────────────────────────┘
```

Each layer has a separate responsibility.

---

# 4. Control Mechanism Classification

Every mechanism used by AAE must be classified as one of:

| Type | Meaning |
|---|---|
| `NATIVE_RUNTIME_VERIFIED` | Directly tested against the current n8n instance |
| `NATIVE_DOCUMENTED` | Documented by n8n but not runtime-tested |
| `INDIRECT_VERIFIED` | Achieves the desired operation through another verified mechanism |
| `VERSION_DEPENDENT` | Behaviour may change between versions |
| `PLAN_DEPENDENT` | Depends on n8n plan/edition |
| `PERMISSION_DEPENDENT` | Requires specific permissions |
| `ENVIRONMENT_DEPENDENT` | Depends on deployment configuration |
| `UNKNOWN` | Mechanism has not been sufficiently verified |
| `UNSUPPORTED` | Mechanism has been tested and found unavailable |

AAE must preserve this classification in its internal capability registry.

---

# 5. Authentication Control Surface

The current n8n API accepts an API key through:

```text
X-N8N-API-KEY
```

Example implementation:

```powershell
$headers = @{
    "X-N8N-API-KEY" = $N8N_API_KEY
}
```

AAE must not place the API key into:

- prompts;
- workflow descriptions;
- LLM context;
- source code;
- Git repositories;
- audit logs;
- error messages;
- generated documentation;
- execution diagnostic objects.

The adapter must manage credentials outside the reasoning context.

### Control classification

`NATIVE_RUNTIME_VERIFIED`

---

# 6. Workflow Inspection Surface

## 6.1 List Workflows

Provider operation:

```text
list_workflows()
```

Current n8n implementation:

```text
GET /api/v1/workflows
```

Status:

`NATIVE_RUNTIME_VERIFIED`

Purpose:

- discover available workflows;
- identify active workflows;
- inventory workflows;
- locate candidate workflows for modification;
- monitor workflow state.

The agent should receive a sanitised workflow summary rather than unnecessary raw metadata.

---

# 7. Get Workflow

Provider operation:

```text
get_workflow(workflow_id)
```

Current implementation:

```text
GET /api/v1/workflows/{workflow_id}
```

Status:

`NATIVE_RUNTIME_VERIFIED`

The adapter may retrieve:

- workflow metadata;
- nodes;
- connections;
- settings;
- version information.

Before passing workflow data to the LLM, the adapter should remove unnecessary secrets and sensitive configuration.

---

# 8. Workflow Creation Surface

Provider operation:

```text
create_workflow(workflow_definition)
```

Current implementation uses the n8n workflow API.

Status:

`NATIVE_RUNTIME_VERIFIED`

AAE creation process:

```text
Requirement
    ↓
Approved specification
    ↓
Workflow plan
    ↓
Workflow JSON
    ↓
Structural validation
    ↓
Create inactive workflow
    ↓
Inspect created workflow
    ↓
Test
```

AAE should prefer creating workflows in an inactive/development state.

Creation alone must never be interpreted as production deployment.

---

# 9. Workflow Modification Surface

Provider operation:

```text
update_workflow(workflow_id, workflow_definition)
```

Current implementation:

```text
PUT /api/v1/workflows/{workflow_id}
```

Status:

`NATIVE_RUNTIME_VERIFIED`

AAE must treat modification as a controlled engineering change.

Required process:

```text
Existing workflow
       ↓
Snapshot/current state
       ↓
Proposed modification
       ↓
Validation
       ↓
Create/update version
       ↓
Test
       ↓
Approval
       ↓
Activation if approved
```

AAE should never overwrite a production workflow simply because an LLM generated a new version.

---

# 10. Workflow Activation Surface

Provider operation:

```text
activate_workflow(workflow_id)
```

Current mechanism:

```text
POST /api/v1/workflows/{workflow_id}/activate
```

Status:

`NATIVE_RUNTIME_VERIFIED`

Activation is classified as:

```text
RISK LEVEL: HIGH
```

because activation may cause real-world side effects.

Production activation requires explicit approval unless a future policy explicitly grants autonomous authority.

---

# 11. Workflow Deactivation Surface

Provider operation:

```text
deactivate_workflow(workflow_id)
```

Current mechanism:

```text
POST /api/v1/workflows/{workflow_id}/deactivate
```

Status:

`NATIVE_RUNTIME_VERIFIED`

Deactivation should be considered a controlled operational action.

AAE may use it during:

- approved repair;
- maintenance;
- rollback;
- controlled testing.

Production deactivation should be logged and auditable.

---

# 12. Workflow Execution Surface

## 12.1 Direct API Execution

The following mechanism was tested:

```text
POST /api/v1/workflows/{workflow_id}/run
```

The instance returned:

```text
POST method not allowed
```

Therefore this mechanism must not be used.

Status:

`UNSUPPORTED`

for the tested mechanism.

---

# 13. Webhook Execution Surface

AAE successfully executed a workflow through an n8n webhook.

Provider abstraction:

```text
execute_workflow()
```

Current verified mechanism:

```text
POST /webhook/{webhook_path}
```

Status:

`INDIRECT_VERIFIED`

Example:

```text
AAE
 ↓
HTTP POST
 ↓
n8n Webhook
 ↓
Workflow execution
 ↓
Execution record
 ↓
AAE inspection
```

This is currently the primary verified mechanism for programmatically triggering webhook-based workflows.

---

# 14. Execution Abstraction

The agent must not care whether execution occurs through:

- webhook;
- native API;
- CLI;
- another verified mechanism.

Instead:

```text
execute_workflow(workflow_id, input, execution_policy)
```

The adapter determines the mechanism.

Example conceptual logic:

```text
execute_workflow()
        │
        ├── native execution available?
        │        ↓
        │       use it
        │
        ├── webhook trigger available?
        │        ↓
        │       use webhook
        │
        └── no safe mechanism
                 ↓
               BLOCK
```

The agent must never invent an execution route.

---

# 15. Execution History Surface

Provider operation:

```text
list_executions()
```

Current implementation:

```text
GET /api/v1/executions
```

Status:

`NATIVE_RUNTIME_VERIFIED`

AAE can use this for:

- monitoring;
- test discovery;
- failure detection;
- operational analysis.

---

# 16. Execution Inspection Surface

Provider operation:

```text
get_execution(execution_id)
```

Current implementation:

```text
GET /api/v1/executions/{execution_id}
```

Status:

`NATIVE_RUNTIME_VERIFIED`

Detailed execution information may contain:

- execution status;
- timing;
- node results;
- workflow data;
- errors;
- execution path;
- outputs.

---

# 17. Execution Data Sanitisation

Raw execution data must pass through a sanitisation layer.

```text
n8n
 ↓
Execution Adapter
 ↓
Secret Detection
 ↓
PII Filtering
 ↓
Sensitive Header Removal
 ↓
Credential Filtering
 ↓
Stack Trace Sanitisation
 ↓
Safe Diagnostic Object
 ↓
Agent
```

The LLM should receive only information required to perform the requested engineering task.

Example:

Instead of:

```text
Authorization: Bearer eyJ...
```

the agent should receive:

```text
Authorization: [REDACTED]
```

---

# 18. Failure Diagnosis Surface

Provider operation:

```text
diagnose_execution(execution_id)
```

This is an AAE capability rather than a raw n8n endpoint.

The adapter retrieves execution information.

AAE then determines:

- whether execution failed;
- which node failed;
- why it failed;
- previous successful node;
- execution path;
- relevant node configuration;
- likely root cause;
- confidence level.

Architecture:

```text
n8n execution
      ↓
get_execution()
      ↓
sanitisation
      ↓
diagnostic engine
      ↓
structured diagnosis
```

---

# 19. Workflow Validation Surface

Provider operation:

```text
validate_workflow(workflow)
```

No authoritative n8n `/validate` mechanism has yet been verified.

Therefore AAE must provide its own validation layer.

Validation should include:

### Structural

- valid node definitions;
- valid connections;
- valid workflow structure;
- missing nodes;
- orphan nodes.

### Configuration

- required parameters;
- invalid configuration;
- missing credentials;
- incompatible node settings.

### Logic

- unreachable nodes;
- impossible branches;
- invalid dependencies;
- missing outputs;
- incorrect data flow.

### Security

- dangerous nodes;
- exposed secrets;
- unprotected webhooks;
- unsafe filesystem access;
- suspicious expressions.

### Runtime

- test execution;
- expected output;
- failure behaviour.

### Semantic

- business requirement satisfied.

---

# 20. Validation Architecture

```text
Workflow
   ↓
Structural Validator
   ↓
Configuration Validator
   ↓
Connection Validator
   ↓
Security Validator
   ↓
Business Logic Validator
   ↓
Runtime Test
   ↓
Semantic Test
   ↓
VALID / INVALID / BLOCKED
```

AAE must not consider a workflow valid merely because n8n accepts it.

---

# 21. Technical vs Semantic Validation

AAE must distinguish:

```text
Technical Success
```

from:

```text
Business Success
```

Example:

```text
Workflow executes
        ↓
n8n status = SUCCESS
        ↓
Expected customer record missing
        ↓
Semantic test = FAILED
```

Therefore:

```text
workflow_valid =
    structural_valid
    AND configuration_valid
    AND security_valid
    AND runtime_success
    AND semantic_success
```

---

# 22. Retry Surface

Provider operation:

```text
retry_execution(execution_id)
```

A native retry API has not yet been conclusively verified.

Status:

`UNKNOWN`

The AAE provider interface should nevertheless define the abstraction.

Possible future implementations:

```text
Native n8n retry
        OR
Controlled re-execution
        OR
Webhook re-trigger
        OR
Other verified mechanism
```

The adapter must report which mechanism was actually used.

AAE must never claim:

> "Native n8n retry was used"

unless it was verified.

---

# 23. Repair Surface

Provider-neutral operation:

```text
repair_workflow(workflow_id, repair_plan)
```

Repair is an AAE engineering operation.

It may involve:

```text
Execution failure
      ↓
Diagnosis
      ↓
Repair proposal
      ↓
Risk assessment
      ↓
Human approval if required
      ↓
Workflow modification
      ↓
Validation
      ↓
Test
```

The repair system must not blindly modify production workflows.

---

# 24. Repair Risk Classification

AAE should classify repairs.

### LOW RISK

Examples:

- fixing obvious code syntax;
- correcting a missing field;
- correcting an expression;
- fixing a broken connection.

### MEDIUM RISK

Examples:

- changing business logic;
- changing API parameters;
- changing database operations.

### HIGH RISK

Examples:

- modifying financial operations;
- deleting data;
- changing authentication;
- changing production triggers;
- changing customer communication behaviour.

### CRITICAL

Examples:

- destructive database actions;
- credential changes;
- production deletion;
- actions affecting large numbers of customers.

High-risk and critical repairs require explicit approval.

---

# 25. Delete Surface

Provider operation:

```text
delete_workflow(workflow_id)
```

Native deletion has not yet been conclusively verified.

Status:

`UNKNOWN`

AAE must treat deletion as:

```text
DESTRUCTIVE
APPROVAL REQUIRED
AUDIT REQUIRED
```

AAE must never infer deletion support from an HTTP `OPTIONS` response.

No production workflow should be deleted automatically during MVP.

---

# 26. Security Audit Surface

Provider operation:

```text
run_security_audit()
```

n8n documents security-audit mechanisms including the audit CLI/API.

Status:

`DOCUMENTED / RUNTIME_VERIFIED WHERE TESTED`

AAE should expose security auditing as a provider-level operation rather than embedding one n8n command into the agent.

Expected workflow:

```text
Request security audit
       ↓
n8n audit mechanism
       ↓
Results
       ↓
AAE normalisation
       ↓
Risk classification
       ↓
Recommendations
```

---

# 27. Node Metadata Surface

AAE requires a reliable mechanism to discover node capabilities.

Provider operation:

```text
get_node_information(node_type)
```

Potential sources:

```text
n8n runtime metadata
n8n installed node definitions
official documentation
verified runtime inspection
```

Current status:

`PARTIALLY VERIFIED`

Further runtime discovery is required.

Node metadata should eventually expose:

```text
Node type
Node version
Display name
Properties
Required fields
Operations
Credentials
Inputs
Outputs
Supported configuration
```

This capability is critical to the workflow builder.

---

# 28. Instance Information Surface

Provider operation:

```text
get_instance_information()
```

AAE should determine:

- n8n version;
- deployment type;
- environment;
- available features;
- permissions;
- relevant configuration;
- installed nodes;
- task-runner capabilities.

The capability should be used during startup and capability discovery.

Status:

`PARTIALLY VERIFIED`

---

# 29. OpenAPI Surface

AAE must not depend on:

```text
/openapi.json
```

The current instance returns the n8n Editor HTML application rather than an OpenAPI document.

Status:

`NOT AVAILABLE AS VERIFIED OPENAPI SPECIFICATION`

This does not prevent AAE from using the n8n API.

AAE instead uses:

```text
Capability Registry
        +
Runtime Verification
        +
Provider Adapter
        +
Verified Control Mechanisms
```

---

# 30. CLI Surface

The n8n CLI is a potential control mechanism for administrative and operational functions.

However, AAE must distinguish:

```text
CLI documented
```

from:

```text
CLI verified in current environment
```

CLI commands should not be used autonomously until:

1. the command is documented;
2. the command is tested safely;
3. its permissions are understood;
4. its side effects are documented;
5. its rollback characteristics are known.

Status:

`DOCUMENTED / REQUIRES TARGETED RUNTIME VERIFICATION`

---

# 31. Environment Separation

AAE should support distinct environments:

```text
DEVELOPMENT
     ↓
TEST
     ↓
STAGING
     ↓
PRODUCTION
```

MVP development should use the local n8n instance.

Production operations must never be inferred from development capability tests.

A capability verified on:

```text
localhost:5678
```

must not automatically be considered verified on:

```text
production.n8n.example
```

---

# 32. Production Protection

AAE should implement production safeguards.

At minimum:

```text
Production workflow detected
        ↓
Risk assessment
        ↓
Change preview
        ↓
Validation
        ↓
Test
        ↓
Human approval
        ↓
Deployment
        ↓
Post-deployment verification
```

The agent must fail closed when it cannot establish the environment or authorization level.

---

# 33. Approval Surface

AAE must distinguish operations that can be autonomous from operations requiring approval.

### Read-only

Generally autonomous:

```text
list_workflows
get_workflow
list_executions
get_execution
get_node_information
get_instance_information
```

### Low-risk engineering

Potentially autonomous in development:

```text
create_test_workflow
validate_workflow
run_test
diagnose_execution
```

### Controlled mutation

Approval depending on environment:

```text
update_workflow
repair_workflow
activate_workflow
deactivate_workflow
```

### Destructive / high-risk

Explicit approval required:

```text
delete_workflow
credential changes
destructive data operations
production changes
```

---

# 34. Audit Surface

Every significant AAE action must generate an audit event.

Minimum fields:

```text
timestamp
actor
request_id
workflow_id
execution_id
operation
environment
provider
mechanism
risk_level
approval_status
before_state
after_state
result
error
```

Example:

```json id="j2c1op"
{
  "operation": "update_workflow",
  "workflow_id": "qz5nU4uONpnI7Lbg",
  "environment": "development",
  "mechanism": "n8n_rest_api",
  "approval": "approved",
  "result": "success"
}
```

Secrets must never be included in audit records.

---

# 35. Failure Handling

When the control surface cannot safely perform an operation:

```text
Attempt
  ↓
Detect failure
  ↓
Classify failure
  ↓
Do not guess
  ↓
Try approved alternative if available
  ↓
Otherwise BLOCK
  ↓
Explain limitation
```

AAE must never fabricate a successful operation.

---

# 36. Capability Registry

AAE should maintain a machine-readable registry derived from this document.

Example:

```json id="b8n8y8"
{
  "provider": "n8n",
  "version": "2.38.7",
  "capabilities": {
    "list_workflows": {
      "status": "RUNTIME_VERIFIED",
      "mechanism": "rest_api"
    },
    "get_workflow": {
      "status": "RUNTIME_VERIFIED",
      "mechanism": "rest_api"
    },
    "execute_workflow": {
      "status": "INDIRECT_VERIFIED",
      "mechanism": "webhook"
    },
    "validate_workflow": {
      "status": "UNKNOWN",
      "mechanism": null
    },
    "retry_execution": {
      "status": "UNKNOWN",
      "mechanism": null
    },
    "delete_workflow": {
      "status": "UNKNOWN",
      "mechanism": null
    }
  }
}
```

The registry becomes the runtime truth source for the n8n adapter.

---

# 37. Provider Interface

The AAE provider abstraction should expose:

```python
class AutomationProvider:

    def get_instance_information(self):
        ...

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

    def list_executions(self, filters=None):
        ...

    def get_execution(self, execution_id, include_data=False):
        ...

    def retry_execution(self, execution_id):
        ...

    def get_node_information(self, node_type):
        ...

    def validate_workflow(self, workflow):
        ...

    def run_security_audit(self):
        ...
```

The n8n adapter implements these operations according to the verified control surface.

---

# 38. n8n Adapter

The adapter should have responsibility for:

```text
Authentication
Endpoint selection
Webhook execution
API communication
Response normalisation
Error normalisation
Capability checks
Version checks
Security filtering
Rate limiting
Retry policy
Audit events
```

The agent should not directly construct arbitrary HTTP requests to n8n.

---

# 39. Normalised Responses

The n8n adapter should convert provider-specific responses into AAE-standard structures.

For example:

```json id="xg4knq"
{
  "success": true,
  "provider": "n8n",
  "operation": "get_workflow",
  "data": {
    "workflow_id": "...",
    "name": "...",
    "active": false
  },
  "mechanism": "rest_api",
  "capability_status": "RUNTIME_VERIFIED"
}
```

This prevents n8n-specific response formats from leaking into the agent architecture.

---

# 40. Error Normalisation

n8n-specific errors should be converted into standard AAE errors.

Example:

```text
N8N_AUTHENTICATION_ERROR
N8N_PERMISSION_ERROR
N8N_NOT_FOUND
N8N_VALIDATION_ERROR
N8N_EXECUTION_ERROR
N8N_RATE_LIMIT
N8N_UNSUPPORTED_OPERATION
N8N_VERSION_MISMATCH
N8N_ENVIRONMENT_ERROR
N8N_UNKNOWN_ERROR
```

The agent can then reason about errors consistently.

---

# 41. Rate Limiting and Safety

The adapter should eventually implement:

- request throttling;
- retry limits;
- exponential backoff where appropriate;
- concurrency controls;
- operation timeouts;
- circuit breaking;
- destructive-operation protection.

The agent must not continuously retry a failing operation.

---

# 42. Control Surface Decision Matrix

| Operation | Mechanism | Status | Risk |
|---|---|---|---|
| List workflows | REST API | Verified | Low |
| Get workflow | REST API | Verified | Low |
| Create workflow | REST API | Verified | Medium |
| Update workflow | REST API | Verified | Medium |
| Activate | REST API | Verified | High |
| Deactivate | REST API | Verified | High |
| Execute webhook workflow | Webhook | Verified | Medium |
| Direct `/run` | REST API | Unsupported | N/A |
| List executions | REST API | Verified | Low |
| Get execution | REST API | Verified | Low |
| Diagnose | AAE engine | Verified architecture | Medium |
| Repair | AAE + REST API | Verified experimentally | High |
| Validate | AAE engine | Required | Medium |
| Retry | TBD | Unknown | Medium |
| Delete | TBD | Unknown | Critical |
| Security audit | CLI/API | Documented/verified | Medium |
| Node metadata | Runtime/docs | Partial | Low |
| OpenAPI | `/openapi.json` | Not available as verified spec | N/A |
| CLI | n8n CLI | Requires verification | Variable |

---

# 43. Control Surface Rules

AAE must follow these rules.

### Rule 1 — Never invent an endpoint

If a mechanism is not verified or documented, the agent must not assume it exists.

### Rule 2 — Never confuse HTTP success with operation success

HTTP 200 does not prove that the response contains the expected resource.

Example:

```text
/openapi.json
HTTP 200
↓
HTML
↓
Not OpenAPI
```

### Rule 3 — Never confuse technical success with business success

A successful n8n execution does not necessarily mean the automation achieved its intended result.

### Rule 4 — Never expose raw secrets to the model

Sensitive data must be redacted before entering reasoning context.

### Rule 5 — Never perform destructive operations without authorization

Deletion and high-impact production changes require approval.

### Rule 6 — Prefer verified indirect mechanisms over unverified direct mechanisms

Example:

```text
Unknown direct execution API
        ↓
Verified webhook execution
        ↓
Use webhook mechanism
```

### Rule 7 — Report mechanism truthfully

AAE must be able to say:

> "Workflow executed through webhook."

rather than:

> "Workflow executed through n8n's run API."

when the latter was not used.

### Rule 8 — Fail closed

When AAE cannot safely establish capability, authorization, or environment:

```text
BLOCK
```

rather than guess.

---

# 44. Relationship to AAE Agent Tools

The agent should receive provider-neutral tools:

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

Later:

```text
retry_execution
activate_workflow
deactivate_workflow
security_audit
delete_workflow
```

These tools are not raw REST wrappers.

Each tool calls the provider interface, which calls the n8n adapter.

---

# 45. End-to-End Engineering Flow

The intended AAE control flow is:

```text
User Requirement
       ↓
Requirement Translation
       ↓
Approved Specification
       ↓
Workflow Planning
       ↓
Capability Check
       ↓
Workflow Construction
       ↓
Structural Validation
       ↓
Create/Update
       ↓
Runtime Test
       ↓
Execution Inspection
       ↓
Semantic Validation
       ↓
    ┌──────────────┐
    │ Test Failed? │
    └──────┬───────┘
           │
      Yes  ↓
       Diagnosis
           ↓
        Repair
           ↓
       Re-validation
           ↓
        Re-test
           │
           └───────────────┐
                           ↓
                      Test Passed
                           ↓
                    Approval Gate
                           ↓
                      Deployment
                           ↓
                       Monitoring
```

---

# 46. Current Control Surface Status

The n8n control surface is sufficiently verified to begin defining the AAE agent behaviour.

The following core operations have been proven against the actual environment:

```text
INSPECT
CREATE
UPDATE
ACTIVATE
DEACTIVATE
EXECUTE
INSPECT EXECUTION
DETECT FAILURE
DIAGNOSE
REPAIR
RE-TEST
VERIFY
```

Remaining capability discovery should be targeted rather than open-ended.

---

# 47. Remaining Research Before Agent Specification

Before `AAE_REQUIREMENT_TRANSLATION_SPEC.md` and `AAE_AGENT_SPECIFICATION.md`, the following should receive targeted investigation:

1. authoritative n8n node metadata;
2. exact validation mechanisms;
3. retry mechanisms;
4. CLI capabilities;
5. instance/environment metadata;
6. permission boundaries;
7. production/environment separation;
8. safe rollback/version strategy.

These investigations should not block the creation of the AAE requirement and agent specifications unless they reveal a fundamental architectural limitation.

---

# 48. Final Architectural Position

AAE will not depend on an n8n OpenAPI specification.

AAE will use:

```text
                    AAE
                     │
                     ▼
          Provider-Neutral Tools
                     │
                     ▼
       Automation Provider Interface
                     │
                     ▼
                n8n Adapter
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
    REST API      Webhooks        CLI
       │             │             │
       └─────────────┼─────────────┘
                     ▼
                n8n Runtime
```

The adapter selects only mechanisms whose capability status is sufficiently established.

This makes AAE:

- safer;
- version-aware;
- provider-independent;
- testable;
- auditable;
- extensible;
- less dependent on undocumented n8n internals.

---

# 49. Next Document

The next document is:

```text
AAE_REQUIREMENT_TRANSLATION_SPEC.md
```

Its purpose is to define how AAE converts natural-language business requests into an authoritative, structured automation specification before workflow construction begins.

No Codex implementation should begin until the requirement translation, agent specification, architecture, security, and evaluation documents are sufficiently defined.