# ADR 0002: n8n Execution Strategy and OpenAPI Limitation

## Status
ACCEPTED

## Context
During runtime verification of the local n8n 2.38.7 instance (`http://localhost:5678`), two critical integration constraints were verified:

1. Direct execution via the REST API endpoint:
   ```text
   POST /api/v1/workflows/{id}/run
   ```
   returned:
   ```text
   405 Method Not Allowed
   ```
   Conclusion: Native REST workflow execution is UNSUPPORTED on this instance.

2. Webhook-triggered workflow execution:
   ```text
   POST http://localhost:5678/webhook/aae-webhook-test
   ```
   successfully triggered workflow execution and created an execution record.

3. OpenAPI specification endpoint:
   ```text
   GET /openapi.json
   ```
   returned HTTP 200, but the response body contained the Vue/Vite n8n web editor HTML, not an OpenAPI JSON/YAML specification.

## Decision

### 1. Direct Execution
Direct workflow execution via `POST /api/v1/workflows/{id}/run` is classified as `UNSUPPORTED`. AAE must not construct execution workflows around this endpoint or attempt to fabricate parameters to bypass the 405 response.

### 2. Execution Routing Logic & Workaround Guardrails
The webhook execution mechanism is a verified workaround (`N8N-WA-001`), NOT a universal native execution mechanism.
AAE must never automatically route all `execute_workflow()` calls to webhooks.
Instead, the provider must implement the following deterministic evaluation:

```text
Native execution capability
        ↓
if unavailable
        ↓
Check workaround applicability
        ↓
Compatible webhook trigger available on workflow?
    YES → use verified workaround (N8N-WA-001)
    NO  → return explicit capability limitation / BLOCK
```

The system must never claim that webhook execution is equivalent to native execution.

### 3. OpenAPI Endpoint Classification
`GET /openapi.json` is classified as:
```text
Endpoint: GET /openapi.json
Observed: HTTP 200
Returned content: n8n editor HTML
Conclusion: Not a usable OpenAPI specification source in the tested n8n 2.38.7 environment.
Classification: KNOWN_LIMITATION
```
AAE must not attempt to dynamically generate or synthesize the n8n provider adapter from `/openapi.json`. Explicit interfaces, documented schemas, and runtime-verified models must be used.

## Consequences
- Execution is safe, deterministic, and honest about provider capabilities.
- Workflows without compatible webhook triggers fail closed with explicit capability errors.
