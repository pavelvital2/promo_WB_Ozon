from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role_code: str
    permission_codes: tuple[str, ...] = ()


class UserEditRequest(BaseModel):
    username: str | None = None
    role_code: str | None = None


class StoreCreateRequest(BaseModel):
    name: str
    marketplace: str
    wb_threshold_percent: int | None = None
    wb_fallback_no_promo_percent: int | None = None
    wb_fallback_over_threshold_percent: int | None = None


class StoreEditRequest(BaseModel):
    name: str


class StoreSettingsRequest(BaseModel):
    wb_threshold_percent: int
    wb_fallback_no_promo_percent: int
    wb_fallback_over_threshold_percent: int


class TempFileUploadRequest(BaseModel):
    original_filename: str
    content_base64: str
    mime_type: str
    wb_file_kind: str | None = None


class RunCreateRequest(BaseModel):
    store_id: int


class HistoryQueryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = 1
    page_size: int = 50
    search: str | None = None
    store_id: int | None = None
    initiated_by_user_id: int | None = None
    marketplace: str | None = None
    module_code: str | None = None
    operation_type: str | None = None
    lifecycle_status: str | None = None
    business_result: str | None = None
    store_status: str | None = None
    started_from_utc: datetime | None = None
    started_to_utc: datetime | None = None
    sort_field: str = "started_at_utc"
    descending: bool = True


class LogsQueryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = 1
    page_size: int = 50
    search: str | None = None
    user_id: int | None = None
    store_id: int | None = None
    module_code: str | None = None
    event_type: str | None = None
    severity: str | None = None
    run_id: int | None = None
    public_run_number: str | None = None
    event_from_utc: datetime | None = None
    event_to_utc: datetime | None = None
    sort_field: str = "event_time_utc"
    descending: bool = True


class DetailAuditQueryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = 1
    page_size: int = 50
    search: str | None = None
    severity: str | None = None
    decision_reason: str | None = None
    row_number_from: int | None = None
    row_number_to: int | None = None
    has_entity_key_1: bool | None = None
    sort_field: str = "row_number"
    descending: bool = False
