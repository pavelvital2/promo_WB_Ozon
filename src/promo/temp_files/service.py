from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from promo.shared.clock import utc_now
from promo.shared.contracts.files import TemporaryUploadedFileDTO
from promo.shared.enums import ErrorCode, ModuleCode
from promo.shared.errors import AppError, ValidationFailedError
from promo.shared.logging import get_logger
from promo.temp_files.contracts import TemporaryFileServiceDependencies, TemporaryFileUploadForm
from promo.temp_files.presentation import TemporaryFileListViewModel, TemporaryFileViewModel

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
MAX_WB_TOTAL_SIZE_BYTES = 100 * 1024 * 1024
MAX_WB_PROMO_FILES = 20
WB_PRICE_FILE_KIND = "price"
WB_PROMO_FILE_KIND = "promo"


class TemporaryFileService:
    def __init__(self, dependencies: TemporaryFileServiceDependencies, ttl_hours: int = 24, clock=utc_now, logger=None) -> None:
        self._dependencies = dependencies
        self._ttl_hours = ttl_hours
        self._clock = clock
        self._logger = logger or get_logger(__name__)

    def upload_file(
        self,
        uploaded_by_user_id: int,
        store_id: int,
        module_code: ModuleCode,
        form: TemporaryFileUploadForm,
    ) -> TemporaryUploadedFileDTO:
        active_files = self._active_files(uploaded_by_user_id, store_id, module_code)
        normalized_kind = self._validate_form(form, module_code)
        projected_files = self._project_active_set(
            active_files=active_files,
            module_code=module_code,
            uploaded_by_user_id=uploaded_by_user_id,
            store_id=store_id,
            replacing_file_id=None,
            new_file_size_bytes=len(form.content),
            wb_file_kind=normalized_kind,
        )
        self._validate_projected_set(module_code, projected_files)

        if module_code == ModuleCode.OZON:
            self._replace_active_pair(uploaded_by_user_id, store_id, module_code)
        elif module_code == ModuleCode.WB and normalized_kind == WB_PRICE_FILE_KIND:
            self._replace_active_price_slot(uploaded_by_user_id, store_id)
        return self._store_uploaded_file(
            uploaded_by_user_id=uploaded_by_user_id,
            store_id=store_id,
            module_code=module_code,
            form=form,
            wb_file_kind=normalized_kind,
            event_type="file_uploaded",
        )

    def replace_file(
        self,
        file_id: int,
        form: TemporaryFileUploadForm,
    ) -> TemporaryUploadedFileDTO:
        existing = self._dependencies.temporary_files.get(file_id)
        if existing is None:
            raise ValidationFailedError("Temporary file not found", {"file_id": file_id})
        module_code = ModuleCode(existing.module_code)
        inherited_kind = existing.wb_file_kind if module_code == ModuleCode.WB else None
        effective_form = replace(form, wb_file_kind=form.wb_file_kind or inherited_kind)
        active_files = self._active_files(existing.uploaded_by_user_id, existing.store_id, module_code)
        normalized_kind = self._validate_form(effective_form, module_code)
        projected_files = self._project_active_set(
            active_files=active_files,
            module_code=module_code,
            uploaded_by_user_id=existing.uploaded_by_user_id,
            store_id=existing.store_id,
            replacing_file_id=file_id,
            new_file_size_bytes=len(effective_form.content),
            wb_file_kind=normalized_kind,
        )
        self._validate_projected_set(module_code, projected_files)
        self._dependencies.file_storage.delete_relative_path(existing.storage_relative_path)
        self._dependencies.temporary_files.update(replace(existing, is_active_in_current_set=False))
        replaced = self._store_uploaded_file(
            uploaded_by_user_id=existing.uploaded_by_user_id,
            store_id=existing.store_id,
            module_code=module_code,
            form=effective_form,
            wb_file_kind=normalized_kind,
            event_type="temporary_file_replaced",
            replaced_file=existing,
        )
        return replaced

    def delete_file(self, file_id: int) -> None:
        existing = self._dependencies.temporary_files.get(file_id)
        if existing is None:
            return
        self._dependencies.file_storage.delete_relative_path(existing.storage_relative_path)
        self._dependencies.temporary_files.delete(file_id)
        self._logger.info(
            "temporary_file_deleted user_id=%s store_id=%s module_code=%s file_metadata_id=%s storage_path=%s wb_file_kind=%s",
            existing.uploaded_by_user_id,
            existing.store_id,
            existing.module_code,
            existing.id,
            existing.storage_relative_path,
            existing.wb_file_kind or "",
        )

    def list_active_files(self, uploaded_by_user_id: int, store_id: int, module_code: ModuleCode) -> TemporaryFileListViewModel:
        items = tuple(
            self._to_view_model(file)
            for file in self._dependencies.temporary_files.list()
            if file.uploaded_by_user_id == uploaded_by_user_id
            and file.store_id == store_id
            and file.module_code == module_code.value
            and file.is_active_in_current_set
        )
        return TemporaryFileListViewModel(items=tuple(sorted(items, key=lambda item: item.id)), total_items=len(items))

    def purge_expired_files(self, now: datetime | None = None) -> int:
        now = now or self._clock()
        affected = 0
        for item in list(self._dependencies.temporary_files.list()):
            if item.expires_at_utc > now:
                continue
            self._dependencies.file_storage.delete_relative_path(item.storage_relative_path)
            self._dependencies.temporary_files.delete(item.id)
            affected += 1
        return affected

    def current_set_signature(self, uploaded_by_user_id: int, store_id: int, module_code: ModuleCode) -> str:
        files = [
            file
            for file in self._dependencies.temporary_files.list()
            if file.uploaded_by_user_id == uploaded_by_user_id
            and file.store_id == store_id
            and file.module_code == module_code.value
            and file.is_active_in_current_set
        ]
        if not files:
            return ""
        payload = "|".join(
            f"{file.file_sha256}:{file.file_size_bytes}:{file.original_filename}"
            for file in sorted(files, key=lambda item: item.id)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _to_view_model(self, file: TemporaryUploadedFileDTO) -> TemporaryFileViewModel:
        return TemporaryFileViewModel(
            id=file.id,
            uploaded_by_user_id=file.uploaded_by_user_id,
            store_id=file.store_id,
            module_code=file.module_code,
            wb_file_kind=file.wb_file_kind,
            original_filename=file.original_filename,
            stored_filename=file.stored_filename,
            storage_relative_path=file.storage_relative_path,
            mime_type=file.mime_type,
            file_size_bytes=file.file_size_bytes,
            file_sha256=file.file_sha256,
            uploaded_at_utc=file.uploaded_at_utc,
            expires_at_utc=file.expires_at_utc,
            is_active_in_current_set=file.is_active_in_current_set,
        )

    def _next_id(self) -> int:
        return max((item.id for item in self._dependencies.temporary_files.list()), default=0) + 1

    def _store_uploaded_file(
        self,
        *,
        uploaded_by_user_id: int,
        store_id: int,
        module_code: ModuleCode,
        form: TemporaryFileUploadForm,
        wb_file_kind: str | None,
        event_type: str,
        replaced_file: TemporaryUploadedFileDTO | None = None,
    ) -> TemporaryUploadedFileDTO:
        now = self._clock()
        stored = self._dependencies.file_storage.write_temp_upload(form.original_filename, form.content, form.mime_type, now)
        record = TemporaryUploadedFileDTO(
            id=self._next_id(),
            uploaded_by_user_id=uploaded_by_user_id,
            store_id=store_id,
            module_code=module_code.value,
            wb_file_kind=wb_file_kind,
            original_filename=form.original_filename,
            stored_filename=stored.stored_filename,
            storage_relative_path=stored.storage_relative_path,
            mime_type=form.mime_type,
            file_size_bytes=stored.file_size_bytes,
            file_sha256=stored.file_sha256,
            uploaded_at_utc=now,
            expires_at_utc=now + timedelta(hours=self._ttl_hours),
            is_active_in_current_set=True,
            created_at_utc=now,
        )
        created = self._dependencies.temporary_files.add(record)
        if replaced_file is None:
            self._logger.info(
                "file_uploaded user_id=%s store_id=%s module_code=%s file_metadata_id=%s storage_path=%s wb_file_kind=%s file_size_bytes=%s",
                created.uploaded_by_user_id,
                created.store_id,
                created.module_code,
                created.id,
                created.storage_relative_path,
                created.wb_file_kind or "",
                created.file_size_bytes,
            )
        else:
            self._logger.info(
                "%s user_id=%s store_id=%s module_code=%s file_metadata_id=%s replaced_file_metadata_id=%s storage_path=%s replaced_storage_path=%s wb_file_kind=%s file_size_bytes=%s",
                event_type,
                created.uploaded_by_user_id,
                created.store_id,
                created.module_code,
                created.id,
                replaced_file.id,
                created.storage_relative_path,
                replaced_file.storage_relative_path,
                created.wb_file_kind or "",
                created.file_size_bytes,
            )
        return created

    def _validate_form(self, form: TemporaryFileUploadForm, module_code: ModuleCode) -> str | None:
        if not form.original_filename.strip():
            raise ValidationFailedError("Original filename is required")
        if not form.content:
            raise ValidationFailedError("File content is required")
        if len(form.content) > MAX_FILE_SIZE_BYTES:
            raise AppError(
                ErrorCode.FILE_LIMIT_EXCEEDED,
                "File exceeds per-file size limit",
                {
                    "limit_type": "per_file_size",
                    "file_size_bytes": len(form.content),
                    "max_file_size_bytes": MAX_FILE_SIZE_BYTES,
                },
            )
        if module_code == ModuleCode.WB:
            normalized_kind = (form.wb_file_kind or "").strip().casefold()
            if normalized_kind not in {WB_PRICE_FILE_KIND, WB_PROMO_FILE_KIND}:
                raise ValidationFailedError(
                    "WB file kind is required",
                    {"module_code": module_code.value, "allowed_wb_file_kinds": [WB_PRICE_FILE_KIND, WB_PROMO_FILE_KIND]},
                )
            return normalized_kind
        return None

    def _replace_active_pair(self, uploaded_by_user_id: int, store_id: int, module_code: ModuleCode) -> None:
        for item in list(self._dependencies.temporary_files.list()):
            if (
                item.uploaded_by_user_id == uploaded_by_user_id
                and item.store_id == store_id
                and item.module_code == module_code.value
                and item.is_active_in_current_set
            ):
                self._dependencies.file_storage.delete_relative_path(item.storage_relative_path)
                self._dependencies.temporary_files.update(replace(item, is_active_in_current_set=False))

    def _replace_active_price_slot(self, uploaded_by_user_id: int, store_id: int) -> None:
        for item in list(self._dependencies.temporary_files.list()):
            if (
                item.uploaded_by_user_id == uploaded_by_user_id
                and item.store_id == store_id
                and item.module_code == ModuleCode.WB.value
                and item.is_active_in_current_set
                and item.wb_file_kind == WB_PRICE_FILE_KIND
            ):
                self._dependencies.file_storage.delete_relative_path(item.storage_relative_path)
                self._dependencies.temporary_files.update(replace(item, is_active_in_current_set=False))

    def _active_files(self, uploaded_by_user_id: int, store_id: int, module_code: ModuleCode) -> tuple[TemporaryUploadedFileDTO, ...]:
        return tuple(
            item
            for item in self._dependencies.temporary_files.list()
            if item.uploaded_by_user_id == uploaded_by_user_id
            and item.store_id == store_id
            and item.module_code == module_code.value
            and item.is_active_in_current_set
        )

    def _project_active_set(
        self,
        *,
        active_files: tuple[TemporaryUploadedFileDTO, ...],
        module_code: ModuleCode,
        uploaded_by_user_id: int,
        store_id: int,
        replacing_file_id: int | None,
        new_file_size_bytes: int,
        wb_file_kind: str | None,
    ) -> tuple[TemporaryUploadedFileDTO, ...]:
        remaining = [item for item in active_files if item.id != replacing_file_id]
        if module_code == ModuleCode.OZON:
            return (
                TemporaryUploadedFileDTO(
                    id=-1,
                    uploaded_by_user_id=uploaded_by_user_id,
                    store_id=store_id,
                    module_code=module_code.value,
                    wb_file_kind=None,
                    original_filename="projected",
                    stored_filename="projected",
                    storage_relative_path="projected",
                    mime_type="projected",
                    file_size_bytes=new_file_size_bytes,
                    file_sha256="projected",
                    uploaded_at_utc=datetime.now(tz=UTC),
                    expires_at_utc=datetime.now(tz=UTC),
                    is_active_in_current_set=True,
                    created_at_utc=datetime.now(tz=UTC),
                ),
            )

        if wb_file_kind == WB_PRICE_FILE_KIND:
            remaining = [item for item in remaining if item.wb_file_kind != WB_PRICE_FILE_KIND]

        remaining.append(
            TemporaryUploadedFileDTO(
                id=-1,
                uploaded_by_user_id=uploaded_by_user_id,
                store_id=store_id,
                module_code=module_code.value,
                wb_file_kind=wb_file_kind,
                original_filename="projected",
                stored_filename="projected",
                storage_relative_path="projected",
                mime_type="projected",
                file_size_bytes=new_file_size_bytes,
                file_sha256="projected",
                uploaded_at_utc=datetime.now(tz=UTC),
                expires_at_utc=datetime.now(tz=UTC),
                is_active_in_current_set=True,
                created_at_utc=datetime.now(tz=UTC),
            )
        )
        return tuple(remaining)

    def _validate_projected_set(self, module_code: ModuleCode, projected_files: tuple[TemporaryUploadedFileDTO, ...]) -> None:
        if module_code != ModuleCode.WB:
            return
        total_size = sum(item.file_size_bytes for item in projected_files)
        if total_size > MAX_WB_TOTAL_SIZE_BYTES:
            raise AppError(
                ErrorCode.FILE_LIMIT_EXCEEDED,
                "WB file set exceeds total size limit",
                {
                    "limit_type": "wb_total_size",
                    "total_file_size_bytes": total_size,
                    "max_total_file_size_bytes": MAX_WB_TOTAL_SIZE_BYTES,
                },
            )
        promo_count = sum(1 for item in projected_files if item.wb_file_kind == WB_PROMO_FILE_KIND)
        if promo_count > MAX_WB_PROMO_FILES:
            raise AppError(
                ErrorCode.FILE_LIMIT_EXCEEDED,
                "WB promo file limit exceeded",
                {
                    "limit_type": "wb_promo_count",
                    "promo_file_count": promo_count,
                    "max_promo_file_count": MAX_WB_PROMO_FILES,
                },
            )
