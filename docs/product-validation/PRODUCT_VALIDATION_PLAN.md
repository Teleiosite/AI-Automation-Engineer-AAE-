# AI Automation Engineer (AAE)
# Product Validation Plan (Stage A)

**Document Reference:** `docs/product-validation/PRODUCT_VALIDATION_PLAN.md`  
**Product:** AI Automation Engineer (AAE)  
**Codename:** AAE  
**Owner:** Teleiocraft Solutions  
**Lead Roles:** Lead Production Engineer, Reliability Engineer, Security Engineer, Release Engineer  
**Status:** APPROVED & ACTIVE  
**Git Baseline Commit:** `a24526a`  

---

## 1. Executive Summary & Objective

The AI Automation Engineer (AAE) has successfully completed Phases 0–24, achieving the formal status of **PRODUCTION ACCEPTED** with 262 passing regression tests, strict pure-domain framework isolation (0 external imports in `app/domain`), PostgreSQL 16 schema integrity, and live n8n orchestration.

However, **operational acceptance is not equivalent to product validation**.

The objective of the **Stage A + Stage B Real-World Product Validation Program** is to evaluate AAE's engineering efficacy when subjected to realistic, imperfect, and varied human automation requests:
1. Does AAE correctly translate informal, underspecified, or nuanced human language into precise architectural specifications?
2. Does AAE distinguish between safe inferences and required clarifications, rejecting unsafe assumptions?
3. Does AAE plan valid, acyclic Directed Acyclic Graph (DAG) topologies with appropriate nodes, idempotency mechanisms, error policies, and data mappings?
4. Does AAE construct valid production n8n workflows that pass 7-layer validation and dry-run semantic testing?
5. Does AAE enforce mandatory human governance and cryptographically verifiable audit logging before any live deployment?
6. Does the deployed automation produce the **intended business outcome** in live execution (Semantic Success), rather than merely returning HTTP 200 or emitting syntactically valid JSON (Transport / Technical Success)?

---

## 2. Operational Scope

The validation program evaluates AAE against a structured catalog of **10 realistic baseline scenarios** (§12 of Master Codex):
- **SCENARIO-001**: Contact Enquiry (Inbound Webhook to CRM & Alert)
- **SCENARIO-002**: New Lead Deduplication (Idempotency & Record Lookup)
- **SCENARIO-003**: Lead Routing (Conditional Branching & Qualification Ambiguity)
- **SCENARIO-004**: Appointment Booking (Temporal Scheduling & Notifications)
- **SCENARIO-005**: Payment Status (Financial Data Risk, Status Transitions & Error Trapping)
- **SCENARIO-006**: Lead Qualification (Missing Business Rules & Delegation — Clarification Target)
- **SCENARIO-007**: External API Failure (Resilience, Bounded Retry & Exponential Backoff)
- **SCENARIO-008**: Duplicate Event (Distributed Event Identity & Deduplication Guards)
- **SCENARIO-009**: Sensitive Information (Security Tier Escalation & PII Scrubbing)
- **SCENARIO-010**: Intentionally Ambiguous Request (Material Detail Deficiency — Clarification Target)

### Out of Scope
- Modifying core domain boundaries or introducing third-party framework imports into `app/domain/`.
- Adding ad-hoc product features, external UI dashboards, or non-automation capabilities.
- Bypassing human approval gates or relaxing fail-closed security policies.
- Optimizing code for synthetic benchmark gaming or tailoring planner logic to keyword tricks.

---

## 3. The 3-Level Measurement Model

Validation outcomes are rigorously classified across three hierarchical levels:

```
Level 1: Transport Success
  ↳ Did the request enter the system without crash, rejection, or transport failure?
      ↓
Level 2: Technical Success
  ↳ Did AAE compile a valid DAG, generate compliant n8n JSON, pass 7-layer validation,
    pass semantic dry-run, secure approval, persist to PostgreSQL 16, and deploy to n8n?
      ↓
Level 3: Semantic / Business Success
  ↳ Did the automation produce the exact business outcome intended by the human request?
    OR, if details were missing, did AAE halt and issue a required clarification?
```

