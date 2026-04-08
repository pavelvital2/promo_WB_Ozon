from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class SystemLogDTO:
    id: int
    event_time_utc: datetime
    user_id: int | None
    store_id: int | None
    run_id: int | None
    module_code: str | None
    event_type: str
    severity: str
    message: str
    payload_json: dict[str, object] | None = None

