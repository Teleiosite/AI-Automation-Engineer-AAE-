# n8n Capability Map

**Project:** AI Automation Engineer (AAE)  
**Provider:** n8n  
**Tested Version:** 2.38.7  
**Environment:** Self-hosted, Windows, local development instance  
**Instance:** `http://localhost:5678`  
**Document Status:** Architecture Baseline  
**Verification Date:** 13 September 2026  
**Authority:** Runtime verification against the actual n8n instance, supplemented by official n8n documentation

---

## 1. Purpose

This document defines the verified capability surface of the n8n instance used by the AI Automation Engineer (AAE).

The purpose is not merely to document what n8n is theoretically capable of doing.

The purpose is to establish:

1. what n8n documents as supported;
2. what the current n8n version exposes;
3. what has been successfully verified against the actual runtime;
4. what is version-, plan-, permission-, or environment-dependent;
5. what AAE can achieve through alternative or indirect mechanisms;
6. what capabilities must remain unknown until further evidence is obtained.

AAE must not treat model knowledge, third-party examples, or undocumented assumptions as equivalent to runtime verification.

---

# 2. Capability Classification

AAE uses the following classification model.

| Classification | Meaning |
|---|---|
| `RUNTIME_VERIFIED` | Successfully tested against the actual n8n 2.38.7 instance |
| `DOCUMENTED` | Supported by authoritative n8n documentation but not yet runtime-tested |
| `VERSION_DEPENDENT` | Capability or behaviour may differ between n8n versions |
| `PLAN_DEPENDENT` | Capability depends on n8n Cloud/self-hosted edition/plan |
| `PERMISSION_DEPENDENT` | Capability requires specific n8n permissions or privileges |
| `ENVIRONMENT_DEPENDENT` | Behaviour depends on deployment/environment configuration |
| `INDIRECTLY_SUPPORTED` | Capability can be achieved through another verified mechanism |
| `KNOWN_LIMITATION` | Known restriction has been identified |
| `UNKNOWN` | Insufficient evidence to classify capability |
| `UNSUPPORTED` | Tested or documented evidence indicates the mechanism is not supported |

AAE must distinguish between:

> **Native n8n capability**

and

> **AAE-achievable capability**

These are not necessarily the same.

---

# 3. Environment

## 3.1 Runtime

| Component | Value | Status |
|---|---|---|
| Operating System | Windows | RUNTIME_VERIFIED |
| Node.js | 24.21.0 | RUNTIME_VERIFIED |
| npm | 11.19.0 | RUNTIME_VERIFIED |
| n8n | 2.38.7 | RUNTIME_VERIFIED |
| n8n Port | 5678 | RUNTIME_VERIFIED |
| Task Broker | 127.0.0.1:5679 | RUNTIME_VERIFIED |
| JavaScript Task Runner | Working | RUNTIME_VERIFIED |
| Python Task Runner | Not currently working in internal configuration | KNOWN_LIMITATION |

---

# 4. Connectivity

## 4.1 n8n HTTP Connectivity

The n8n instance was successfully reached locally.

### Test

```powershell
Test-NetConnection localhost -Port 5678
```

### Result

```text
TcpTestSucceeded : True
```

### Classification

`RUNTIME_VERIFIED`

---

## 4.2 n8n Web Interface

The n8n web interface successfully returned HTTP 200.

### Test

```text
GET http://localhost:5678
```

### Result

```text
HTTP 200
```

### Classification

`RUNTIME_VERIFIED`

---

# 5. Authentication

AAE successfully communicated with the n8n REST API using the n8n API-key authentication mechanism.

Example:

```powershell
$N8N_API_KEY = Read-Host "Paste your n8n API key"
$headers = @{
    "X-N8N-API-KEY" = $N8N_API_KEY
}
```

The API key must never be exposed to the LLM, logs, source code, prompts, or user-visible diagnostic output.

### Classification

`RUNTIME_VERIFIED`

### Security requirement

AAE must store and transmit credentials through a protected secret mechanism.

AAE must never request that users paste production credentials into the conversational context.

---

# 6. Workflow Capabilities

## 6.1 List Workflows

Endpoint tested:

```text
GET /api/v1/workflows
```

Successfully returned workflow information.

### Classification

`RUNTIME_VERIFIED`

### AAE usage

AAE may use this capability for:

- workflow discovery;
- inventory;
- monitoring;
- workflow selection;
- audit;
- environment inspection.

---

# 7. Get Workflow

Endpoint tested:

```text
GET /api/v1/workflows/{workflowId}
```

