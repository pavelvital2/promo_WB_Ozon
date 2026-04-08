from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class RunFileViewModel:
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


@dataclass(slots=True, frozen=True)
class RunPollingViewModel:
    id: int
    public_run_number: str
    store_id: int
    operation_type: str
    lifecycle_status: str
    execution_phase: str
    business_result: str | None
    module_code: str
    short_result_text: str | None
    result_file_id: int | None
    result_file_is_available: bool | None
    result_file_unavailable_reason: str | None
    is_locked: bool
    updated_at_utc: datetime


@dataclass(slots=True, frozen=True)
class RunPageViewModel:
    run: RunPollingViewModel
    summary_audit_json: dict[str, object] | None
    detail_row_count: int
    files: tuple[RunFileViewModel, ...]
