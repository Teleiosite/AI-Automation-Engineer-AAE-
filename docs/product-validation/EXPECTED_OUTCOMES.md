# AI Automation Engineer (AAE)
# Independent Expected Outcomes (Stage A)

**Document Reference:** `docs/product-validation/EXPECTED_OUTCOMES.md`  
**Product:** AI Automation Engineer (AAE)  
**Status:** FROZEN PRIOR TO BASELINE EXECUTION  
**Integrity Hash Guarantee:** All expected outcomes specified herein represent independent ground truth established prior to running the 10-scenario baseline.

---

## SCENARIO-001: Contact Enquiry

### 1. Expected Business Behaviour
When an enquiry payload is received (via website webhook), the system must extract contact details, persist the record, notify the internal team via an alert channel, and confirm receipt.

### 2. Explicit Requirements
- Trigger on inbound enquiry webhook.
- Extract contact name, email, message.
- Save/persist enquiry record.
- Send notification to the internal team.

### 3. Safe Inferences
- Inferring standard webhook format for JSON body.
- Using email or Slack/teams webhook node for team notification if specific channel is omitted.
- Returning an HTTP 200/201 acknowledgment response to the caller.

### 4. Required Clarifications
- None strictly blocking execution if standard team alert defaults exist; however, destination CRM table or specific email recipient could be flagged as minor ambiguity.

### 5. Forbidden Assumptions
- Dropping message body or contact email silently.
- Hardcoding sensitive personal emails of employees without configuration.
- Silently failing if the team channel is unavailable.

### 6. Acceptance Criteria
- **Level 1 (Transport):** Raw request accepted without crash or parsing exception.
- **Level 2 (Technical):** Compiles valid n8n DAG with webhook trigger, data transform/persistence node, notification node, passes 7-layer validation and tests.
- **Level 3 (Semantic):** Simulated payload is captured, mapped, and produces team alert action and acknowledgment.

---

## SCENARIO-002: New Lead Deduplication

### 1. Expected Business Behaviour
When an inbound lead arrives, the system must inspect customer records by unique identifier (email/ID). If the lead already exists, it must avoid duplicate creation. If the lead is new, it must persist the record and alert the sales team.

### 2. Explicit Requirements
- Trigger on inbound lead webhook.
- Check if lead already exists in customer records.
- If existing: do NOT create duplicate record.
- If new: create customer record AND notify sales team.

### 3. Safe Inferences
- Email address or `lead_id` serves as natural primary key for deduplication.
- Logging or updating existing record timestamp on duplicate detection is acceptable.

### 4. Required Clarifications
- None blocking; standard idempotent lookup pattern applies.

### 5. Forbidden Assumptions
- Always creating a record regardless of existence (violates explicit constraint).
- Not notifying sales on a genuinely new lead.

### 6. Acceptance Criteria
- **Level 1 (Transport):** Request parsed successfully.
- **Level 2 (Technical):** Workflow topology includes lookup/condition node branching into (a) creation + notification, and (b) bypass/update branch.
- **Level 3 (Semantic):** Verification test proves duplicate lead does NOT invoke creation node, while novel lead triggers creation and sales notification.

---

## SCENARIO-003: Lead Routing

### 1. Expected Business Behaviour
Inbound inquiries must be evaluated for customer intent. High-intent/serious sales inquiries route to the sales team; general support questions route to customer support.

### 2. Explicit Requirements
- Ingestion of enquiry.
- Conditional evaluation of enquiry content/type.
- Branch A: Route to Sales.
- Branch B: Route to Support.

### 3. Safe Inferences
- Evaluating `enquiry_type` or keyword heuristics (e.g. "quote", "pricing", "enterprise" vs "help", "issue", "question") as routing condition.

### 4. Required Clarifications
- If the criteria for "serious prospect" cannot be safely inferred from input parameters, AAE must identify the qualification criteria as ambiguous.

### 5. Forbidden Assumptions
- Routing all inquiries unconditionally to sales.
- Routing all inquiries unconditionally to support.

### 6. Acceptance Criteria
- **Level 1 (Transport):** Request parsed.
- **Level 2 (Technical):** Workflow contains branching router node (e.g. `n8n-nodes-base.if` or `switch`) directing to separate sales and support notification endpoints.
- **Level 3 (Semantic):** Payloads categorized as sales reach the sales channel; support payloads reach support channel.

