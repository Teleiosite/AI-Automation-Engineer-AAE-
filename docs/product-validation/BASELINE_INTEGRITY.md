# AAE Product Validation — Baseline Integrity Document

**Product:** AI Automation Engineer (AAE)  
**Version:** 0.1.0-prod  
**Date:** September 16, 2026  
**Status:** BASELINE FROZEN FOR PRODUCT VALIDATION  
**Classification:** Product Validation Integrity & Reproducibility Record  

---

## 1. Baseline Environment Snapshot

Prior to commencing the Stage A + Stage B Product Validation Program, the exact system state, dependencies, and environment configuration were recorded and frozen:

| Parameter | Frozen Value / Specification | Evidence |
| :--- | :--- | :--- |
| **Git Commit** | `a24526a` (`feat(planner): support Code and RespondToWebhook node planning for self-contained workflows`) | Verified via `git rev-parse HEAD` |
| **Git Branch** | `main` | Synchronized with `origin/main` |
| **Repository Cleanliness**| Clean working tree (0 uncommitted modifications) | `git status` clean |
| **Python Runtime** | Python 3.14.6 (win32, x64) | `sys.version` verified |
| **Host OS** | Windows 11 Home 10.0.22621 (Build 22621) | `systeminfo.exe` |
| **Docker Engine** | Docker Engine 29.5.3, Docker Desktop with WSL2 (Kernel 6.18.33.2) | `docker version` |
| **PostgreSQL Database** | PostgreSQL 16.15-alpine in container `aae-postgres` (port 5432) | Verified healthy, accepting connections |
| **n8n Orchestrator** | n8n 2.38.7 on Node.js v24.21.0 (port 5678, authenticated via API key) | Verified healthy, `GET /healthz` -> 200 OK |
| **Existing Test Suite**| 262 passed, 0 failed, 1 warning (100% pass rate) | `pytest tests/` clean run |
| **Pure Domain AST Purity**| 0 framework imports across all 25 modules in `app/domain/` | Verified via AST scan |
| **Production Audit Trail**| All 25 Phase Audits + `PRODUCTION_BASELINE_AUDIT.md` + `PRODUCTION_DEPLOYMENT_AUDIT.md` | Frozen in `docs/audits/` |

---

## 2. Benchmark Integrity & Anti-Contamination Rules

In accordance with Section 4 and Section 38 of the Master Codex Prompt:

1. **Independent Expected Outcomes:** Expected outcomes for all 10 scenarios are defined strictly *prior* to executing the baseline and are stored independently in `tests/product_validation/expected/` and `docs/product-validation/EXPECTED_OUTCOMES.md`.
2. **No Keyword Engineering:** Scenarios 001 through 010 are realistic human prompts formulated without artificial injection of planner keyword triggers (e.g. `code`, `validate`, `respond`).
3. **No Baseline Patching:** Once Scenario 001 begins execution, no production code, planner logic, builder logic, validation rules, or expected outcome assertions may be altered between scenarios.
4. **Failure Separation:** Environment failures, test harness defects, and genuine AAE product defects are strictly segregated in reporting.
5. **Measurement Integrity:** Transport success (`REQUEST ACCEPTED`) and execution success (`WORKFLOW STARTED / EXECUTED`) are never equated with semantic/business success (`DID THE AUTOMATION DO WHAT THE USER ACTUALLY ASKED FOR?`).

---

## 3. Reference Demonstration Record (Sarah Connor Test)

The previously demonstrated live webhook execution is recorded here as an existing **Reference Demonstration** and is intentionally excluded from the 10 baseline evaluation scenarios:
* **Workflow Target:** `Personal / Customer Lead Qualification & Email Notification` (ID: `058fiiQ6BbbdkbbJ` / `jNozYOv6gZOzmNlD`)
* **Demonstrated Path:** `Webhook Trigger` (received `POST http://localhost:5678/webhook-test/lead`) -> captured Sarah Connor synthetic lead.
* **Status:** Operational proof-of-concept verified; does not substitute for the multi-scenario general engineering benchmark.