Successfully returned:

- workflow ID;
- workflow name;
- nodes;
- connections;
- settings;
- workflow metadata;
- workflow version information.

### Classification

`RUNTIME_VERIFIED`

### AAE usage

This is a core read capability.

AAE can inspect an existing workflow before:

- explaining it;
- modifying it;
- testing it;
- diagnosing it;
- comparing versions;
- validating it.

---

# 8. Create Workflow

AAE successfully created a test workflow.

### Test workflow

```text
Manual Trigger
      ↓
Set Test Message
```

The workflow was created successfully and initially remained inactive.

### Classification

`RUNTIME_VERIFIED`

### Safety requirement

New workflows should initially be created in a non-production/inactive state whenever possible.

---

# 9. Update Workflow

AAE successfully modified an existing workflow and created a new workflow version.

The test sequence demonstrated:

```text
Version 1
   ↓
Deactivate
   ↓
Modify
   ↓
Create/update
   ↓
Version 2
   ↓
Activate
   ↓
Execute
```

### Classification

`RUNTIME_VERIFIED`

### Important architectural finding

AAE should treat workflow changes as versioned engineering changes rather than uncontrolled mutation.

---

# 10. Workflow Activation

Endpoint tested:

```text
POST /api/v1/workflows/{id}/activate
```

Successfully activated a workflow.

### Classification

`RUNTIME_VERIFIED`

### Safety

Production activation must be approval-gated.

---

# 11. Workflow Deactivation

Endpoint tested:

```text
POST /api/v1/workflows/{id}/deactivate
```

Successfully deactivated a workflow.

### Classification

`RUNTIME_VERIFIED`

---

# 12. Direct Workflow Execution

An attempted direct execution mechanism was tested:

```text
POST /api/v1/workflows/{id}/run
```

The n8n instance returned:

```text
POST method not allowed
```

### Classification

`NOT SUPPORTED` for this tested mechanism.

This does not mean that n8n workflows cannot be programmatically executed.

It means:

> The tested `/api/v1/workflows/{id}/run` mechanism cannot be treated as the execution mechanism for AAE.

---

# 13. Webhook-Based Execution

AAE successfully created a webhook-triggered workflow.

Example:

```text
HTTP POST
    ↓
n8n Webhook Trigger
    ↓
Workflow
```

The workflow was activated and successfully triggered through:

```text
POST /webhook/{path}
```

The execution was then available through the execution API.

### Classification

`RUNTIME_VERIFIED`

### Architectural significance

Webhook execution provides an important alternative execution mechanism.

AAE should therefore implement an abstraction:

```text
execute_workflow()
```

rather than hard-coding:

```text
POST /api/v1/workflows/{id}/run
```

The n8n adapter can select the verified execution mechanism appropriate to the workflow.

---

# 14. List Executions

Endpoint tested:

```text
GET /api/v1/executions
```

Successfully returned execution records.

### Classification

`RUNTIME_VERIFIED`

### AAE usage

AAE can use this for:

- monitoring;
- execution history;
- failure discovery;
- workflow health;
- test result discovery.

---

# 15. Get Execution

Endpoint tested:

```text
GET /api/v1/executions/{executionId}
```

Successfully returned detailed execution information.

With execution data enabled, AAE was able to inspect:

- execution status;
- timing;
- node execution information;
- workflow data;
- output;
- failed node;
- execution path;
- errors.

### Classification

`RUNTIME_VERIFIED`

---

# 16. Execution Data

Detailed execution data was successfully retrieved.

This demonstrated that AAE can inspect individual node results and execution paths.

Example diagnostic information obtained:

```text
Execution:
    ID
    status
    mode
    workflow ID
    workflow version

Failure:
    node
    node type
    node version
    error type
    error message
    line number
    execution time

Execution path:
    previous node
    failed node
```

### Classification

`RUNTIME_VERIFIED`

---

# 17. Execution Data Security

Execution data may contain sensitive information including:

- HTTP headers;
- webhook URLs;
- request bodies;
- business data;
- personal information;
- tokens;
- resume tokens;
- workflow configuration;
- local filesystem paths;
- credential-related information.

Therefore raw n8n execution data must never be passed directly to an LLM.

Required architecture:

```text
n8n execution
      ↓
AAE execution adapter
      ↓
redaction / sanitisation
      ↓
safe diagnostic object
      ↓
diagnosis engine / LLM
```

### Classification

`RUNTIME_VERIFIED` observation + `AAE_SECURITY_REQUIREMENT`

