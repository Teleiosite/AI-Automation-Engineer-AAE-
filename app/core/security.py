"""Security utilities for credential masking, redaction, and sanitization."""

from typing import Any, Dict


def mask_secret(value: str, prefix_len: int = 0, suffix_len: int = 0) -> str:
    """Mask a sensitive string with asterisks."""
    if not value:
        return ""
    if len(value) <= (prefix_len + suffix_len):
        return "********"
    prefix = value[:prefix_len] if prefix_len > 0 else ""
    suffix = value[-suffix_len:] if suffix_len > 0 else ""
    return f"{prefix}********{suffix}"


def redact_sensitive_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redacts sensitive keys in a dictionary."""
    sensitive_patterns = ("password", "secret", "token", "api_key", "auth", "credential", "private_key")
    redacted = {}
    for k, v in data.items():
        k_lower = k.lower()
        if isinstance(v, dict):
            redacted[k] = redact_sensitive_dict(v)
        elif isinstance(v, list):
            redacted[k] = [
                redact_sensitive_dict(item)
                if isinstance(item, dict)
                else ("********" if any(s in k_lower for s in sensitive_patterns) else item)
                for item in v
            ]
        elif any(s in k_lower for s in sensitive_patterns):
            redacted[k] = "********"
        else:
            redacted[k] = v
    return redacted
