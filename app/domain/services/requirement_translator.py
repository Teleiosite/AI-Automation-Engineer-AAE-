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
    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
        re.compile(r"bypass\s+security(\s+policy)?", re.IGNORECASE),
        re.compile(r"admin\s+override", re.IGNORECASE),
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
        (re.compile(r"\b(new\s+(row|record|lead|customer|entry))\b", re.IGNORECASE), "New record event"),
        (re.compile(r"\b(when|whenever)\s+(someone|somebody|a\s+user|a\s+customer)\s+submits?\b", re.IGNORECASE), "User form submission"),
        (re.compile(r"\b(email\s+received|incoming\s+email|when\s+email\s+arrives)\b", re.IGNORECASE), "Incoming email trigger"),
        (re.compile(r"\b(incoming\s+message|when\s+whatsapp\s+received)\b", re.IGNORECASE), "Incoming message trigger"),
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
        (re.compile(r"\b(rest\s+api|external\s+api|api)\b", re.IGNORECASE), "REST API"),
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

        # Save/Store action
        if re.search(r"\b(save|store|insert|record|write)\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Persist incoming record to data store",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.MEDIUM if not has_destructive else RiskLevel.HIGH,
                )
            )

        # Send/Notify action
        if re.search(r"\b(send|notify|message|alert|email|whatsapp)\b", lower_text):
            req.add_item(
                RequirementItem(
                    type=RequirementType.ACTION,
                    description="Dispatch outbound notification/message",
                    confidence=ConfidenceLevel.EXPLICIT,
                    risk=RiskLevel.MEDIUM,
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
        if re.search(r"\bretr(y|ies)\b", lower_text):
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
        if any(w in lower_text for w in ["phone", "email", "customer", "lead", "details"]):
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

        # Ambiguity 3: Database mentioned without target table
        if re.search(r"\b(database|postgresql|postgres|mysql|sqlite)\b", lower_text):
            if not re.search(r"\b(table\s+\w+|\w+_table|leads?|customers?|contacts?|users?|enquir(y|ies))\b", lower_text):
                ambiguity = "Database destination table unspecified: Target table or schema name is not provided."
                req.add_ambiguity(ambiguity)

        # Ambiguity 4: Untestable vague quality terms
        if re.search(r"\b(make\s+it\s+(reliable|fast|robust|good)|handle\s+everything)\b", lower_text):
            req.add_ambiguity("Vague non-functional requirement: Qualities like 'reliable' or 'fast' must be translated into measurable criteria.")

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