---

# 18. Technical vs Semantic Success

Testing revealed an important limitation of relying only on n8n's execution status.

A workflow can technically execute successfully while producing an incorrect or empty business result.

Example:

```text
Execution status:
SUCCESS
```

while the expected output was not correctly produced.

Therefore AAE must distinguish:

```text
TECHNICAL TEST
    ↓
Did n8n execute successfully?

SEMANTIC TEST
    ↓
Did the workflow produce the expected business result?
```

### Classification

`RUNTIME_VERIFIED` architectural finding

---

# 19. Failure Detection

AAE deliberately introduced a workflow failure:

```javascript
throw new Error('AAE deliberate test failure');
```

The resulting execution was successfully inspected.

AAE identified:

- failed execution;
- failed node;
- node type;
- node version;
- error message;
- stack trace;
- previous successful node;
- execution path;
- workflow version.

### Classification

`RUNTIME_VERIFIED`

---

# 20. Automated Diagnosis

AAE successfully transformed the failed execution into a structured diagnostic object.

Example:

```json
{
  "execution": {
    "id": "5",
    "status": "error",
    "mode": "webhook",
    "workflow_id": "qz5nU4uONpnI7Lbg",
    "workflow_version_id": "633c0680-249e-4128-a37c-c19f2ac34b4f"
  },
  "failure": {
    "node": "AAE Deliberate Failure",
    "node_type": "n8n-nodes-base.code",
    "node_version": 2,
    "execution_status": "error",
    "error_type": "Error",
    "message": "AAE deliberate test failure [line 1]"
  }
}
```

### Classification

`RUNTIME_VERIFIED`

---

# 21. Automated Repair

AAE successfully repaired the deliberately failing workflow.

The failing code:

```javascript
throw new Error('AAE deliberate test failure');
```

was replaced with:

```javascript
return [{
    json: {
        message: 'AAE repair successful',
        repaired: true
    }
}];
```

A new workflow version was created.

### Classification

`RUNTIME_VERIFIED`

---

# 22. Re-test After Repair

The repaired workflow was triggered again.

Execution succeeded.

The resulting output was:

```json
{
  "message": "AAE repair successful",
  "repaired": true
}
```

### Classification

`RUNTIME_VERIFIED`

---

# 23. Complete Repair Lifecycle

The following AAE engineering loop has therefore been experimentally demonstrated:

```text
Detect
   ↓
Inspect
   ↓
Diagnose
   ↓
Repair
   ↓
Create new version
   ↓
Activate
   ↓
Execute
   ↓
Inspect result
   ↓
Confirm success
```

### Classification

`RUNTIME_VERIFIED`

This is one of the most important findings in the capability discovery phase.

---

# 24. Security Audit

n8n provides a security audit capability.

The documented mechanisms include:

```text
n8n audit CLI
POST /audit
n8n security audit functionality
```

The audit can identify security-related issues including:

- credential risks;
- risky nodes;
- filesystem-related risks;
- unprotected webhooks;
- community/custom-node risks;
- missing security settings;
- outdated instances.

The actual availability of particular mechanisms can depend on authentication, deployment, version, and environment.

### Classification

`DOCUMENTED` / `RUNTIME_VERIFIED` where directly tested

---

# 25. OpenAPI

## 25.1 `/openapi.json` investigation

The endpoint was explicitly tested:

```text
GET http://localhost:5678/openapi.json
```

Result:

```text
HTTP Status: 200
Content-Type: text/html; charset=utf-8
Content-Length: 51723
```

The response began with:

```html
<!DOCTYPE html>
<html lang="en">
```

and contained the n8n Editor application.

The response could not be parsed as JSON.

### Classification

`NOT VERIFIED`

More specifically:

> `/openapi.json` is NOT an OpenAPI specification endpoint in the tested n8n 2.38.7 instance.

The HTTP 200 response must not be interpreted as proof that OpenAPI is available.

### Important correction

Any previous documentation stating:

```text
OpenAPI: VERIFIED
```

must be removed or corrected.

---

# 26. OpenAPI Dependency

AAE must not make an OpenAPI document a hard dependency for n8n integration.

The absence of a usable OpenAPI specification does not prevent AAE from controlling n8n.

AAE should instead use a provider adapter and capability registry.

Recommended architecture:

```text
AAE Core
    ↓
Automation Provider Interface
    ↓
n8n Adapter
    ↓
┌──────────────────────────────┐
│ Verified n8n control surface │
├──────────────────────────────┤
│ REST API                     │
│ Webhooks                     │
│ CLI                          │
│ Node metadata                │
│ Other verified mechanisms    │
└──────────────────────────────┘
```

