"""Structured JSON logging with correlation IDs and automatic secret redaction."""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

# Context variable for tracking request correlation IDs
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# Patterns that match sensitive information for redaction
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*['\"]?)([^'\"\s&]+)(['\"]?)"),
    re.compile(r"(?i)(password\s*[:=]\s*['\"]?)([^'\"\s&]+)(['\"]?)"),
    re.compile(r"(?i)(secret\s*[:=]\s*['\"]?)([^'\"\s&]+)(['\"]?)"),
    re.compile(r"(?i)(token\s*[:=]\s*['\"]?)([^'\"\s&]+)(['\"]?)"),
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9\-._~+/]+=*)"),
    re.compile(r"(://[^:]+:)([^@]+)(@)"),  # database passwords in URLs
]


def redact_secrets(text: str) -> str:
    """Redact sensitive patterns in text."""
    if not isinstance(text, str):
        return text

    sanitized = text
    for pattern in SENSITIVE_PATTERNS:
        # Match pattern with 3 groups (e.g. key=val)
        if pattern.groups == 3:
            sanitized = pattern.sub(r"\g<1>********\g<3>", sanitized)
        elif pattern.groups == 2:
            sanitized = pattern.sub(r"\g<1>********", sanitized)
    return sanitized


class JSONLogFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        cid = correlation_id_ctx.get()
        raw_message = record.getMessage()
        sanitized_message = redact_secrets(raw_message)

        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitized_message,
            "correlation_id": cid,
            "module": record.module,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = redact_secrets(self.formatException(record.exc_info))

        # Include custom extra fields if present
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            # Recursively redact extra data
            safe_extra = {}
            for k, v in record.extra_data.items():
                if any(sec in k.lower() for sec in ("key", "secret", "password", "token")):
                    safe_extra[k] = "********"
                elif isinstance(v, str):
                    safe_extra[k] = redact_secrets(v)
                else:
                    safe_extra[k] = v
            log_data["extra"] = safe_extra

        return json.dumps(log_data)


class TextLogFormatter(logging.Formatter):
    """Formats log records as sanitized plain text."""

    def format(self, record: logging.LogRecord) -> str:
        cid = correlation_id_ctx.get()
        cid_str = f" [{cid}]" if cid else ""
        raw_message = record.getMessage()
        sanitized_message = redact_secrets(raw_message)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"{timestamp} [{record.levelname}]{cid_str} {record.name}: {sanitized_message}"
        if record.exc_info:
            formatted += "\n" + redact_secrets(self.formatException(record.exc_info))
        return formatted


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure root logger with the specified level and formatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to prevent duplicate logs
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    if log_format.lower() == "json":
        stream_handler.setFormatter(JSONLogFormatter())
    else:
        stream_handler.setFormatter(TextLogFormatter())

    root_logger.addHandler(stream_handler)
