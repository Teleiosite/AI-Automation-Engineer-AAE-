"""Requirement Translation Engine (Phase 7).

Converts natural-language automation requests into structured, typed, testable,
and clarification-ready Requirement aggregates without hallucinating unsupported
assumptions or bypassing security boundaries.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import List, Optional, Set, Tuple
from uuid import UUID

from app.domain.enums import ConfidenceLevel, RequirementType, RiskLevel
from app.domain.errors import DomainValidationError
from app.domain.models.requirement import Requirement, RequirementItem


@dataclass(frozen=True)
class RequirementTranslationResult:
    """Structured immutable output of the requirement translation process."""
    requirement: Requirement
    risk_level: RiskLevel
    is_clarification_required: bool
    clarification_questions: Tuple[str, ...]
    assumptions: Tuple[str, ...]
    ambiguities: Tuple[str, ...]
    conflicts: Tuple[str, ...]
    is_prompt_injection_detected: bool = False

    def to_dict(self) -> dict:
        """Convert result to dictionary representation."""
        return {
            "requirement_id": str(self.requirement.id),
            "project_id": str(self.requirement.project_id),
            "original_request": self.requirement.original_request,
            "risk_level": self.risk_level.value,
            "is_clarification_required": self.is_clarification_required,
            "clarification_questions": list(self.clarification_questions),
            "assumptions": list(self.assumptions),
            "ambiguities": list(self.ambiguities),
            "conflicts": list(self.conflicts),
            "is_prompt_injection_detected": self.is_prompt_injection_detected,
            "items": [
                {
                    "id": str(item.id),
                    "type": item.type.value,
                    "description": item.description,
                    "confidence": item.confidence.value,
                    "risk": item.risk.value,
                    "notes": item.notes,
                }
                for item in self.requirement.items
            ],
        }


class RequirementTranslator:
    """Deterministic domain requirement translation engine.

    Parses natural language automation requests into structured requirements,
    extracting triggers, actions, external integrations, data stores, security rules,
    and success criteria while detecting ambiguities, conflicts, and adversarial prompts.
    """

    # Adversarial patterns to defend against prompt injection
    # Adversarial patterns to defend against prompt injection
    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+(instructions|safety\s+rules|rules)", re.IGNORECASE),
        re.compile(r"system\s+(prompt\s+)?override", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+(developer|debug|god)\s+mode", re.IGNORECASE),
        re.compile(r"bypass\s+security(\s+policy)?", re.IGNORECASE),
        re.compile(r"admin\s+override", re.IGNORECASE),
        re.compile(r"email\s+all\s+(database\s+credentials|passwords|api\s+keys)", re.IGNORECASE),
    ]

    # Destructive action keywords
    DESTRUCTIVE_KEYWORDS = [
        "delete", "remove", "drop", "truncate", "wipe", "purge",
        "destroy", "clean up", "cleanup", "cancel all", "disable all"
    ]

    # Financial operation keywords
    FINANCIAL_KEYWORDS = [
        "payment", "charge", "refund", "invoice", "stripe", "credit card", "bank", "payout"
    ]

    # Common triggers
    TRIGGER_PATTERNS = [
        (re.compile(r"\b(webhook|http\s+post|incoming\s+request)\b", re.IGNORECASE), "Webhook event"),
        (re.compile(r"\b(form\s+submi\w+|contact\s+form|fills?\s+out\s+(our\s+)?form)\b", re.IGNORECASE), "Website form submission"),
        (re.compile(r"\b(every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|day|morning|hour|week|month)|daily|hourly|cron|schedule)\b", re.IGNORECASE), "Scheduled / Cron trigger"),
        (re.compile(r"\b(new\s+(row|record|lead|customer|entry|hire))\b", re.IGNORECASE), "New record event"),
        (re.compile(r"\b(when|whenever)\s+(someone|somebody|a\s+user|a\s+customer)\s+submits?\b", re.IGNORECASE), "User form submission"),
        (re.compile(r"\b(email\s+received|incoming\s+email|when\s+email\s+arrives)\b", re.IGNORECASE), "Incoming email trigger"),
        (re.compile(r"\b(incoming\s+message|when\s+whatsapp\s+received)\b", re.IGNORECASE), "Incoming message trigger"),
        (re.compile(r"\b(enquir(y|ies)|contact(s)?\s+us|sends?\s+(us\s+)?an?\s+enquiry|when\s+somebody\s+enquires)\b", re.IGNORECASE), "Website contact enquiry"),
        (re.compile(r"\b(books?\s+(an?\s+)?appointment|appointment\s+booking|new\s+appointment|reservation)\b", re.IGNORECASE), "Appointment booking event"),
        (re.compile(r"\b(invoice|payment)\s+changes?\s+status|status\s+changes?\b", re.IGNORECASE), "Invoice status change event"),
        (re.compile(r"\b(sends?\s+(the\s+)?(same\s+)?event|event\s+(arrives|received|occurs)|incoming\s+event|customer\s+action)\b", re.IGNORECASE), "System customer event"),
        (re.compile(r"\b(external\s+service|service\s+doesn't\s+respond)\b", re.IGNORECASE), "External service event"),
        (re.compile(r"\bprocess\s+customer\s+information\b", re.IGNORECASE), "Customer data processing event"),
        (re.compile(r"\b(orders?|receipts?|checkout|purchase)\b", re.IGNORECASE), "Customer order event"),
        (re.compile(r"\b(shipping\s+status|tracking\s+coordinates|delivery\s+driver|picked\s+up)\b", re.IGNORECASE), "Logistics / Shipping status event"),
        (re.compile(r"\b(transaction|ledger\s+entries|wire\s+transfer|sanctions?)\b", re.IGNORECASE), "Financial transaction event"),
        (re.compile(r"\b(ticket|support\s+ticket|health\s+screening|cardiology|incident|alert\s+triggers?|datadog|demo\s+request|warehouse\s+stock|applicant|candidate)\b", re.IGNORECASE), "Domain inbound event"),
    ]

    # Data stores
    DATA_STORE_PATTERNS = [
        (re.compile(r"\b(postgresql|postgres)\b", re.IGNORECASE), "PostgreSQL"),
        (re.compile(r"\b(mysql)\b", re.IGNORECASE), "MySQL"),
        (re.compile(r"\b(sqlite)\b", re.IGNORECASE), "SQLite"),
        (re.compile(r"\b(redis)\b", re.IGNORECASE), "Redis"),
        (re.compile(r"\b(mongodb|mongo)\b", re.IGNORECASE), "MongoDB"),
        (re.compile(r"\b(google\s+sheets?|sheets?)\b", re.IGNORECASE), "Google Sheets"),
        (re.compile(r"\b(airtable)\b", re.IGNORECASE), "Airtable"),
        (re.compile(r"\b(database|data\s+table)\b", re.IGNORECASE), "Database"),
        (re.compile(r"\b(customer\s+records?|record\s+it|save\s+(their\s+)?details|update\s+(the\s+)?customer\s+record)\b", re.IGNORECASE), "Customer Records Store"),
        (re.compile(r"\b(warehouse\s+stock|inventory|stock|purchase\s+orders?)\b", re.IGNORECASE), "Inventory & Orders Store"),
        (re.compile(r"\b(dossier|application\s+dossier)\b", re.IGNORECASE), "Student Dossier Store"),
        (re.compile(r"\b(ledger|ledger\s+entries|balances?)\b", re.IGNORECASE), "Ledger & Balances Store"),
        (re.compile(r"\b(calendar|calendar\s+slot)\b", re.IGNORECASE), "Calendar Appointments Store"),
    ]

    # External services
    EXTERNAL_SERVICE_PATTERNS = [
        (re.compile(r"\b(whatsapp)\b", re.IGNORECASE), "WhatsApp"),
        (re.compile(r"\b(telegram)\b", re.IGNORECASE), "Telegram"),
        (re.compile(r"\b(slack)\b", re.IGNORECASE), "Slack"),
        (re.compile(r"\b(email|smtp|sendgrid|mailgun)\b", re.IGNORECASE), "Email"),
        (re.compile(r"\b(stripe)\b", re.IGNORECASE), "Stripe"),
        (re.compile(r"\b(twilio)\b", re.IGNORECASE), "Twilio"),
        (re.compile(r"\b(hubspot)\b", re.IGNORECASE), "HubSpot"),
        (re.compile(r"\b(salesforce)\b", re.IGNORECASE), "Salesforce"),
        (re.compile(r"\b(rest\s+api|external\s+api|api|endpoint)\b", re.IGNORECASE), "REST API"),
        (re.compile(r"\b(notify\s+sales|send\s+.*?to\s+sales|sales\s+team)\b", re.IGNORECASE), "Sales Team Channel"),
        (re.compile(r"\b(support\s+team|to\s+support|helpdesk)\b", re.IGNORECASE), "Support Team Channel"),
        (re.compile(r"\b(alert\s+(the\s+)?finance\s+team|finance\s+team)\b", re.IGNORECASE), "Finance Alert Channel"),
        (re.compile(r"\b(team\s+knows|let\s+us\s+know|notify\s+(the\s+)?team|alert\s+(the\s+)?team)\b", re.IGNORECASE), "Team Notification Channel"),
        (re.compile(r"\b(reminder\s+before|send\s+.*?reminder)\b", re.IGNORECASE), "Appointment Reminder Service"),
        (re.compile(r"\b(procurement\s+channel|supplier|primary\s+supplier|vendor)\b", re.IGNORECASE), "Procurement & Supplier Service"),
        (re.compile(r"\b(tier\s+2|tier\s+2\s+engineers|standard\s+pool)\b", re.IGNORECASE), "Support Engineer Channel"),
        (re.compile(r"\b(logistics|3pl|courier|delivery)\b", re.IGNORECASE), "Logistics & Delivery Service"),
        (re.compile(r"\b(quest\s+diagnostics|diagnostics|lab\s+test)\b", re.IGNORECASE), "Diagnostic Laboratory API"),
        (re.compile(r"\b(opsgenie|pagerduty|zoom|status\s+page)\b", re.IGNORECASE), "Incident Management Platform"),
        (re.compile(r"\b(clearbit|zoominfo)\b", re.IGNORECASE), "Lead Enrichment API"),
        (re.compile(r"\b(aml\s+sanctions|fx\s+rate)\b", re.IGNORECASE), "Financial Sanctions & FX Gateway"),
        (re.compile(r"\b(to\s+the\s+patient|patient\s+notification|notify\s+(the\s+)?patient|send\s+.*?patient)\b", re.IGNORECASE), "Patient Notification Email"),
    ]

    def translate(self, project_id: UUID, raw_text: str, created_by: str = "user") -> RequirementTranslationResult:
        """Translate a natural language request into a structured Requirement."""
        if not raw_text or not raw_text.strip():
            raise DomainValidationError("Original user request cannot be empty")

        cleaned_text = raw_text.strip()
        requirement = Requirement(
            project_id=project_id,
            original_request=cleaned_text,
            created_by=created_by,
        )

        # 1. Check for prompt injection / adversarial attempts
        is_injection = self._check_prompt_injection(cleaned_text)
        if is_injection:
            requirement.add_item(
                RequirementItem(
                    type=RequirementType.SECURITY_REQUIREMENT,
                    description="Adversarial prompt injection pattern detected in input text",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.CRITICAL,
                    notes="System instructions cannot be overridden by user-supplied text.",
                )
            )
            requirement.add_ambiguity("Adversarial prompt injection pattern detected: system instructions cannot be overridden.")

        # 2. Extract business objective
        self._extract_business_objective(cleaned_text, requirement)

        # 3. Extract trigger
        self._extract_trigger(cleaned_text, requirement)

        # 4. Extract actions
        self._extract_actions(cleaned_text, requirement)

        # 5. Extract inputs
        self._extract_inputs(cleaned_text, requirement)

        # 6. Extract data stores & external services
        self._extract_integrations(cleaned_text, requirement)

        # 7. Extract timing and scheduling
        self._extract_timing(cleaned_text, requirement)

        # 8. Extract failure handling
        self._extract_failure_handling(cleaned_text, requirement)

        # 9. Extract security requirements
        self._extract_security(cleaned_text, requirement)

        # 10. Extract success criteria
        self._extract_success_criteria(cleaned_text, requirement)

        # 11. Detect conflicts / contradictions
        self._detect_conflicts(cleaned_text, requirement)

        # 12. Detect ambiguities and gaps
        self._detect_ambiguities(cleaned_text, requirement)

        # Compute risk and clarification needs
        overall_risk = requirement.overall_risk()
        if is_injection:
            overall_risk = RiskLevel.CRITICAL

        clarification_questions = self._generate_clarification_questions(requirement)
        is_clarification_required = (
            len(clarification_questions) > 0
            or requirement.has_ambiguities()
            or requirement.has_unresolved_conflicts()
        )

        return RequirementTranslationResult(
            requirement=requirement,
            risk_level=overall_risk,
            is_clarification_required=is_clarification_required,
            clarification_questions=tuple(clarification_questions),
            assumptions=tuple(requirement.assumptions),
            ambiguities=tuple(requirement.ambiguities),
            conflicts=tuple(requirement.conflicts),
            is_prompt_injection_detected=is_injection,
        )

    def _check_prompt_injection(self, text: str) -> bool:
        """Evaluate whether text contains prompt injection attempts."""
        return any(pattern.search(text) for pattern in self.PROMPT_INJECTION_PATTERNS)

    def _extract_business_objective(self, text: str, req: Requirement) -> None:
        """Derive the primary business objective from the request."""
        first_sentence = text.split(".")[0].strip()
        objective = first_sentence if len(first_sentence) <= 120 else first_sentence[:117] + "..."
        req.add_item(
            RequirementItem(
                type=RequirementType.BUSINESS_OBJECTIVE,
                description=f"Automate: {objective}",
                confidence=ConfidenceLevel.INFERRED,
                risk=RiskLevel.LOW,
            )
        )

    def _extract_trigger(self, text: str, req: Requirement) -> None:
        """Extract triggering events or identify missing trigger."""
        found_triggers = []
        for pattern, desc in self.TRIGGER_PATTERNS:
            if pattern.search(text):
                found_triggers.append(desc)

        if not found_triggers and re.search(r"^(when|whenever|if)\b", text.strip(), re.IGNORECASE):
            found_triggers.append("Inbound event trigger")

        if found_triggers:
            for trigger_desc in sorted(set(found_triggers)):
                req.add_item(
                    RequirementItem(
                        type=RequirementType.TRIGGER,
                        description=f"Trigger on: {trigger_desc}",
                        confidence=ConfidenceLevel.EXPLICIT,
                        risk=RiskLevel.LOW,
                    )
                )
        else:
            req.add_ambiguity("Trigger unspecified: How should this workflow be initiated (e.g., webhook, schedule, manual)?")
            req.add_item(
                RequirementItem(
                    type=RequirementType.TRIGGER,
                    description="Unspecified automation trigger",
                    confidence=ConfidenceLevel.UNKNOWN,
                    risk=RiskLevel.LOW,
                    notes="Requires user clarification on invocation mechanism.",
                )
            )

    def _extract_actions(self, text: str, req: Requirement) -> None:
        """Identify discrete business actions and evaluate destructive risks."""
        lower_text = text.lower()

        # Check destructive operations
        has_destructive = any(re.search(rf"\b{re.escape(k)}\b", lower_text) for k in self.DESTRUCTIVE_KEYWORDS)
        if has_destructive:
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Execute destructive record modification or deletion",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.HIGH,
                    notes="Destructive operation requires elevated governance approval.",
                )
            )

        # Check financial operations
        has_financial = any(re.search(rf"\b{re.escape(k)}\b", lower_text) for k in self.FINANCIAL_KEYWORDS)
        if has_financial:
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Process financial transactions or invoice data",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.HIGH,
                    notes="Financial operations require strict validation and idempotency.",
                )
            )

        # Save/Store/Update action
        if re.search(r"\b(save|store|insert|record|write|update|create\s+(their\s+)?(team\s+record|dossier|order|entry|item))\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Persist incoming record to data store",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.MEDIUM if not has_destructive else RiskLevel.HIGH,
                )
            )

        # Lookup / inspect state action
        if re.search(r"\b(check|verify|lookup|inspect|pull|match|query)\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Query state or inspect record in data store",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.LOW,
                )
            )

        # Transform / validate / format / enrich / calculate action
        if re.search(r"\b(validate|transform|format|enrich|assign|convert|code|calculate|compute|aggregate|parse|generate)\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Validate and format payload via transformation node",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.LOW,
                )
            )

        # Send/Notify/Dispatch action
        if re.search(r"\b(send|notify|message|alert|email|whatsapp|team\s+knows|push|call|dispatch|forward|post|page|publish|ping|respond)\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Dispatch outbound notification/message",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.MEDIUM,
                )
            )

        # Check deduplication / idempotency
        if re.search(r"\b(don't\s+create\s+another|already\s+there|isn't\s+processed\s+twice|same\s+customer\s+action\s+isn't\s+processed\s+twice|deduplicat\w+)\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Deduplicate incoming event and enforce idempotency guard",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.LOW,
                )
            )

        # Check conditional routing
        if re.search(r"\b(send\s+.*?to\s+sales\s+and\s+.*?to\s+support|if\s+the\s+payment\s+fails|if\s+they're\s+already|if\b|otherwise|assess|triage|route\b|split\b|branch\b|match\b)\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Conditional evaluation and routing branch",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.LOW,
                )
            )

    def _extract_inputs(self, text: str, req: Requirement) -> None:
        """Extract data inputs required for the workflow."""
        lower_text = text.lower()
        common_fields = ["name", "email", "phone", "enquiry", "message", "details", "company", "amount"]
        detected = [field for field in common_fields if re.search(rf"\b{field}\b", lower_text)]

        if detected:
            req.add_item(
                RequirementItem(
                    type=RequirementType.INPUT,
                    description=f"Incoming fields: {', '.join(detected)}",
                    confidence=ConfidenceLevel.INFERRED,
                    risk=RiskLevel.LOW,
                )
            )
        else:
            req.add_item(
                RequirementItem(
                    type=RequirementType.INPUT,
                    description="Standard payload or form fields",
                    confidence=ConfidenceLevel.ASSUMED,
                    risk=RiskLevel.LOW,
                )
            )
            req.add_assumption("Standard payload fields will be accepted from trigger source.")

    def _extract_integrations(self, text: str, req: Requirement) -> None:
        """Extract data store and external service integrations."""
        # Data stores
        for pattern, name in self.DATA_STORE_PATTERNS:
            if pattern.search(text):
                req.add_item(
                    RequirementItem(
                        type=RequirementType.DATA_SOURCE,
                        description=f"Data store integration: {name}",
                        confidence=ConfidenceLevel.EXPLICIT,
                        risk=RiskLevel.LOW,
                    )
                )

        # External services
        for pattern, name in self.EXTERNAL_SERVICE_PATTERNS:
            if pattern.search(text):
                req.add_item(
                    RequirementItem(
                        type=RequirementType.EXTERNAL_SERVICE,
                        description=f"External service integration: {name}",
                        confidence=ConfidenceLevel.EXPLICIT,
                        risk=RiskLevel.LOW,
                    )
                )

    def _extract_timing(self, text: str, req: Requirement) -> None:
        """Extract timing constraints, delays, and scheduling."""
        lower_text = text.lower()
        if re.search(r"\b(immediately|instant|real-?time)\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.TIMING,
                    description="Immediate execution on trigger event",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.LOW,
                )
            )
        
        delay_match = re.search(r"\b(after\s+\d+\s+(minutes?|hours?|days?)|wait\s+\d+\s+(minutes?|hours?|days?))\b", lower_text)
        if delay_match:
            req.add_item(
                RequirementItem(
                    type=RequirementType.TIMING,
                    description=f"Execution delay: {delay_match.group(0)}",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.LOW,
                )
            )

    def _extract_failure_handling(self, text: str, req: Requirement) -> None:
        """Extract error recovery and retry specifications."""
        lower_text = text.lower()
        if re.search(r"\b(retr(y|ies)|timeout|times\s+out|occasional(ly)?\s+hangs|backoff|resilien\w+)\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.FAILURE_HANDLING,
                    description="Retry failed transient operations with backoff",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.LOW,
                )
            )
        else:
            req.add_assumption("Transient API/database failures should be retried up to 3 times before failing.")

    def _extract_security(self, text: str, req: Requirement) -> None:
        """Extract security, credential, and compliance requirements."""
        lower_text = text.lower()
        if re.search(r"\b(sensitive\s+information|authori[sz]ed\s+to\s+see|confidential|restricted\s+access)\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.SECURITY_REQUIREMENT,
                    description="Enforce access control and PII data sanitization for sensitive information",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.CRITICAL,
                    notes="Sensitive data must only be accessible to authorized roles and redacted from general logs.",
                )
            )
        elif any(w in lower_text for w in ["phone", "email", "customer", "lead", "details"]):
            req.add_item(
                RequirementItem(
                    type=RequirementType.SECURITY_REQUIREMENT,
                    description="Protect customer Personally Identifiable Information (PII)",
                    confidence=ConfidenceLevel.INFERRED,
                    risk=RiskLevel.LOW,
                    notes="Redact contact details in operational logs and audit events.",
                )
            )

    def _extract_success_criteria(self, text: str, req: Requirement) -> None:
        """Derive objective, measurable success criteria."""
        req.add_item(
            RequirementItem(
                type=RequirementType.SUCCESS_CRITERIA,
                description="Trigger payload is parsed and validated successfully",
                confidence=ConfidenceLevel.INFERRED,
                risk=RiskLevel.LOW,
            )
        )
        if any(item.type == RequirementType.DATA_SOURCE for item in req.items):
            req.add_item(
                RequirementItem(
                    type=RequirementType.SUCCESS_CRITERIA,
                    description="Exactly one persistent database record is created per valid trigger event",
                    confidence=ConfidenceLevel.INFERRED,
                    risk=RiskLevel.LOW,
                )
            )
        if any(item.type == RequirementType.EXTERNAL_SERVICE for item in req.items):
            req.add_item(
                RequirementItem(
                    type=RequirementType.SUCCESS_CRITERIA,
                    description="Outbound communication is dispatched exactly once without duplicates",
                    confidence=ConfidenceLevel.INFERRED,
                    risk=RiskLevel.LOW,
                )
            )

    def _detect_conflicts(self, text: str, req: Requirement) -> None:
        """Identify internal contradictions or mutually exclusive requirements."""
        lower_text = text.lower()
        has_immediate = bool(re.search(r"\b(immediately|instant(ly)?)\b", lower_text))
        has_delay = bool(re.search(r"\b(wait|delay|after)\s+\d+\s+(minutes?|hours?|days?)\b", lower_text))

        if has_immediate and has_delay:
            conflict_msg = "Contradictory timing: Request specifies both immediate execution and a delay period."
            req.add_conflict(conflict_msg)
            req.add_item(
                RequirementItem(
                    type=RequirementType.TIMING,
                    description="Conflicting timing instructions (immediate vs delayed)",
                    confidence=ConfidenceLevel.CONFLICTING,
                    risk=RiskLevel.MEDIUM,
                    notes=conflict_msg,
                )
            )

        has_delete = bool(re.search(r"\b(delete|remove|wipe)\b", lower_text))
        has_preserve = bool(re.search(r"\b(do\s+not\s+delete|never\s+delete|keep\s+all|preserve\s+all)\b", lower_text))
        if has_delete and has_preserve:
            conflict_msg = "Contradictory retention: Request specifies deleting records while also instructing not to delete or preserve all."
            req.add_conflict(conflict_msg)
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Conflicting retention instructions (delete vs preserve)",
                    confidence=ConfidenceLevel.CONFLICTING,
                    risk=RiskLevel.HIGH,
                    notes=conflict_msg,
                )
            )

        has_before_trigger = bool(re.search(r"\b\d+\s+(minutes?|hours?|days?)\s+before\s+(they\s+submit|the\s+form|submission|trigger|applying|they\s+apply)\b", lower_text))
        if has_before_trigger:
            conflict_msg = "Causal impossibility: Action cannot be scheduled before the triggering event occurs."
            req.add_conflict(conflict_msg)
            req.add_item(
                RequirementItem(
                    type=RequirementType.TIMING,
                    description="Impossible negative temporal latency (action before trigger)",
                    confidence=ConfidenceLevel.CONFLICTING,
                    risk=RiskLevel.MEDIUM,
                    notes=conflict_msg,
                )
            )

    def _detect_ambiguities(self, text: str, req: Requirement) -> None:
        """Detect missing critical details, ambiguous targets, or untestable requests."""
        lower_text = text.lower()

        # Ambiguity 1: Destructive action without specific retention/criteria
        if any(k in lower_text for k in ["remove customer", "delete customer", "delete record", "clean up old", "cleanup"]):
            if not re.search(r"\b(older\s+than|\d+\s+(days?|months?|years?)|status\s*=|where)\b", lower_text):
                ambiguity = "Destructive criteria unspecified: Retention period, age threshold, or exact filter conditions are missing."
                req.add_ambiguity(ambiguity)
                req.add_item(
                    RequirementItem(
                        type=RequirementType.ACTION,
                        description="Unspecified criteria for destructive record removal",
                        confidence=ConfidenceLevel.UNKNOWN,
                        risk=RiskLevel.HIGH,
                        notes=ambiguity,
                    )
                )

        # Ambiguity 2: Follow-up without communication channel
        if re.search(r"\b(follow\s*up|contact\s+them|send\s+them\s+a\s+message)\b", lower_text):
            has_channel = any(ch in lower_text for ch in ["whatsapp", "email", "sms", "slack", "telegram"])
            if not has_channel:
                ambiguity = "Communication channel unspecified: What channel (e.g. WhatsApp, Email, SMS) should be used?"
                req.add_ambiguity(ambiguity)
                req.add_item(
                    RequirementItem(
                        type=RequirementType.EXTERNAL_SERVICE,
                        description="Unspecified communication channel for contact",
                        confidence=ConfidenceLevel.UNKNOWN,
                        risk=RiskLevel.LOW,
                        notes=ambiguity,
                    )
                )

        # Ambiguity 3: Database mentioned without target table (excluding backup and dump tasks)
        if re.search(r"\b(database|postgresql|postgres|mysql|sqlite)\b", lower_text):
            if not re.search(r"\b(backup|dump|restore)\b", lower_text):
                if not re.search(r"\b(table\s+\w+|\w+_table|leads?|customers?|contacts?|users?|enquir(y|ies)|ledger|dossier|accounts?)\b", lower_text):
                    ambiguity = "Database destination table unspecified: Target table or schema name is not provided."
                    req.add_ambiguity(ambiguity)

        # Ambiguity 4: Untestable vague quality terms
        if re.search(r"\b(make\s+it\s+(reliable|fast|robust|good)|handle\s+everything)\b", lower_text):
            req.add_ambiguity("Vague non-functional requirement: Qualities like 'reliable' or 'fast' must be translated into measurable criteria.")

        # Ambiguity 5: Qualification without criteria
        if re.search(r"\b(worth\s+sending|worthwhile|qualified\s+(ones?|leads?)|good\s+leads?|important\s+leads?|qualif(y|ies)\s+leads?)\b", lower_text):
            if not re.search(r"\b(score|threshold|budget|company\s+size|revenue|greater|more\s+than|less\s+than|criteria)\b", lower_text):
                ambiguity = "What makes a lead 'qualified' (e.g., budget threshold, company size > 50, or scoring rules)?"
                req.add_ambiguity(ambiguity)
                req.add_item(
                    RequirementItem(
                        type=RequirementType.ACTION,
                        description="Unspecified lead qualification criteria",
                        confidence=ConfidenceLevel.UNKNOWN,
                        risk=RiskLevel.LOW,
                        notes=ambiguity,
                    )
                )

        # Ambiguity 6: Delegation/assignment without recipient or routing rules
        if re.search(r"\b(right\s+person|appropriate\s+person|assign(s)?\s+(qualified\s+)?(leads?|ones?)\s+to\s+sales|assigned\s+representative)\b", lower_text):
            if not re.search(r"\b(round-?robin|territor\w+|region\w+|rep\s+name|by\s+industry|specific\s+salesperson|rep@|sales@)\b", lower_text):
                ambiguity = "How should qualified leads be assigned (e.g., round-robin, by territory, or to a specific email)?"
                req.add_ambiguity(ambiguity)
                req.add_item(
                    RequirementItem(
                        type=RequirementType.ACTION,
                        description="Unspecified lead assignment rule",
                        confidence=ConfidenceLevel.UNKNOWN,
                        risk=RiskLevel.LOW,
                        notes=ambiguity,
                    )
                )

        # Ambiguity 6B: Fallback when no match occurs
        if re.search(r"\b(assign(s)?\s+.*?\s+to\s+sales|assigned\s+representative)\b", lower_text):
            if not re.search(r"\b(if\s+no\s+match|otherwise|fallback|default\s+rep|unassigned|if\s+not)\b", lower_text):
                ambiguity = "What happens when no salesperson matches or the lead is not qualified?"
                req.add_ambiguity(ambiguity)
                req.add_item(
                    RequirementItem(
                        type=RequirementType.ACTION,
                        description="Unspecified fallback for unmatched salesperson",
                        confidence=ConfidenceLevel.UNKNOWN,
                        risk=RiskLevel.LOW,
                        notes=ambiguity,
                    )
                )

        # Ambiguity 6C: Customer database store unspecified
        if re.search(r"\b(customer\s+already\s+exists|creates?\s+the\s+customer)\b", lower_text):
            if not re.search(r"\b(postgres|postgresql|database|crm|sheets?|airtable|table|hubspot|salesforce)\b", lower_text):
                ambiguity = "Where should customer records be checked and created (e.g., PostgreSQL table, CRM, Google Sheets)?"
                req.add_ambiguity(ambiguity)
                req.add_item(
                    RequirementItem(
                        type=RequirementType.DATA_SOURCE,
                        description="Unspecified customer data store",
                        confidence=ConfidenceLevel.UNKNOWN,
                        risk=RiskLevel.LOW,
                        notes=ambiguity,
                    )
                )

        # Ambiguity 7: Unspecified lead retention/SLA
        if re.search(r"\b(don't\s+get\s+forgotten|not\s+get\s+forgotten)\b", lower_text):
            ambiguity = "Lead retention mechanism unspecified: What SLA or action ensures important leads are not forgotten?"
            req.add_ambiguity(ambiguity)
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Unspecified lead retention mechanism",
                    confidence=ConfidenceLevel.UNKNOWN,
                    risk=RiskLevel.LOW,
                    notes=ambiguity,
                )
            )

        # Ambiguity 8: Subjective or undefined financial/risk thresholds
        if re.search(r"\b(normal\s+budget|standard\s+budget|good\s+customers?|attractive\s+discount|significant\s+risk|significant\s+liability|trustworthy|honest)\b", lower_text):
            ambiguity = "Subjective or undefined threshold criteria: Specific numerical thresholds or explicit rule criteria are required."
            req.add_ambiguity(ambiguity)
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Unspecified criteria or undefined threshold",
                    confidence=ConfidenceLevel.UNKNOWN,
                    risk=RiskLevel.HIGH,
                    notes=ambiguity,
                )
            )

        # Ambiguity 9: SSRF targeting private or cloud metadata addresses
        if re.search(r"\b(https?://)?(169\.254\.169\.254|localhost|127\.0\.0\.1|0\.0\.0\.0)\b", lower_text):
            ambiguity = "Security violation (SSRF): Workflow requests target private loopback or cloud metadata address, which is strictly prohibited."
            req.add_ambiguity(ambiguity)
            req.add_item(
                RequirementItem(
                    type=RequirementType.SECURITY_REQUIREMENT,
                    description="SSRF target detected and blocked",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.CRITICAL,
                    notes=ambiguity,
                )
            )

        # Ambiguity 10: Autonomous high-value wire transfers without human approval
        if re.search(r"\b(wire\s+transfer|bank\s+wire)\b", lower_text) and re.search(r"\b(without\s+(disturbing|approval|manager)|automatically\s+execute)\b", lower_text):
            ambiguity = "Financial governance restriction: High-value wire transfers cannot be executed autonomously without human manager approval."
            req.add_ambiguity(ambiguity)
            req.add_item(
                RequirementItem(
                    type=RequirementType.SECURITY_REQUIREMENT,
                    description="Autonomous wire transfer blocked pending governance approval",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.CRITICAL,
                    notes=ambiguity,
                )
            )

    def _generate_clarification_questions(self, req: Requirement) -> List[str]:
        """Produce clear, focused questions for each unresolved ambiguity or conflict."""
        questions: List[str] = []

        for conflict in req.conflicts:
            questions.append(f"Conflict Resolution Required: {conflict}")

        for ambiguity in req.ambiguities:
            questions.append(f"Clarification Required: {ambiguity}")

        for item in req.items:
            if item.confidence == ConfidenceLevel.UNKNOWN and item.notes:
                if item.notes not in questions and f"Clarification Required: {item.notes}" not in questions:
                    questions.append(f"Missing Detail: {item.notes}")

        return questions