OpenAPI may be used in the future if a reliable authoritative specification becomes available, but AAE must not depend on it.

---

# 27. Workflow Validation Endpoint

A dedicated n8n `/validate` endpoint has not yet been conclusively verified.

### Classification

`UNKNOWN`

AAE must not assume that:

```text
POST /validate
```

exists or is usable.

### AAE workaround

AAE should implement its own validation layer.

At minimum:

```text
Structural validation
        ↓
Node/configuration validation
        ↓
Connection validation
        ↓
Business-logic validation
        ↓
Runtime testing
        ↓
Semantic validation
```

This may ultimately provide stronger validation than relying on a single generic provider endpoint.

---

# 28. Retry Execution

A native retry API mechanism has not yet been conclusively verified through the current runtime tests.

### Classification

`UNKNOWN`

### AAE design

AAE should expose a provider-level abstraction:

```text
retry_execution()
```

The n8n adapter can later select:

1. native n8n retry if verified;
2. approved workflow re-execution;
3. controlled re-trigger;
4. another verified mechanism.

AAE must not label a workaround as a native n8n retry API.

---

# 29. Delete Workflow

A native workflow deletion capability has not been conclusively verified through a safe runtime test.

An HTTP `OPTIONS` response must not be interpreted as proof that deletion is supported.

### Classification

`UNKNOWN`

### Safety

Deletion is a destructive operation.

AAE must require explicit human approval before deleting workflows.

No production workflow should be deleted merely because the model believes deletion is supported.

---

# 30. Node Metadata

AAE requires authoritative information about n8n nodes in order to reliably construct workflows.

Required information includes:

- node type;
- node version;
- available properties;
- operations;
- required fields;
- credential requirements;
- supported configuration;
- input/output expectations.

Potential sources include:

```text
n8n runtime metadata
n8n installed node definitions
n8n documentation
verified runtime inspection
```

### Current classification

`PARTIALLY VERIFIED / REQUIRES FURTHER DISCOVERY`

This capability is important enough to be included in the next control-surface investigation.

---

# 31. Python Execution

The n8n environment successfully registered the JavaScript task runner.

The internal Python task runner configuration was not working because the required Python virtual environment was unavailable.

### Classification

`KNOWN_LIMITATION`

This does not establish that n8n cannot execute Python generally.

It establishes only that Python execution is not currently verified in this particular configuration.

AAE must therefore not assume Python execution is available in the current environment.

---

# 32. AI Assistant

n8n's AI Assistant is available as a preview capability in the relevant n8n version/environment.

It may require:

- supported n8n version;
- model provider;
- model/API key;
- appropriate environment configuration;
- additional feature support.

The AAE project does not depend on n8n's AI Assistant.

### Classification

`DOCUMENTED / ENVIRONMENT_DEPENDENT / PREVIEW`

---

# 33. Version and Environment Sensitivity

n8n capabilities can differ based on:

- n8n version;
- self-hosted vs Cloud;
- edition;
- plan;
- permissions;
- configuration;
- installed community nodes;
- deployment environment.

Therefore the following statement is invalid:

> "n8n supports X."

AAE should instead use:

> "Capability X is documented by n8n."

or:

> "Capability X was verified against n8n 2.38.7 in the AAE development environment."

This distinction is mandatory.

---

# 34. Capability Truthfulness Model

AAE must maintain two separate concepts.

## Native capability

What n8n itself exposes.

```text
N8N_NATIVE_CAPABILITY
```

## Achievable capability

What AAE can accomplish through verified mechanisms.

```text
AAE_ACHIEVABLE_CAPABILITY
```

Example:

```text
Direct workflow /run endpoint
        ↓
N8N_NATIVE_CAPABILITY = NOT_SUPPORTED

Webhook-triggered execution
        ↓
N8N_NATIVE_CAPABILITY = VERIFIED

AAE execute_workflow()
        ↓
AAE_ACHIEVABLE_CAPABILITY = VERIFIED
```

This prevents the AAE agent from confusing a workaround with native provider functionality.

---

# 35. Current Verified Capability Matrix

