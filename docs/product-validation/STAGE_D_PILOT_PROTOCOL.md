# AI AUTOMATION ENGINEER (AAE)

## STAGE D — CONTROLLED HUMAN PILOT PROTOCOL
### Non-Developer Usability & Empirical Observation Protocol

**Document ID:** `PROTO-AAE-STAGE-D-2026-09`  
**Product:** AI Automation Engineer (AAE)  
**Codename:** AAE  
**Version Target:** `1.0.0-rc1`  
**Owner:** Teleiocraft Solutions  
**Repository:** `C:\Users\Owner\Desktop\AAE`  
**Branch:** `validation/stage-d-release-readiness`  
**Audience:** Pilot Facilitators, UX Researchers, Usability Evaluators  

---

## 1. Executive Protocol Summary

The objective of the Stage D Controlled Pilot is to rigorously measure whether non-technical enterprise personnel can operate AAE to construct, modify, clarify, and govern automated business workflows without technical assistance.

This document specifies the exact end-to-end testing protocol, observational standards, environment configurations, and measurement instruments required to conduct fair, unassisted, and repeatable human trials.

---

## 2. Participant Cohort Profiles (5 Standard Personas)

To prevent bias and evaluate true generalisation across business disciplines, the cohort must recruit participants matching five predefined non-developer profiles:

### Profile A: Non-Technical Operations Manager
- **Domain Context:** Facilities, logistics, or general business operations.
- **Skill Profile:** Highly proficient with Google Workspace / Microsoft 365, email, and Slack; zero knowledge of programming, JSON, REST APIs, or webhook listeners.
- **Assigned Tasks:**
  - `TASK-D01`: Simple Automation (Form submission to team notification).
  - `TASK-D08`: Natural Variation (Colloquial prompt with filler phrases).

### Profile B: Business Analyst
- **Domain Context:** Financial operations, FP&A, or business process modeling.
- **Skill Profile:** Understands business rules, decision trees, and SQL table structures conceptually; cannot write API client code or construct visual n8n execution graphs.
- **Assigned Tasks:**
  - `TASK-D02`: Multi-Step Automation (Invoice parsing, DB record, manager approval).
  - `TASK-D06`: Business-Rule Ambiguity (Loyalty discounting with undefined criteria).

### Profile C: Junior Administrator
- **Domain Context:** IT helpdesk, customer onboarding, or SaaS tool administration.
- **Skill Profile:** Configures SaaS user accounts and permissions; understands system outages but lacks experience handling network retries or dead-letter queues.
- **Assigned Tasks:**
  - `TASK-D05`: External Failure Recovery (Third-party CRM sync outage).

### Profile D: Support Lead
- **Domain Context:** Customer support, helpdesk escalation, and ticketing operations.
- **Skill Profile:** Manages customer tickets and resolution SLAs; does not think in deterministic DAG topologies.
- **Assigned Tasks:**
  - `TASK-D03`: Ambiguous Automation (Customer complaint handling with vague scope).

### Profile E: Compliance & Risk Officer
- **Domain Context:** Internal audit, regulatory compliance, or anti-money laundering (AML).
- **Skill Profile:** Rigorous adherence to governance, approval boundaries, separation of duties, and audit trails; highly sensitive to unauthorized actions or financial exposure.
- **Assigned Tasks:**
  - `TASK-D04`: Security-Sensitive Automation (Customer refund dispute).
  - `TASK-D07`: High-Risk Approval Boundary (Wire transfer escalation).

---

## 3. Environment & Workspace Setup

Prior to participant arrival, the testing environment must be provisioned as follows:
1. **Operating System:** Windows 11 / 10 Enterprise or macOS Sonoma.
2. **Terminal / Client Interface:**
   - Dedicated AAE interactive terminal session (`python scripts/test_real_life.py` or interactive API client).
   - Clean terminal window with standard 14pt monospace font.
3. **Target Automation Canvas:**
   - Web browser opened to the live local n8n instance canvas at `http://localhost:5678`.
   - Workspaces cleared of prior demonstration workflows.
4. **Database Verification:**
   - PostgreSQL 16 active on `localhost:5432` (`aae_dev`).
   - Tables migrated and accessible via `UnitOfWork`.
5. **Screen & Audio Recording:**
   - Screen capture software active (recording terminal, browser, and audio with participant consent).

---

## 4. Facilitator Operating Rules & Observation Protocol

To guarantee scientific objectivity, facilitators must adhere strictly to the **Non-Intervention Protocol**:

> [!WARNING]
> **Facilitator Non-Intervention Rule:**
> Facilitators MUST NOT:
> 1. Guide the participant on how to phrase requests.
> 2. Explain technical terms like "webhook", "DAG", "node", "JSON", or "AST".
> 3. Suggest parameters, table names, or condition thresholds.
> 4. Intervene when the participant pauses or appears confused.
>
> Facilitators MAY ONLY:
> 1. Read the task objective scenario prompt aloud if requested.
> 2. Remind the participant to "think aloud".
> 3. Terminate a task if the participant explicitly declares they cannot proceed or if the 10-minute timeout is reached.

### 4.1 Think-Aloud Methodology
Participants are instructed:
> *"Please speak your thoughts aloud as you work. Tell us what you are trying to do, what you expect the system to do, what you understand from the system's responses, and whenever something surprises or confuses you."*

### 4.2 Observational Rubric
The facilitator or silent observer must record:
- Time to enter initial prompt.
- Time spent reading system output / clarification questions.
- Whether the participant understands the clarification question on the first attempt.
- Emotional responses (confusion, satisfaction, frustration, hesitation).
- Final state: Success (verified in n8n canvas), Controlled Clarification Halt, or Abandonment.

---

## 5. Post-Task Measurement Instruments

### 5.1 System Usability Scale (SUS)
At the conclusion of the session, each participant completes the standard 10-item System Usability Scale (rated 1 = Strongly Disagree to 5 = Strongly Agree):

1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.

**Scoring Method:**
- For odd-numbered items ($1, 3, 5, 7, 9$): Score contribution = $\text{Rating} - 1$.
- For even-numbered items ($2, 4, 6, 8, 10$): Score contribution = $5 - \text{Rating}$.
- Total Score = $\sum(\text{Contributions}) \times 2.5$ (Scale: $0 - 100$).
- Target: $\ge 75.0$.

### 5.2 Qualitative Debriefing Interview
Four open-ended debriefing questions:
1. *"When the system asked you questions to clarify what you wanted, did those questions make sense in terms of your business goal?"*
2. *"Did you feel in control of whether the workflow actually went live?"*
3. *"Were there any words or messages that felt too technical or confusing?"*
4. *"If you had this tool in your daily job, what would prevent you from using it?"*

---

## 6. Execution Certification Requirements

In adherence to the **Strict Truth-in-Reporting Invariant**, any published results derived from this protocol must include:
- Date, location, and facilitator identity.
- Full unedited transcripts and timestamps.
- Explicit participant consent forms on file.
- If unperformed, the results document must certify:
  `STATUS: NOT EXECUTED — HUMAN PARTICIPANT REQUIRED`.
