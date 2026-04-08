from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class RunDTO:
    id: int
    public_run_number: str
    store_id: int
    initiated_by_user_id: int
    operation_type: str
    lifecycle_status: str
    business_result: str | None
    module_code: str
    input_set_signature: str
    started_at_utc: datetime
    finished_at_utc: datetime | None
    short_result_text: str | None
    result_file_id: int | None
    validation_was_auto_before_process: bool
    created_at_utc: datetime
    updated_at_utc: datetime


@dataclass(slots=True, frozen=True)
class RunFileDTO:
    id: int
    run_id: int
    file_role: str
    original_filename: str
    stored_filename: str
    storage_relative_path: str
    mime_type: str
    file_size_bytes: int
    file_sha256: str
    uploaded_at_utc: datetime
    expires_at_utc: datetime | None
    is_available: bool
    unavailable_reason: str | None
    created_at_utc: datetime