| Capability | Status |
|---|---|
| n8n connectivity | `RUNTIME_VERIFIED` |
| API-key authentication | `RUNTIME_VERIFIED` |
| List workflows | `RUNTIME_VERIFIED` |
| Get workflow | `RUNTIME_VERIFIED` |
| Create workflow | `RUNTIME_VERIFIED` |
| Update workflow | `RUNTIME_VERIFIED` |
| Workflow versioning | `RUNTIME_VERIFIED` |
| Activate workflow | `RUNTIME_VERIFIED` |
| Deactivate workflow | `RUNTIME_VERIFIED` |
| List executions | `RUNTIME_VERIFIED` |
| Get execution | `RUNTIME_VERIFIED` |
| Detailed execution data | `RUNTIME_VERIFIED` |
| Webhook execution | `RUNTIME_VERIFIED` |
| Failure detection | `RUNTIME_VERIFIED` |
| Failed-node identification | `RUNTIME_VERIFIED` |
| Structured diagnosis | `RUNTIME_VERIFIED` |
| Workflow repair | `RUNTIME_VERIFIED` |
| Re-test after repair | `RUNTIME_VERIFIED` |
| Semantic testing requirement | `RUNTIME_VERIFIED` finding |
| Security audit | `RUNTIME_VERIFIED` / `DOCUMENTED` |
| Direct `/workflows/{id}/run` | `UNSUPPORTED` for tested mechanism |
| `/openapi.json` OpenAPI specification | `NOT VERIFIED` |
| `/validate` endpoint | `UNKNOWN` |
| Native retry API | `UNKNOWN` |
| Delete workflow | `UNKNOWN` |
| Node metadata discovery | `PARTIALLY VERIFIED` |
| Python execution | `KNOWN_LIMITATION` in current setup |
| AI Assistant | `DOCUMENTED / ENVIRONMENT_DEPENDENT / PREVIEW` |

---

# 36. Recommended AAE Provider Interface

AAE should not expose raw n8n endpoints to the agent.

Instead, the agent should use provider-neutral operations:

```text
list_workflows()
get_workflow()
create_workflow()
update_workflow()

activate_workflow()
deactivate_workflow()

execute_workflow()
list_executions()
get_execution()

retry_execution()

validate_workflow()

get_node_information()
get_instance_information()

run_security_audit()

delete_workflow()
```

The n8n adapter determines how each operation is actually implemented.

---

# 37. Control Surface Principle

The AAE architecture must follow:

```text
AAE Core
    ↓
Automation Provider Interface
    ↓
n8n Adapter
    ↓
Verified Control Mechanisms
```

The agent must never assume that one particular REST endpoint is the universal control mechanism.

This permits:

- API-based execution;
- webhook-based execution;
- CLI-based operations;
- runtime metadata;
- future provider adapters;
- future automation platforms.

---

# 38. Next Capability Discovery Priorities

The remaining discovery work should focus on high-value capabilities rather than indiscriminate endpoint hunting.

Priority order:

### Priority 1 — Node Metadata

Determine how AAE can reliably discover:

- available nodes;
- node versions;
- node properties;
- operations;
- required fields;
- credential requirements.

### Priority 2 — Validation

Determine whether n8n exposes any authoritative validation mechanism.

If not, design AAE's provider-independent validation engine.

### Priority 3 — Retry

Determine whether a safe native retry mechanism exists.

If not, define the AAE retry abstraction around verified execution mechanisms.

### Priority 4 — Delete

Determine whether deletion is supported, but keep it approval-gated and non-essential to MVP.

### Priority 5 — CLI

Document which administrative and operational functions can safely be performed through the n8n CLI.

---

# 39. Architectural Conclusion

The capability discovery phase has already demonstrated that AAE can perform a substantial engineering lifecycle against a real n8n instance.

Verified lifecycle:

```text
Inspect
   ↓
Create
   ↓
Modify
   ↓
Activate
   ↓
Execute
   ↓
Inspect execution
   ↓
Detect failure
   ↓
Diagnose
   ↓
Repair
   ↓
Re-test
   ↓
Verify success
```

Therefore the absence of a usable OpenAPI specification is **not an architectural blocker**.

The correct architecture is a provider adapter with a verified capability registry rather than an OpenAPI-dependent n8n wrapper.

---

# 40. Status

**Capability discovery status:** Substantially verified; targeted discovery remains.

**OpenAPI:** Not verified; do not depend on it.

**n8n control:** Proven through multiple runtime mechanisms.

**AAE engineering lifecycle:** Core diagnose → repair → re-test cycle experimentally demonstrated.

**Next document:** `N8N_CONTROL_SURFACE.md`

**Do not begin full Codex implementation yet.**

The next stage is to convert this capability evidence into the formal n8n control surface before defining the AAE agent and architecture.