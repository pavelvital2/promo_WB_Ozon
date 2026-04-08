from __future__ import annotations

from dataclasses import is_dataclass
from typing import Any

from fastapi.encoders import jsonable_encoder


def to_payload(value: Any) -> Any:
    if is_dataclass(value):
        return jsonable_encoder(value)
    if isinstance(value, tuple):
        return [to_payload(item) for item in value]
    if isinstance(value, list):
        return [to_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: to_payload(item) for key, item in value.items()}
    return jsonable_encoder(value)
