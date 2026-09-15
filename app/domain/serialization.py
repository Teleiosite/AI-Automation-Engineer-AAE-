"""Pure standard-library domain serialization utilities."""

import dataclasses
from datetime import datetime
from enum import Enum
from typing import Any, Dict
from uuid import UUID


def serialize_domain_object(obj: Any) -> Any:
    """
    Recursively serialize domain objects, dataclasses, enums, UUIDs,
    and datetimes to clean JSON-compatible primitives without secret leakage.
    """
    sensitive_keys = {"password", "secret", "token", "api_key", "auth", "credential", "private_key"}

    if isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif dataclasses.is_dataclass(obj):
        res: Dict[str, Any] = {}
        for f in dataclasses.fields(obj):
            val = getattr(obj, f.name)
            if any(s in f.name.lower() for s in sensitive_keys):
                res[f.name] = "********"
            else:
                res[f.name] = serialize_domain_object(val)
        return res
    elif isinstance(obj, dict):
        res_dict = {}
        for k, v in obj.items():
            if any(s in str(k).lower() for s in sensitive_keys):
                res_dict[k] = "********"
            else:
                res_dict[k] = serialize_domain_object(v)
        return res_dict
    elif isinstance(obj, (list, tuple, set)):
        return [serialize_domain_object(item) for item in obj]
    else:
        return obj
