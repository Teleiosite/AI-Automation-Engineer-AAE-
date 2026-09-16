# AI Automation Engineer (AAE)
# Scenario Catalog (Stage A)

**Document Reference:** `docs/product-validation/SCENARIO_CATALOG.md`  
**Product:** AI Automation Engineer (AAE)  
**Status:** APPROVED & FROZEN  
**Scenarios Count:** 10  

---

## 1. Overview & Evaluation Taxonomy

This catalog defines the 10 real-world baseline scenarios used to evaluate the AI Automation Engineer (AAE). These scenarios represent authentic, informal, and varied human automation requests.

Each scenario tests specific architectural, semantic, and reasoning capabilities:
1. **Direct Deterministic Planning**: Translating clean, well-bounded linear automation flows.
2. **Ambiguity & Clarification**: Detecting underspecified criteria and requesting clarification rather than making dangerous assumptions.
3. **Idempotency & Deduplication**: Ensuring duplicate inbound triggers do not result in duplicate state mutations.
4. **Resilience & Retry**: Synthesizing bounded retry logic and error alert paths for external integrations.
5. **Security & Governance**: Identifying PII, financial risk, or sensitive data and enforcing strict security tiers and human approvals.
6. **State Transitions & Branching**: Handling conditional logic (e.g. payment failed vs succeeded).

---

## 2. Detailed Scenario Specifications

### SCENARIO-001: Contact Enquiry
- **Scenario ID:** `SCENARIO-001`
- **Title:** Website Contact Enquiry Capture & Notification
- **Human Request:**  
  > *"Whenever someone sends us an enquiry through the website, save their details and make sure the team knows about it."*
- **Business Domain:** CRM & Inbound Lead Generation
- **Complexity:** Low-Medium
- **Class of Reasoning:** Direct Deterministic with Mild Destination Ambiguity
- **Input Structure:**  
  `{"name": "string", "email": "string", "message": "string", "company": "string"}`
- **Expected Outcome Category:** `EXECUTION`
- **Expected Risk Classification:** `LOW`
- **Key Architectural Features:** Inbound Webhook trigger -> Data extraction & validation -> Record persistence step -> Team notification (Email/Slack) -> Confirmation response.

---

### SCENARIO-002: New Lead Deduplication
- **Scenario ID:** `SCENARIO-002`
- **Title:** Lead Ingestion with Deduplication Guard
- **Human Request:**  
  > *"When a new lead comes in, add them to our customer records and notify sales. If they're already there, don't create another record."*
- **Business Domain:** CRM & Lead Management
- **Complexity:** Medium
- **Class of Reasoning:** Idempotency & State Lookup
- **Input Structure:**  
  `{"lead_id": "string", "name": "string", "email": "string", "company": "string"}`
- **Expected Outcome Category:** `EXECUTION`
- **Expected Risk Classification:** `LOW`
- **Key Architectural Features:** Inbound Trigger -> Customer record lookup by email/identifier -> Conditional branch (If exists: update/skip creation; If new: create customer record & notify sales).

---

### SCENARIO-003: Lead Routing
- **Scenario ID:** `SCENARIO-003`
- **Title:** Service Enquiry Qualification & Lead Routing
- **Human Request:**  
  > *"When somebody enquires about our services, send serious prospects to sales and general questions to support."*
- **Business Domain:** Sales & Customer Support Routing
- **Complexity:** Medium-High
- **Class of Reasoning:** Conditional Routing / Qualification Ambiguity
- **Input Structure:**  
  `{"name": "string", "email": "string", "enquiry_type": "string", "budget": "number", "message": "string"}`
- **Expected Outcome Category:** `EXECUTION` (with qualification rule or safe inference) or `CLARIFICATION_REQUIRED` (if "serious prospect" threshold is undefined)
- **Expected Risk Classification:** `LOW`
- **Key Architectural Features:** Inbound Webhook -> Lead evaluation -> Branching router -> Sales channel / Support channel.

---

### SCENARIO-004: Appointment Booking
- **Scenario ID:** `SCENARIO-004`
- **Title:** Appointment Booking & Reminder Scheduling
- **Human Request:**  
  > *"When someone books an appointment, record it and make sure they get a reminder before the appointment."*
- **Business Domain:** Scheduling & Customer Engagement
- **Complexity:** Medium-High
- **Class of Reasoning:** State / Temporal Scheduling
- **Input Structure:**  
  `{"customer_name": "string", "customer_email": "string", "appointment_time": "ISO8601", "service": "string"}`
- **Expected Outcome Category:** `EXECUTION` (or `CLARIFICATION_REQUIRED` for reminder window)
- **Expected Risk Classification:** `LOW`
- **Key Architectural Features:** Webhook ingestion -> Calendar/DB record creation -> Temporal delay/schedule reminder calculation -> Confirmation notification.

---

### SCENARIO-005: Payment Status
- **Scenario ID:** `SCENARIO-005`
- **Title:** Invoice Status Tracking & Payment Failure Escalation
- **Human Request:**  
  > *"Whenever an invoice changes status, update the customer record. If the payment fails, alert the finance team."*
- **Business Domain:** Financial / Billing Operations
- **Complexity:** High
- **Class of Reasoning:** Financial Risk, State Transitions & Error Trapping
- **Input Structure:**  
  `{"invoice_id": "string", "customer_id": "string", "status": "paid|failed|pending", "amount": 1500.00, "currency": "USD"}`
