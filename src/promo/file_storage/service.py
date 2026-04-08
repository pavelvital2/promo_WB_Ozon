from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from promo.shared.files.paths import StoragePathBuilder


@dataclass(slots=True, frozen=True)
class StoredFileDTO:
    original_filename: str
    stored_filename: str
    storage_relative_path: str
    absolute_path: Path
    mime_type: str
    file_size_bytes: int
    file_sha256: str
    created_at_utc: datetime


class FileStorageService:
    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path
        self._paths = StoragePathBuilder(root_path=root_path)

    @property
    def root_path(self) -> Path:
        return self._root_path

    def write_temp_upload(self, original_filename: str, content: bytes, mime_type: str, created_at_utc: datetime | None = None) -> StoredFileDTO:
        created_at_utc = created_at_utc or datetime.now(tz=UTC)
        stored_filename = self._build_stored_filename(original_filename)
        directory = self._paths.temp_uploads_dir()
        return self._write_bytes(
            directory=directory,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content=content,
            mime_type=mime_type,
            created_at_utc=created_at_utc,
        )

    def copy_to_run_input(
        self,
        source_path: Path,
        module_code: str,
        store_id: int | str,
        public_run_number: str,
        original_filename: str,
        mime_type: str,
        created_at_utc: datetime | None = None,
    ) -> StoredFileDTO:
        created_at_utc = created_at_utc or datetime.now(tz=UTC)
        stored_filename = self._build_stored_filename(original_filename)
        directory = self._paths.run_input_dir(module_code, store_id, public_run_number)
        directory.mkdir(parents=True, exist_ok=True)
        target_path = directory / stored_filename
        copy2(source_path, target_path)
        content = target_path.read_bytes()
        return self._build_record(
            original_filename=original_filename,
            stored_filename=stored_filename,
            absolute_path=target_path,
            content=content,
            mime_type=mime_type,
            created_at_utc=created_at_utc,
        )

    def copy_to_run_output(
        self,
        source_path: Path,
        module_code: str,
        store_id: int | str,
        public_run_number: str,
        original_filename: str,
        mime_type: str,
        created_at_utc: datetime | None = None,
    ) -> StoredFileDTO:
        created_at_utc = created_at_utc or datetime.now(tz=UTC)
        stored_filename = self._build_stored_filename(original_filename)
        directory = self._paths.run_output_dir(module_code, store_id, public_run_number)
        directory.mkdir(parents=True, exist_ok=True)
        target_path = directory / stored_filename
        copy2(source_path, target_path)
        content = target_path.read_bytes()
        return self._build_record(
            original_filename=original_filename,
            stored_filename=stored_filename,
            absolute_path=target_path,
            content=content,
            mime_type=mime_type,
            created_at_utc=created_at_utc,
        )

    def delete_relative_path(self, storage_relative_path: str) -> bool:
        absolute_path = self._root_path / storage_relative_path
        if not absolute_path.exists():
            return False
        absolute_path.unlink()
        return True

    def delete_absolute_path(self, absolute_path: Path) -> bool:
        if not absolute_path.exists():
            return False
        absolute_path.unlink()
        return True

    def build_relative_path(self, absolute_path: Path) -> str:
        return absolute_path.relative_to(self._root_path).as_posix()

    def temp_uploads_path(self) -> Path:
        return self._paths.temp_uploads_dir()

    def run_input_path(self, module_code: str, store_id: int | str, public_run_number: str) -> Path:
        return self._paths.run_input_dir(module_code, store_id, public_run_number)

    def run_output_path(self, module_code: str, store_id: int | str, public_run_number: str) -> Path:
        return self._paths.run_output_dir(module_code, store_id, public_run_number)

    def _write_bytes(
        self,
        directory: Path,
        original_filename: str,
        stored_filename: str,
        content: bytes,
        mime_type: str,
        created_at_utc: datetime,
    ) -> StoredFileDTO:
        directory.mkdir(parents=True, exist_ok=True)
        absolute_path = directory / stored_filename
        absolute_path.write_bytes(content)
        return self._build_record(
            original_filename=original_filename,
            stored_filename=stored_filename,
            absolute_path=absolute_path,
            content=content,
            mime_type=mime_type,
            created_at_utc=created_at_utc,
        )

    def _build_record(
        self,
        original_filename: str,
        stored_filename: str,
        absolute_path: Path,
        content: bytes,
        mime_type: str,
        created_at_utc: datetime,
    ) -> StoredFileDTO:
        return StoredFileDTO(
            original_filename=original_filename,
            stored_filename=stored_filename,
            storage_relative_path=self.build_relative_path(absolute_path),
            absolute_path=absolute_path,
            mime_type=mime_type,
            file_size_bytes=len(content),
            file_sha256=sha256(content).hexdigest(),
            created_at_utc=created_at_utc,
        )

    def _build_stored_filename(self, original_filename: str) -> str:
        safe_name = self._sanitize_original_filename(original_filename)
        suffix = Path(safe_name).suffix.lower()
        stem = Path(safe_name).stem or "file"
        return f"{stem}-{uuid4().hex}{suffix}"

    def _sanitize_original_filename(self, original_filename: str) -> str:
        candidate = original_filename.replace("\\", "/").split("/")[-1].strip()
        if not candidate:
            return "file"
        candidate = candidate.replace("\x00", "").strip(".")
        return candidate or "file"
