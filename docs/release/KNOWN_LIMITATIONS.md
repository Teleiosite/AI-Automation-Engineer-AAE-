# AI AUTOMATION ENGINEER (AAE)

## RELEASE KNOWN LIMITATIONS & OPERATIONAL WORKAROUNDS
### Product Version: v1.0.0-rc1

**Owner:** Teleiocraft Solutions  
**Repository:** `C:\Users\Owner\Desktop\AAE`  

---

## 1. Overview

This document provides transparent operational guidance regarding current product boundaries and architectural constraints in **AAE v1.0.0-rc1**, along with verified workarounds.

---

## 2. Catalog of Known Limitations

### 1. No Built-in Custom SPA Web UI (`LIM-001`)
- **Nature:** Architectural design choice.
- **Description:** AAE is a backend automation engineering engine. It does not provide a custom React or Vue web application.
- **Operational Workaround:** Users interact with AAE via the interactive terminal interface (`scripts/test_real_life.py`) or REST API. Visual workflow management, debugging, and execution inspection take place directly on the live n8n web canvas at `http://localhost:5678`.
- **Roadmap:** v1.1 will introduce a web-based chat widget.

### 2. n8n Community Edition Headless Triggering (`LIM-002`)
- **Nature:** Upstream third-party restriction.
- **Description:** n8n Community Edition does not expose a public manual execution API endpoint (`POST /workflows/{id}/execute`).
- **Operational Workaround:** AAE configures workflows to trigger via Webhooks (`/webhook/{path}` or `/webhook-test/{path}`) or Schedules. Workflows are invoked by sending HTTP payloads to their live webhook endpoints.
- **Roadmap:** Native headless execution available when paired with n8n Enterprise Edition.

### 3. Batch Clarification vs. Step-by-Step Wizard (`LIM-003`)
- **Nature:** Interface ergonomics.
- **Description:** When an automation prompt contains multiple distinct ambiguities, AAE outputs all clarification questions at once rather than asking one question per turn.
- **Operational Workaround:** Non-developers should address each listed question in their follow-up response.
- **Roadmap:** v1.1 conversational guided wizard.

### 4. Shared Canvas Multi-Tenancy (`LIM-004`)
- **Nature:** Upstream n8n Community Edition constraint.
- **Description:** n8n Community Edition operates in a single-organization shared workspace without multi-tenant role-based access control (RBAC).
- **Operational Workaround:** For multi-client service providers, provision dedicated containerized n8n instances per tenant, or deploy n8n Enterprise Edition.

### 5. Advanced Mathematical Formulas (`LIM-005`)
- **Nature:** Domain reasoning boundary.
- **Description:** Custom mathematical formulas (e.g. specialized financial amortization tables) must be explicitly stated in the request. The system does not invent ungrounded financial calculations.
- **Operational Workaround:** Include the calculation formula directly in the prompt or integrate a dedicated microservice.