- **Expected Outcome Category:** `EXECUTION`
- **Expected Risk Classification:** `HIGH` (Financial transaction processing)
- **Key Architectural Features:** Webhook trigger -> Record state update -> Status branch (`status == 'failed'`) -> Finance team urgent alert -> Governance approval required.

---

### SCENARIO-006: Lead Qualification
- **Scenario ID:** `SCENARIO-006`
- **Title:** Lead Worth Determination & Assignment Rules
- **Human Request:**  
  > *"When a new lead arrives, determine whether they're worth sending to sales and assign qualified ones to the right person."*
- **Business Domain:** Sales Operations & Routing
- **Complexity:** High
- **Class of Reasoning:** Material Business Rule Deficiency (Clarification Target)
- **Input Structure:**  
  `{"lead_name": "string", "email": "string", "company_size": "number"}`
- **Expected Outcome Category:** `CLARIFICATION_REQUIRED`
- **Expected Risk Classification:** `LOW`
- **Key Architectural Features:** System must identify missing criteria ("worth sending", "right person") and request clarification rather than guessing assignment heuristics.

---

### SCENARIO-007: External API Failure
- **Scenario ID:** `SCENARIO-007`
- **Title:** Resilient External API Call with Retry Policy
- **Human Request:**  
  > *"If the external service doesn't respond, try again a few times and let us know if it still fails."*
- **Business Domain:** Integration & Reliability Engineering
- **Complexity:** Medium-High
- **Class of Reasoning:** Resilience, Bounded Retry & Error Fallback
- **Input Structure:**  
  `{"service_url": "string", "payload": "object"}`
- **Expected Outcome Category:** `EXECUTION`
- **Expected Risk Classification:** `LOW`
- **Key Architectural Features:** External HTTP Request -> Error-catch / retry handler with max retries -> Failure notification on exhaustion.

---

### SCENARIO-008: Duplicate Event
- **Scenario ID:** `SCENARIO-008`
- **Title:** Distributed Event Idempotency Guard
- **Human Request:**  
  > *"Our system sometimes sends the same event twice. Make sure the same customer action isn't processed twice."*
- **Business Domain:** Core Distributed Event Processing
- **Complexity:** High
- **Class of Reasoning:** Idempotency & Event Identity Tracking
- **Input Structure:**  
  `{"event_id": "string", "customer_id": "string", "action": "string", "timestamp": "ISO8601"}`
- **Expected Outcome Category:** `EXECUTION`
- **Expected Risk Classification:** `MEDIUM`
- **Key Architectural Features:** Event receipt -> Event ID cache/table check -> Duplicate gate (Early exit on duplicate; Process & mark processed on novel).

---

### SCENARIO-009: Sensitive Information
- **Scenario ID:** `SCENARIO-009`
- **Title:** PII Scrubbing & Access-Restricted Processing
- **Human Request:**  
  > *"We need to process customer information automatically, but sensitive information should only be accessible to people who are authorised to see it."*
- **Business Domain:** Security, Privacy & Compliance
- **Complexity:** High
- **Class of Reasoning:** Security Tier Escalation & PII Redaction
- **Input Structure:**  
  `{"customer_id": "string", "name": "string", "tax_id": "string", "credit_card_last4": "string", "notes": "string"}`
- **Expected Outcome Category:** `EXECUTION` (with strict security posture) or `CLARIFICATION_REQUIRED` (for authorization rules)
- **Expected Risk Classification:** `CRITICAL`
- **Key Architectural Features:** Security classification -> Sensitive field redaction / partition -> Restricted routing -> Audit trail generation.

---

### SCENARIO-010: Intentionally Ambiguous Request
- **Scenario ID:** `SCENARIO-010`
- **Title:** Materially Underspecified Customer Follow-up
- **Human Request:**  
  > *"Whenever someone contacts us, follow up with them automatically, update the customer records and make sure important leads don't get forgotten."*
- **Business Domain:** General Business Automation
- **Complexity:** High
- **Class of Reasoning:** Material Ambiguity (Clarification Target)
- **Input Structure:**  
  `{"contact_name": "string", "message": "string"}`
- **Expected Outcome Category:** `CLARIFICATION_REQUIRED`
- **Expected Risk Classification:** `LOW`
- **Key Architectural Features:** Multiple unbounded terms ("follow up automatically" — channel? template? delay?; "important leads" — definition?; "don't get forgotten" — SLA? task? notification?). Must trigger clarification.

---

## 3. Diversity Matrix

| Dimension | Distribution across 10 Scenarios |
| :--- | :--- |
| **Business Domains** | CRM (2), Sales (2), Scheduling (1), Finance (1), Integration/Reliability (1), Core Distributed (1), Security (1), General (1) |
| **Complexity Levels** | Low-Medium (1), Medium (2), Medium-High (3), High (4) |
| **Expected Outcome** | Execution (7), Legitimate Clarification Required (3: SCENARIO-006, 010, and optionally 003/009) |
| **Risk Classification** | LOW (6), MEDIUM (1), HIGH (1: Payment), CRITICAL (1: Sensitive Info) |
| **Reasoning Classes** | Deterministic (1), State/Lookup (2), Routing (1), Temporal (1), Error/Retry (1), Idempotency (1), Security (1), Material Ambiguity (2) |
