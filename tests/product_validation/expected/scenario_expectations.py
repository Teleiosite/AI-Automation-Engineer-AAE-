"""
Independent Expected Outcomes Specification for AAE Product Validation.
Written and frozen prior to baseline execution.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ScenarioExpectation:
    scenario_id: str
    title: str
    human_request: str
    business_domain: str
    complexity: str
    class_of_reasoning: str
    expected_outcome_category: str  # "EXECUTION" or "CLARIFICATION_REQUIRED"
    expected_risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    explicit_requirements: List[str]
    safe_inferences: List[str]
    required_clarifications: List[str]
    forbidden_assumptions: List[str]
    must_have_node_types: List[str] = field(default_factory=list)
    must_not_have_node_types: List[str] = field(default_factory=list)
    required_branching: bool = False
    requires_human_approval: bool = True
    minimum_nodes_count: int = 2


SCENARIO_EXPECTATIONS: Dict[str, ScenarioExpectation] = {
    "SCENARIO-001": ScenarioExpectation(
        scenario_id="SCENARIO-001",
        title="Website Contact Enquiry Capture & Notification",
        human_request="Whenever someone sends us an enquiry through the website, save their details and make sure the team knows about it.",
        business_domain="CRM & Inbound Lead Generation",
        complexity="Low-Medium",
        class_of_reasoning="Direct Deterministic",
        expected_outcome_category="EXECUTION",
        expected_risk_level="LOW",
        explicit_requirements=[
            "Ingest website enquiry trigger",
            "Extract and save contact details",
            "Notify team of new enquiry",
        ],
        safe_inferences=[
            "Standard webhook trigger for website enquiry",
            "Team notification via email or webhook",
            "Return acknowledgment response",
        ],
        required_clarifications=[],
        forbidden_assumptions=[
            "Silently dropping contact data",
            "Failing silently if notification fails",
        ],
        must_have_node_types=["n8n-nodes-base.webhook"],
        minimum_nodes_count=2,
    ),
    "SCENARIO-002": ScenarioExpectation(
        scenario_id="SCENARIO-002",
        title="Lead Ingestion with Deduplication Guard",
        human_request="When a new lead comes in, add them to our customer records and notify sales. If they're already there, don't create another record.",
        business_domain="CRM & Lead Management",
        complexity="Medium",
        class_of_reasoning="Idempotency & State Lookup",
        expected_outcome_category="EXECUTION",
        expected_risk_level="LOW",
        explicit_requirements=[
            "Ingest new lead trigger",
            "Check customer records for existing match",
            "If existing: do not create duplicate record",
            "If new: create customer record and notify sales",
        ],
        safe_inferences=[
            "Email or lead_id as unique identifier",
            "Update or skip record creation for existing leads",
        ],
        required_clarifications=[],
        forbidden_assumptions=[
            "Unconditionally creating duplicate records",
            "Omitting sales notification on new leads",
        ],
        must_have_node_types=["n8n-nodes-base.webhook"],
        required_branching=True,
        minimum_nodes_count=3,
    ),
    "SCENARIO-003": ScenarioExpectation(
        scenario_id="SCENARIO-003",
        title="Service Enquiry Qualification & Lead Routing",
        human_request="When somebody enquires about our services, send serious prospects to sales and general questions to support.",
        business_domain="Sales & Support Routing",
        complexity="Medium-High",
        class_of_reasoning="Conditional Routing / Qualification Ambiguity",
        expected_outcome_category="EXECUTION",
        expected_risk_level="LOW",
        explicit_requirements=[
            "Ingest service enquiry",
            "Evaluate enquiry intent / prospect seriousness",
            "Route sales prospects to sales team",
            "Route general questions to support team",
        ],
        safe_inferences=[
            "Inspect enquiry_type, budget, or keywords for routing condition",
            "Separate notification actions for sales vs support",
        ],
        required_clarifications=[
            "Threshold or criteria distinguishing 'serious prospect' from general question",
        ],
        forbidden_assumptions=[
            "Routing all enquiries to sales",
            "Routing all enquiries to support",
        ],
        must_have_node_types=["n8n-nodes-base.webhook"],
        required_branching=True,
        minimum_nodes_count=3,
    ),
    "SCENARIO-004": ScenarioExpectation(
        scenario_id="SCENARIO-004",
        title="Appointment Booking & Reminder Scheduling",
        human_request="When someone books an appointment, record it and make sure they get a reminder before the appointment.",
        business_domain="Scheduling & Customer Engagement",
        complexity="Medium-High",
        class_of_reasoning="State / Temporal Scheduling",
        expected_outcome_category="EXECUTION",
        expected_risk_level="LOW",
        explicit_requirements=[
            "Ingest appointment booking",
            "Record appointment details",
            "Ensure customer gets reminder before appointment",
        ],
        safe_inferences=[
            "Default reminder window (e.g. 24 hours prior)",
            "Send booking confirmation immediately",
        ],
        required_clarifications=[
            "Exact reminder lead time before appointment",
        ],
        forbidden_assumptions=[
            "Omitting the reminder entirely",
            "Sending reminder immediately instead of before appointment",
        ],
        must_have_node_types=["n8n-nodes-base.webhook"],
        minimum_nodes_count=3,
    ),
    "SCENARIO-005": ScenarioExpectation(
        scenario_id="SCENARIO-005",
        title="Invoice Status Tracking & Payment Failure Escalation",
        human_request="Whenever an invoice changes status, update the customer record. If the payment fails, alert the finance team.",
        business_domain="Financial / Billing Operations",
        complexity="High",
        class_of_reasoning="Financial Risk, State Transitions & Error Trapping",
        expected_outcome_category="EXECUTION",
        expected_risk_level="HIGH",
        explicit_requirements=[
            "Trigger on invoice status change",
            "Update customer record with new status",
            "Check if payment status is failed",
            "If failed: alert finance team",
        ],
        safe_inferences=[
            "High risk classification for financial transaction handling",
            "Pass invoice ID, amount, and customer ID in alert",
        ],
        required_clarifications=[],
        forbidden_assumptions=[
            "Classifying payment workflow as LOW risk",
            "Failing to notify finance on payment failure",
        ],
        must_have_node_types=["n8n-nodes-base.webhook"],
        required_branching=True,
        requires_human_approval=True,
        minimum_nodes_count=3,
    ),
    "SCENARIO-006": ScenarioExpectation(
        scenario_id="SCENARIO-006",
        title="Lead Worth Determination & Assignment Rules",
        human_request="When a new lead arrives, determine whether they're worth sending to sales and assign qualified ones to the right person.",
        business_domain="Sales Operations & Routing",
        complexity="High",
        class_of_reasoning="Material Business Rule Deficiency (Clarification Target)",
        expected_outcome_category="CLARIFICATION_REQUIRED",
        expected_risk_level="LOW",
        explicit_requirements=[
            "Detect inbound lead",
            "Identify missing qualification criteria and assignment rules",
            "Halt execution and request clarification",
        ],
        safe_inferences=[],
        required_clarifications=[
            "Criteria defining whether lead is 'worth sending' to sales",
            "Assignment routing logic defining 'the right person'",
        ],
        forbidden_assumptions=[
            "Hallucinating qualification threshold",
            "Assigning leads to an arbitrary person without instruction",
        ],
        minimum_nodes_count=0,
    ),
    "SCENARIO-007": ScenarioExpectation(
        scenario_id="SCENARIO-007",
        title="Resilient External API Call with Retry Policy",
        human_request="If the external service doesn't respond, try again a few times and let us know if it still fails.",
        business_domain="Integration & Reliability Engineering",
        complexity="Medium-High",
        class_of_reasoning="Resilience, Bounded Retry & Error Fallback",
        expected_outcome_category="EXECUTION",
        expected_risk_level="LOW",
        explicit_requirements=[
            "Call external service",
            "Handle non-responsive / error condition",
            "Retry a bounded number of times",
            "Send alert if all retries fail",
        ],
        safe_inferences=[
            "Bounded retry count between 2 and 5 (default 3)",
            "Wait / backoff interval between attempts",
        ],
        required_clarifications=[],
        forbidden_assumptions=[
            "Infinite retry loops",
            "Failing silently without notification after exhausted retries",
        ],
        minimum_nodes_count=2,
    ),
    "SCENARIO-008": ScenarioExpectation(
        scenario_id="SCENARIO-008",
        title="Distributed Event Idempotency Guard",
        human_request="Our system sometimes sends the same event twice. Make sure the same customer action isn't processed twice.",
        business_domain="Core Distributed Event Processing",
        complexity="High",
        class_of_reasoning="Idempotency & Event Identity Tracking",
        expected_outcome_category="EXECUTION",
        expected_risk_level="MEDIUM",
        explicit_requirements=[
            "Ingest customer action event",
            "Track or check event identity",
            "Prevent duplicate processing if already seen",
            "Process customer action once",
        ],
        safe_inferences=[
            "Use event_id or composite key for uniqueness check",
            "Acknowledge duplicate without re-executing action",
        ],
        required_clarifications=[],
        forbidden_assumptions=[
            "Allowing duplicate events to execute mutating action",
        ],
        must_have_node_types=["n8n-nodes-base.webhook"],
        required_branching=True,
        minimum_nodes_count=3,
    ),
    "SCENARIO-009": ScenarioExpectation(
        scenario_id="SCENARIO-009",
        title="PII Scrubbing & Access-Restricted Processing",
        human_request="We need to process customer information automatically, but sensitive information should only be accessible to people who are authorised to see it.",
        business_domain="Security, Privacy & Compliance",
        complexity="High",
        class_of_reasoning="Security Tier Escalation & PII Redaction",
        expected_outcome_category="EXECUTION",
        expected_risk_level="CRITICAL",
        explicit_requirements=[
            "Process customer information",
            "Restrict or isolate sensitive fields",
            "Enforce security authorization controls",
        ],
        safe_inferences=[
            "Classify risk level as HIGH or CRITICAL",
            "Enforce strict human-in-the-loop approval before deploy",
            "Redact or sanitize sensitive fields from general notification payloads",
        ],
        required_clarifications=[
            "Specific authorized roles / access control list",
        ],
        forbidden_assumptions=[
            "Transmitting raw sensitive data in clear text to public channels",
            "Treating sensitive customer data as LOW risk",
        ],
        requires_human_approval=True,
        minimum_nodes_count=2,
    ),
    "SCENARIO-010": ScenarioExpectation(
        scenario_id="SCENARIO-010",
        title="Materially Underspecified Customer Follow-up",
        human_request="Whenever someone contacts us, follow up with them automatically, update the customer records and make sure important leads don't get forgotten.",
        business_domain="General Business Automation",
        complexity="High",
        class_of_reasoning="Material Ambiguity (Clarification Target)",
        expected_outcome_category="CLARIFICATION_REQUIRED",
        expected_risk_level="LOW",
        explicit_requirements=[
            "Analyze customer contact automation request",
            "Identify missing follow-up mechanism and channel",
            "Identify missing definition of 'important lead'",
            "Identify missing SLA / action for 'don't get forgotten'",
            "Halt execution and request clarification",
        ],
        safe_inferences=[],
        required_clarifications=[
            "Follow-up channel and message content",
            "Definition of 'important lead'",
            "Action or schedule to ensure leads are not forgotten",
            "Target system of record for customer records",
        ],
        forbidden_assumptions=[
            "Arbitrarily choosing follow-up channel without asking",
            "Hallucinating criteria for important leads",
            "Ignoring the 'don't get forgotten' requirement completely",
        ],
        minimum_nodes_count=0,
    ),
}
