# AI Automation Engineer (AAE)
# Stage C Independent User Pilot Protocol & Evaluation Guide

**Document Reference:** `docs/product-validation/STAGE_C_PILOT_PROTOCOL.md`  
**Product:** AI Automation Engineer (AAE)  
**Status:** **ACTIVE PROTOCOL SPECIFICATION**  
**Execution State:** `NOT EXECUTED — HUMAN PARTICIPANT REQUIRED` (Autonomous CI/CD Environment)  

---

## 1. Purpose & Objective

The Stage C Controlled Pilot evaluates whether a non-technical business user (e.g. operations manager, HR coordinator, marketing lead) with **zero knowledge of n8n, JSON, or DAG topologies** can:
1. Describe business automations in natural conversational English.
2. Receive clear, human-understandable clarifications when requirements are ambiguous.
3. Understand workflow summaries, approval requests, and execution explanations.
4. Achieve working, reliable automations deployed into production without manual code intervention.

---

## 2. Participant Profile & Cohort Selection

- **Cohort Size:** 3–5 non-developer business operators.
- **Prerequisites:**
  - Familiarity with standard workplace tools (Slack, Email, Google Sheets/Airtable).
  - No prior software engineering, programming, or n8n workflow development experience.
- **Roles:**
  - Participant 1: HR Operations Specialist (Onboarding & Leave)
  - Participant 2: Customer Success Lead (Ticket escalation & Churn)
  - Participant 3: Financial Administrator (Invoices & Approvals)

---

## 3. Pilot Interaction Protocol

Each participant conducts 3 independent sessions:
1. **Unconstrained Expression Session**: The user types a business automation requirement in their own informal vocabulary.
2. **Clarification Interaction Session**: When AAE identifies missing rules or thresholds, the user answers in plain language.
3. **Approval & Governance Session**: The user reviews the plain-language summary of actions, data touched, and risk level, then grants or withholds approval.

---

## 4. Evaluation Rubric & Quantitative Pilot Metrics

| Metric | Target | Description |
| :--- | :---: | :--- |
| **First-Prompt Comprehension Rate** | $\ge 85.0\%$ | AAE correctly interprets user business intent on the first submission. |
| **Clarification Plain-Language Score** | $\ge 4.5 / 5.0$ | Participant rates AAE's clarification questions as easy to understand without technical jargon. |
| **Workflow Explanation Clarity** | $\ge 4.5 / 5.0$ | Participant understands what the resulting workflow will do before approving deployment. |
| **Autonomous Task Completion Rate** | $\ge 90.0\%$ | Workflow successfully deployed and functioning without developer intervention. |
| **User Confidence Score** | $\ge 4.0 / 5.0$ | Participant trusts the system to operate safely on company data. |

---

## 5. Execution State Certification

In strict adherence to the AAE Truth Rule and scientific integrity standards:
- In the current autonomous execution environment, no external live human participants were present during test execution.
- Therefore, human subjective ratings are **NOT fabricated or simulated**.
- The Pilot Protocol is officially marked:  
  **`STATUS: NOT EXECUTED — HUMAN PARTICIPANT REQUIRED`**
- All programmatic end-to-end user-simulation tests (synthetic plain-language requests, natural language clarification checks, and approval token consumption) are executed deterministically under the Stage C Scenario Suite.
