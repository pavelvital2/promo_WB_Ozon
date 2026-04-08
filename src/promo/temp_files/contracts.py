from __future__ import annotations

from dataclasses import dataclass

from promo.file_storage.service import FileStorageService
from promo.shared.contracts.files import TemporaryUploadedFileDTO
from promo.shared.persistence.contracts import Repository


@dataclass(slots=True, frozen=True)
class TemporaryFileUploadForm:
    original_filename: str
    content: bytes
    mime_type: str
    wb_file_kind: str | None = None


@dataclass(slots=True, frozen=True)
class TemporaryFileServiceDependencies:
    temporary_files: Repository[TemporaryUploadedFileDTO, int]
    file_storage: FileStorageService
