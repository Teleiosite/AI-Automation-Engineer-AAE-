"""Domain enumerations using Python standard library enum."""

from enum import Enum


class RiskLevel(str, Enum):
    """Exact AAE risk levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConfidenceLevel(str, Enum):
    """Requirement element confidence levels."""
    EXPLICIT = "EXPLICIT"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"


class RequirementType(str, Enum):
    """Extracted requirement classification types."""
    BUSINESS_OBJECTIVE = "BUSINESS_OBJECTIVE"
    TRIGGER = "TRIGGER"
    INPUT = "INPUT"
    ACTION = "ACTION"
    CONDITION = "CONDITION"
    OUTPUT = "OUTPUT"
    DATA_SOURCE = "DATA_SOURCE"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    TIMING = "TIMING"
    FAILURE_HANDLING = "FAILURE_HANDLING"
    SECURITY_REQUIREMENT = "SECURITY_REQUIREMENT"
    SUCCESS_CRITERIA = "SUCCESS_CRITERIA"


class SpecificationStatus(str, Enum):
    """Specification lifecycle status."""
    DRAFT = "DRAFT"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    IMPLEMENTED = "IMPLEMENTED"


class WorkflowStatus(str, Enum):
    """Operational container status in automation provider environment."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class WorkflowVersionStatus(str, Enum):
    """Engineering maturity of a specific workflow revision."""
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    TESTED = "TESTED"
    APPROVED = "APPROVED"
    DEPLOYED = "DEPLOYED"
    SUPERSEDED = "SUPERSEDED"


class ExecutionStatus(str, Enum):
    """Lifecycle status of an execution run."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


class TechnicalStatus(str, Enum):
    """Direct technical execution outcome."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ERROR = "ERROR"


class SemanticStatus(str, Enum):
    """Business/intent satisfaction outcome."""
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    UNKNOWN = "UNKNOWN"


class TriggerType(str, Enum):
    """Execution trigger origin."""
    MANUAL = "MANUAL"
    WEBHOOK = "WEBHOOK"
    SCHEDULE = "SCHEDULE"
    TEST = "TEST"


class ApprovalDecision(str, Enum):
    """Decision recorded for an approval request."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalStatus(str, Enum):
    """Lifecycle status of an approval record."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class ApprovalTargetType(str, Enum):
    """Entity type target of an approval."""
    SPECIFICATION = "SPECIFICATION"
    WORKFLOW_VERSION = "WORKFLOW_VERSION"
    DEPLOYMENT = "DEPLOYMENT"
    REPAIR = "REPAIR"


class DeploymentStatus(str, Enum):
    """Lifecycle status of a deployment."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DEPLOYED = "DEPLOYED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class FailureCategory(str, Enum):
    """Categorization of workflow execution failures."""
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    LOGIC_ERROR = "LOGIC_ERROR"
    DATA_ERROR = "DATA_ERROR"
    INTEGRATION_ERROR = "INTEGRATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    PLATFORM_ERROR = "PLATFORM_ERROR"
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"
    UNKNOWN = "UNKNOWN"


class FailureSeverity(str, Enum):
    """Failure severity level."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AgentState(str, Enum):
    """The 21 lifecycle states of an autonomous AAE engineering task."""
    # Active lifecycle states (17)
    INTAKE = "INTAKE"
    ANALYSING = "ANALYSING"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    SPECIFICATION_READY = "SPECIFICATION_READY"
    PLANNING = "PLANNING"
    BUILDING = "BUILDING"
    VALIDATING = "VALIDATING"
    TESTING = "TESTING"
    FAILED = "FAILED"
    DIAGNOSING = "DIAGNOSING"
    REPAIRING = "REPAIRING"
    RETESTING = "RETESTING"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"
    MONITORING = "MONITORING"

    # Terminal states (4)
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    FAILED_PERMANENTLY = "FAILED_PERMANENTLY"
