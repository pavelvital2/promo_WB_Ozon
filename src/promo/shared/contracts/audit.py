from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class RunSummaryAuditDTO:
    id: int
    run_id: int
    audit_json: dict[str, object]
    created_at_utc: datetime


@dataclass(slots=True, frozen=True)
class RunDetailAuditDTO:
    id: int
    run_id: int
    row_number: int
    entity_key_1: str | None
    entity_key_2: str | None
    severity: str
    decision_reason: str | None
    message: str
    audit_payload_json: dict[str, object]
    created_at_utc: datetime