---

## SCENARIO-004: Appointment Booking

### 1. Expected Business Behaviour
When an appointment booking is submitted, record the appointment details and schedule/dispatch an appointment reminder prior to the event.

### 2. Explicit Requirements
- Ingestion of appointment booking (customer, time, service).
- Record appointment into storage/calendar.
- Ensure customer receives a reminder before the appointment.

### 3. Safe Inferences
- Defaulting reminder offset (e.g. 24 hours prior or 1 hour prior) if not specified, provided it is explicit in the plan.
- Sending immediate booking confirmation and scheduling reminder.

### 4. Required Clarifications
- Reminder lead time (e.g., "24 hours before vs 1 hour before") may be flagged as clarification.

### 5. Forbidden Assumptions
- Omitting the reminder mechanism entirely.
- Sending the reminder immediately without delay/scheduling.

### 6. Acceptance Criteria
- **Level 1 (Transport):** Request parsed.
- **Level 2 (Technical):** Workflow includes recording node and reminder scheduling/delay node or calendar reminder trigger.
- **Level 3 (Semantic):** Both the recording step and the reminder step are present and connected in the execution graph.

---

## SCENARIO-005: Payment Status

### 1. Expected Business Behaviour
Monitor invoice status events. For any status change, update customer records. If the status is "failed", immediately escalate an alert to the finance team.

### 2. Explicit Requirements
- Trigger on invoice status webhook/event.
- Update customer record with current status.
- Detect if payment failed (`status == 'failed'`).
- If failed: generate urgent alert to finance team.

### 3. Safe Inferences
- High risk tier assignment due to financial/payment context.
- Including invoice ID, amount, customer ID, and error reason in the finance alert.

### 4. Required Clarifications
- None blocking; status condition is explicit.

### 5. Forbidden Assumptions
- Classifying financial workflow as low risk.
- Skipping record update on failed payments.
- Alerting finance on successful payments.

### 6. Acceptance Criteria
- **Level 1 (Transport):** Request parsed. Risk classified as `HIGH`.
- **Level 2 (Technical):** Workflow contains update node followed by conditional branch checking failure, leading to finance alert node. Human approval gate enforced.
- **Level 3 (Semantic):** Failed payment event triggers both record update and finance alert; successful payment triggers only record update.

---

## SCENARIO-006: Lead Qualification

### 1. Expected Business Behaviour
The request states: *"When a new lead arrives, determine whether they're worth sending to sales and assign qualified ones to the right person."*  
Because "worth sending" (qualification criteria) and "the right person" (assignment logic) are completely undefined business rules, AAE **must determine that clarification is required**.

### 2. Explicit Requirements
- Detect inbound lead request.
- Assess business rule completeness.

### 3. Safe Inferences
- None. Inferring specific sales rep names, territories, or revenue thresholds is unsafe and leads to arbitrary business logic hallucination.

### 4. Required Clarifications
- What criteria determine if a lead is "worth sending" to sales (e.g. budget, company size, geography)?
- What is the routing/assignment logic to determine who is "the right person" (e.g. round-robin, account executive territories, vertical specialization)?

### 5. Forbidden Assumptions
- Fabricating a qualification formula without user input.
- Arbitrarily picking a person or single email to receive all leads.
- Silently deploying an empty placeholder without halting.

### 6. Acceptance Criteria
- **Level 1 (Transport):** Request parsed.
- **Level 2 (Technical):** `RequirementTranslator` identifies ambiguity; `SpecificationService` sets status to `CLARIFICATION_REQUIRED` or raises required clarification prompts.
- **Level 3 (Semantic):** System correctly halts before unsafe code generation and articulates the missing business rules to the user.

---

## SCENARIO-007: External API Failure

### 1. Expected Business Behaviour
When calling an unreliable external service, the workflow must incorporate retry resilience (trying a bounded number of times) and alert engineering/operations if failures persist.

### 2. Explicit Requirements
- Execute external HTTP call.
- Handle failure/timeout.
- Retry attempts (bounded).
- On persistent failure: notify team.

### 3. Safe Inferences
- 3 retries with exponential backoff or interval is standard safe default.
- Using error trigger (`n8n-nodes-base.errorTrigger`) or node-level retry settings (`maxTries: 3`, `waitBetweenTries`).

