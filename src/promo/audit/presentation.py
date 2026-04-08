from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from promo.runs.presentation import RunFileViewModel, RunPollingViewModel


@dataclass(slots=True, frozen=True)
class DetailAuditRowViewModel:
    id: int
    run_id: int
    row_number: int
    entity_key_1: str | None
    entity_key_2: str | None
    severity: str
    decision_reason: str | None
    message: str
    audit_payload_json: dict[str, object]
    created_at_utc: object


@dataclass(slots=True, frozen=True)
class DetailAuditPageViewModel:
    items: tuple[DetailAuditRowViewModel, ...]
    total_items: int
    page: int
    page_size: int


@dataclass(slots=True, frozen=True)
class RunPageHeaderViewModel:
    run_id: int
    public_run_number: str
    store_id: int
    store_name: str
    marketplace: str
    module_code: str
    initiated_by_user_id: int
    initiated_by_username: str
    operation_type: str
    lifecycle_status: str
    execution_phase: str
    business_result: str | None
    short_result_text: str | None
    started_at_utc: datetime
    finished_at_utc: datetime | None
    updated_at_utc: datetime
    result_file_id: int | None
    result_file_is_available: bool | None
    result_file_unavailable_reason: str | None
    is_locked: bool


@dataclass(slots=True, frozen=True)
class RunPageReadModel:
    run: RunPageHeaderViewModel
    polling: RunPollingViewModel
    summary_audit_json: dict[str, object] | None
    detail_audit: DetailAuditPageViewModel
    files: tuple[RunFileViewModel, ...]
