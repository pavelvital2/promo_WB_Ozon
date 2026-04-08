from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class TemporaryFileViewModel:
    id: int
    uploaded_by_user_id: int
    store_id: int
    module_code: str
    wb_file_kind: str | None
    original_filename: str
    stored_filename: str
    storage_relative_path: str
    mime_type: str
    file_size_bytes: int
    file_sha256: str
    uploaded_at_utc: datetime
    expires_at_utc: datetime
    is_active_in_current_set: bool


@dataclass(slots=True, frozen=True)
class TemporaryFileListViewModel:
    items: tuple[TemporaryFileViewModel, ...]
    total_items: int