A scenario is considered **SUCCESSFUL** if and only if:
- For **executable scenarios**: Level 1, Level 2, and Level 3 pass completely.
- For **ambiguity/clarification scenarios**: AAE correctly identifies the ambiguity, halts execution before unsafe synthesis, and specifies the exact required clarifications (`CLARIFICATION_REQUIRED`).

---

## 4. Primary & Secondary Product Metrics

1. **Working Automation Success Rate (WASR)**:
   $$\text{WASR} = \frac{\text{Correctly Implemented Automations Producing Expected Business Outcome}}{\text{Executable Automation Scenarios Attempted}}$$
   *(Clarification scenarios where clarification is legitimately required are excluded from the denominator)*.

2. **Clarification Correctness Rate (CCR)**:
   $$\text{CCR} = \frac{\text{Correct Clarification Determinations}}{\text{Total Scenarios with Material Ambiguity}}$$

3. **Unsafe Assumption Rate (UAR)**:
   $$\text{UAR} = \frac{\text{Automations Making Unsafe Inferences / Silently Guessing Missing Material Data}}{\text{Total Scenarios Attempted}}$$

4. **Semantic Success Rate (SSR)**:
   $$\text{SSR} = \frac{\text{Scenarios Achieving Level 3 Semantic Intent}}{\text{Total Scenarios (10)}}$$

5. **Regression & Boundary Rate**:
   - Must remain **100%** on existing unit test suite (262/262 passed).
   - Must remain **0** framework imports in `app/domain/`.

---

## 5. Governance & Anti-Contamination Rules

To prevent benchmark gaming and ensure authentic evaluation:
1. **Freeze Before Measure**: All 10 baseline scenarios must be executed against the frozen codebase before any repairs or adjustments are made ("Measure First, Fix Later").
2. **No Keyword Gaming**: Scenarios must use natural, informal human business language. The planner and translator must not rely on artificial keywords (`code`, `validate`, `respond`, etc.).
3. **Independent Expected Outcomes**: Expected outcomes are written and frozen in `EXPECTED_OUTCOMES.md` before baseline execution.
4. **Fail-Closed Security**: High-risk financial, credential, or PII operations must trigger security risk escalation and mandatory human approval.
5. **Human Gate Conservation**: The one-time approval token mechanism (`app.domain.models.approval.Approval`) must be consumed atomically upon deployment.

---

## 6. Risk Matrix & Mitigation

| Risk | Likelihood | Impact | Mitigation Strategy |
| :--- | :---: | :---: | :--- |
| **Silent Hallucination / Unsafe Guessing** | High | Severe | Clarification threshold enforcement in `RequirementTranslator` and `SpecificationService`. |
| **False Technical Success** | Medium | Moderate | Independent semantic verification using synthetic test payloads against actual workflow DAG logic. |
| **Credential / PII Leakage** | Low | Critical | Layer 4 & Layer 7 validation checks; strict synthetic test fixtures with dummy emails/keys. |
| **Regression in Core Domain** | Low | High | Automated execution of full 262-test regression suite after any repair. |
| **Infrastructure Interruption** | Low | High | Automated pre-flight health checks for PostgreSQL 16 (`5432`) and n8n (`5678`). |

---

## 7. Roles & Responsibilities

- **Lead Production Engineer**: Infrastructure verification, test harness orchestration, environment health, deployment execution.
- **Reliability Engineer**: DAG topology validation, retry policy verification, idempotency guard auditing, failure analysis.
- **Security Engineer**: PII classification, secret protection, approval token lifecycle, risk tier escalation verification.
- **Release Engineer**: Baseline integrity, git versioning, audit log verification, final release sign-off.