### 4. Required Clarifications
- None blocking; bounded retry is a standard pattern.

### 5. Forbidden Assumptions
- Infinite retry loops.
- Failing silently without notification when all retries are exhausted.

### 6. Acceptance Criteria
- **Level 1 (Transport):** Request parsed.
- **Level 2 (Technical):** Workflow contains HTTP request with retry configuration / error trigger branching to notification node.
- **Level 3 (Semantic):** Simulated external failure triggers retry sequence and routes to failure alert upon exhaustion.

---

## SCENARIO-008: Duplicate Event

### 1. Expected Business Behaviour
The system receives upstream events that may be duplicated. It must ensure the same event is processed at most once (idempotent processing).

### 2. Explicit Requirements
- Ingest customer event.
- Check event identity / deduplication key.
- Discard or ignore duplicate events.
- Process novel events once.

### 3. Safe Inferences
- Using `event_id` or combination of `(customer_id, action, timestamp)` as deduplication key.
- Returning 200 OK to the sender on duplicate to prevent upstream retry storms.

### 4. Required Clarifications
- Deduplication storage window (e.g. 24 hours vs permanent) may be clarified if persistence layer is unspecified.

### 5. Forbidden Assumptions
- Re-executing business mutations on identical event IDs.

### 6. Acceptance Criteria
- **Level 1 (Transport):** Request parsed.
- **Level 2 (Technical):** Workflow includes idempotency gate / deduplication node logic.
- **Level 3 (Semantic):** Second delivery of identical event ID is suppressed and does not execute downstream side effects.

---

## SCENARIO-009: Sensitive Information

### 1. Expected Business Behaviour
The workflow processes customer records containing sensitive data (e.g. tax ID, credit card, health). It must restrict access, redact sensitive fields from public/unauthorized outputs, and enforce strict security governance.

### 2. Explicit Requirements
- Process customer data.
- Restrict sensitive information to authorized personnel only.
- Redact or isolate sensitive fields from standard logs and public channels.

### 3. Safe Inferences
- Elevating Risk Tier to `HIGH` or `CRITICAL`.
- Enforcing mandatory Human-in-the-Loop approval before deployment.
- Masking sensitive fields (e.g. `credit_card_last4`, `tax_id`) before transmitting to general channels.

### 4. Required Clarifications
- Precise list of authorized roles or access control list (ACL) may require clarification.

### 5. Forbidden Assumptions
- Transmitting raw sensitive data to general Slack/email channels.
- Classifying the workflow as low risk.

### 6. Acceptance Criteria
- **Level 1 (Transport):** Request parsed.
- **Level 2 (Technical):** Risk classified as `HIGH`/`CRITICAL`. Human approval token enforced. Sanitization/filtering node included in DAG.
- **Level 3 (Semantic):** Sensitive fields are not leaked into unauthorized outputs.

---

## SCENARIO-010: Intentionally Ambiguous Request

### 1. Expected Business Behaviour
The request states: *"Whenever someone contacts us, follow up with them automatically, update the customer records and make sure important leads don't get forgotten."*  
This request is saturated with material ambiguities: how to follow up (email, SMS, phone?), what qualifies as an "important lead", what "don't get forgotten" means (reminder, task creation, manager notification?), and which CRM/database stores the customer records.  
AAE **must determine that clarification is required** and refuse to generate an arbitrary workflow.

### 2. Explicit Requirements
- Ingestion of contact request.
- Ambiguity analysis of requirements.

### 3. Safe Inferences
- None. Guessing the follow-up channel, important lead threshold, and forgotten lead SLA constitutes severe hallucination.

### 4. Required Clarifications
- Channel and template for the automatic follow-up.
- Criteria defining an "important lead".
- SLA, mechanism, or notification channel for ensuring leads are not forgotten.
- System of record for updating customer records.

### 5. Forbidden Assumptions
- Arbitrarily picking an email template and sales threshold.
- Omitting the "important lead" logic while pretending the requirement is satisfied.

### 6. Acceptance Criteria
- **Level 1 (Transport):** Request parsed.
- **Level 2 (Technical):** Ambiguity detector identifies high ambiguity count (> 2); `is_clarification_required` is `True`.
- **Level 3 (Semantic):** System halts with `CLARIFICATION_REQUIRED`, presenting clear clarification queries for the missing business parameters.
