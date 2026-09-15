# AAE Workaround Registry

This registry documents all non-native workarounds used by the AI Automation Engineer (AAE) across automation providers. Every entry must preserve capability truthfulness and adhere to strict safety guardrails.

---

## N8N-WA-001: Webhook-Triggered Workflow Execution

| Field | Value |
|---|---|
| **ID** | `N8N-WA-001` |
| **Capability** | Workflow Execution / Triggering |
| **Native Status** | `UNSUPPORTED` (`POST /api/v1/workflows/{id}/run` returns 405 Method Not Allowed on n8n 2.38.7) |
| **Workaround** | Execute workflow via an active HTTP Webhook trigger node (`POST /webhook/{path}`) |
| **Provider** | n8n |
| **Provider Version** | 2.38.7 |
| **Risk** | Low to Moderate (Workaround requires workflow to have an active, compatible webhook trigger node; webhook URLs may be exposed if unauthenticated) |
| **Prerequisites** | 1. Workflow must be activated.<br>2. Workflow must contain an HTTP Webhook trigger node.<br>3. Webhook path and HTTP method must match the trigger node configuration.<br>4. Network connectivity between AAE and n8n webhook listener must be verified. |
| **Limitations** | 1. Only works for workflows explicitly designed with webhook triggers.<br>2. Workflows with schedule, manual, poll, or event triggers cannot be executed through this workaround.<br>3. Does not provide native synchronous execution handles unless webhook is configured with 'Respond to Webhook' node.<br>4. Workaround MUST NOT be silently treated as a universal substitute for native execution. |
| **Verification Method** | Runtime execution test: `POST http://localhost:5678/webhook/aae-webhook-test` verified execution creation in n8n execution history. |
| **Rollback** | Deactivate workflow or delete/disable webhook trigger node in workflow JSON. |
| **Approval Requirement** | Human approval required before triggering external side-effect-producing webhooks in staging/production environments. |
| **Last Verification Date** | 13 September 2026 / 14 September 2026 |

---

## Registry Rules

1. **No Silent Workarounds**: Any mechanism that bypasses or substitutes for a missing native capability must be documented here.
2. **Pre-flight Checks**: The provider adapter must verify that all prerequisites of the workaround are satisfied before executing it.
3. **Fail-Closed**: If a workflow lacks the necessary trigger for `N8N-WA-001`, execution must be blocked with an explicit capability limitation, rather than fabricating a trigger or retrying unsupported endpoints.
