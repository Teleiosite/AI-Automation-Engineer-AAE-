"""
Synthetic Data Fixtures for AAE Real-World Product Validation Program.
All data is strictly synthetic and generated for testing purposes.
No real PII, credentials, or production tokens are present.
"""

from typing import Any, Dict

# SCENARIO-001: Contact Enquiry
SCENARIO_001_PAYLOAD: Dict[str, Any] = {
    "name": "Jane Doe",
    "email": "jane.doe@synthetic-example.com",
    "company": "Acme Widgets Ltd",
    "message": "We are looking to implement automated inventory notifications across 3 warehouses. Please get in touch.",
}

# SCENARIO-002: New Lead Deduplication
SCENARIO_002_NEW_LEAD: Dict[str, Any] = {
    "lead_id": "lead-synth-1001",
    "name": "Marcus Vance",
    "email": "marcus.vance@techflow-example.io",
    "company": "TechFlow Systems",
    "annual_revenue": 2500000,
}

SCENARIO_002_DUPLICATE_LEAD: Dict[str, Any] = {
    "lead_id": "lead-synth-1002",
    "name": "Marcus Vance",
    "email": "marcus.vance@techflow-example.io",  # Same email identifier
    "company": "TechFlow Systems Inc",
    "annual_revenue": 2500000,
}

# SCENARIO-003: Lead Routing
SCENARIO_003_SALES_PROSPECT: Dict[str, Any] = {
    "name": "Elena Rostova",
    "email": "elena.rostova@enterprise-corp-mock.com",
    "enquiry_type": "sales",
    "budget": 50000,
    "message": "Requesting formal pricing and security review for 500 enterprise seats.",
}

SCENARIO_003_SUPPORT_QUESTION: Dict[str, Any] = {
    "name": "Arthur Pendelton",
    "email": "arthur@smallbiz-demo.org",
    "enquiry_type": "support",
    "budget": 0,
    "message": "How do I reset my account password from the settings dashboard?",
}

# SCENARIO-004: Appointment Booking
SCENARIO_004_BOOKING_PAYLOAD: Dict[str, Any] = {
    "customer_name": "Dr. Aris Thorne",
    "customer_email": "aris.thorne@medtech-demo.edu",
    "appointment_time": "2026-10-15T14:30:00Z",
    "service": "Architecture Design Review",
    "duration_minutes": 60,
}

# SCENARIO-005: Payment Status
SCENARIO_005_PAYMENT_FAILED: Dict[str, Any] = {
    "invoice_id": "inv-2026-9901",
    "customer_id": "cust-8812",
    "status": "failed",
    "amount": 2450.00,
    "currency": "USD",
    "failure_reason": "INSUFFICIENT_FUNDS_OR_CARD_DECLINED",
}

SCENARIO_005_PAYMENT_SUCCESS: Dict[str, Any] = {
    "invoice_id": "inv-2026-9902",
    "customer_id": "cust-8812",
    "status": "paid",
    "amount": 2450.00,
    "currency": "USD",
    "failure_reason": None,
}

# SCENARIO-006: Lead Qualification (Missing Rules)
SCENARIO_006_AMBIGUOUS_LEAD: Dict[str, Any] = {
    "lead_name": "David Kim",
    "email": "david.kim@startup-synthetic.co",
    "company_size": 45,
}

# SCENARIO-007: External API Failure (Resilience / Retry)
SCENARIO_007_API_CALL_PAYLOAD: Dict[str, Any] = {
    "service_url": "https://api.external-unreliable-mock.net/v1/sync",
    "payload": {
        "sync_id": "sync-batch-771",
        "records_count": 150,
    },
    "expected_max_retries": 3,
}

# SCENARIO-008: Duplicate Event (Distributed Event Idempotency)
SCENARIO_008_EVENT_FIRST: Dict[str, Any] = {
    "event_id": "evt-idemp-008-xyz",
    "customer_id": "cust-707",
    "action": "order_placed",
    "timestamp": "2026-09-16T10:00:00Z",
}

SCENARIO_008_EVENT_DUPLICATE: Dict[str, Any] = {
    "event_id": "evt-idemp-008-xyz",  # Duplicate event_id
    "customer_id": "cust-707",
    "action": "order_placed",
    "timestamp": "2026-09-16T10:00:05Z",
}

# SCENARIO-009: Sensitive Information
SCENARIO_009_SENSITIVE_CUSTOMER_DATA: Dict[str, Any] = {
    "customer_id": "cust-sec-909",
    "name": "Sarah Connor",
    "tax_id": "999-00-1234",  # Sensitive PII
    "credit_card_last4": "4242",  # Financial PII
    "notes": "VIP Client - Handle with restricted permissions",
    "public_email": "sarah.connor@cyberdyne-synthetic.com",
}

# SCENARIO-010: Intentionally Ambiguous Request
SCENARIO_010_AMBIGUOUS_CONTACT: Dict[str, Any] = {
    "contact_name": "Anonymous Prospect",
    "message": "Interested in everything you do, please update records and don't forget me.",
}
