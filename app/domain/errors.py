"""Domain exception hierarchy."""


class DomainError(Exception):
    """Base exception for all domain errors."""
    pass


class DomainValidationError(DomainError):
    """Raised when a domain entity or value object fails structural/rule validation."""
    pass


class InvalidStateTransitionError(DomainError):
    """Raised when an illegal lifecycle transition is attempted."""

    def __init__(self, from_state: str, to_state: str, message: str = "") -> None:
        self.from_state = from_state
        self.to_state = to_state
        msg = message or f"Illegal transition from '{from_state}' to '{to_state}'"
        super().__init__(msg)


class ApprovalRequiredError(DomainError):
    """Raised when a gated action lacks required human/policy approval."""
    pass


class StaleApprovalError(DomainError):
    """Raised when an approval is expired, already consumed, superseded, or version-mismatched."""
    pass


class ImmutableArtifactError(DomainError):
    """Raised when an attempt is made to mutate a locked or approved domain artifact."""
    pass


class InvariantViolationError(DomainError):
    """Raised when a business invariant is violated."""
    pass
