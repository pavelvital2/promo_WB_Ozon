from __future__ import annotations

from dataclasses import dataclass

from promo.access.contracts import SessionContextDTO
from promo.access.policy import AccessPolicy
from promo.audit.contracts import ALLOWED_PAGE_SIZES, AuditReadDependencies, DetailAuditQuery, PageResult
from promo.audit.presentation import DetailAuditPageViewModel, DetailAuditRowViewModel, RunPageHeaderViewModel, RunPageReadModel
from promo.runs.presentation import RunFileViewModel, RunPollingViewModel
from promo.shared.contracts.audit import RunDetailAuditDTO, RunSummaryAuditDTO
from promo.shared.contracts.runs import RunDTO, RunFileDTO
from promo.shared.contracts.users import UserDTO
from promo.shared.errors import AccessDeniedError, ValidationFailedError


class AuditReadService:
    def __init__(self, dependencies: AuditReadDependencies, policy: AccessPolicy | None = None) -> None:
        self._dependencies = dependencies
        self._policy = policy or AccessPolicy()

    def list_detail_audit(self, context: SessionContextDTO, run_id: int, query: DetailAuditQuery) -> DetailAuditPageViewModel:
        run = self._get_run(run_id)
        self._assert_run_access(context, run)
        self._validate_pagination(query.page, query.page_size)
        query_gateway = self._dependencies.query_gateway
        if query_gateway is not None:
            page_result = query_gateway.list_detail_audit(run_id, query)
            return DetailAuditPageViewModel(
                items=tuple(self._to_row(item) for item in page_result.items),
                total_items=page_result.total_items,
                page=page_result.page,
                page_size=page_result.page_size,
            )
        items = [item for item in self._dependencies.run_detail_audits.list() if item.run_id == run_id]
        items = self._apply_filters(items, query)
        items = self._apply_sort(items, query)
        page_result = self._paginate(items, query.page, query.page_size)
        return DetailAuditPageViewModel(
            items=tuple(self._to_row(item) for item in page_result.items),
            total_items=page_result.total_items,
            page=page_result.page,
            page_size=page_result.page_size,
        )

    def get_run_page(self, context: SessionContextDTO, run_id: int, query: DetailAuditQuery | None = None) -> RunPageReadModel:
        run = self._get_run(run_id)
        self._assert_run_access(context, run)
        detail_query = query or DetailAuditQuery()
        query_gateway = self._dependencies.query_gateway
        if query_gateway is not None:
            summary = query_gateway.get_summary_audit(run_id)
            files = tuple(self._to_file(item) for item in query_gateway.list_run_files(run_id))
        else:
            summary = next((item for item in self._dependencies.run_summary_audits.list() if item.run_id == run_id), None)
            files = tuple(self._to_file(item) for item in self._load_run_files(run_id))
        result_file = self._resolve_result_file(run)
        return RunPageReadModel(
            run=self._to_header(run, result_file),
            polling=self._to_polling(run, result_file),
            summary_audit_json=None if summary is None else summary.audit_json,
            detail_audit=self.list_detail_audit(context, run_id, detail_query),
            files=files,
        )

    def _assert_run_access(self, context: SessionContextDTO, run: RunDTO) -> None:
        store = self._dependencies.stores.get(run.store_id)
        if store is None:
            raise ValidationFailedError("Store not found", {"store_id": run.store_id})
        decision = self._policy.can_access_store(context, store)
        if not decision.allowed:
            raise AccessDeniedError("Run is not accessible", {"run_id": run.id, "store_id": run.store_id})

    def _get_run(self, run_id: int) -> RunDTO:
        run = self._dependencies.runs.get(run_id)
        if run is None:
            raise ValidationFailedError("Run not found", {"run_id": run_id})
        return run

    def _load_run_files(self, run_id: int) -> tuple[RunFileDTO, ...]:
        query_gateway = self._dependencies.query_gateway
        if query_gateway is not None:
            return query_gateway.list_run_files(run_id)
        return tuple(sorted((item for item in self._dependencies.run_files.list() if item.run_id == run_id), key=lambda item: item.id))

    def _apply_filters(self, items: list[RunDetailAuditDTO], query: DetailAuditQuery) -> list[RunDetailAuditDTO]:
        filtered: list[RunDetailAuditDTO] = []
        search = None if not query.search else query.search.casefold()
        for item in items:
            if query.severity is not None and item.severity != query.severity:
                continue
            if query.decision_reason is not None and item.decision_reason != query.decision_reason:
                continue
            if query.row_number_from is not None and item.row_number < query.row_number_from:
                continue
            if query.row_number_to is not None and item.row_number > query.row_number_to:
                continue
            if query.has_entity_key_1 is True and not item.entity_key_1:
                continue
            if query.has_entity_key_1 is False and item.entity_key_1:
                continue
            if search is not None:
                haystack = (
                    str(item.row_number),
                    item.entity_key_1 or "",
                    item.entity_key_2 or "",
                    item.message,
                    item.decision_reason or "",
                )
                if not any(search in value.casefold() for value in haystack):
                    continue
            filtered.append(item)
        return filtered

    def _apply_sort(self, items: list[RunDetailAuditDTO], query: DetailAuditQuery) -> list[RunDetailAuditDTO]:
        field = query.sort_field or "row_number"
        allowed = {"row_number", "severity", "decision_reason", "entity_key_1"}
        if field not in allowed:
            raise ValidationFailedError("Unsupported audit sort field", {"sort_field": field})
        return sorted(items, key=lambda item: self._sort_value(item, field), reverse=query.descending)

    def _sort_value(self, item: RunDetailAuditDTO, field: str):
        if field == "row_number":
            return item.row_number
        if field == "severity":
            return item.severity
        if field == "decision_reason":
            return item.decision_reason or ""
        return item.entity_key_1 or ""

    def _paginate(self, items: list[RunDetailAuditDTO], page: int, page_size: int) -> PageResult[RunDetailAuditDTO]:
        self._validate_pagination(page, page_size)
        total = len(items)
        offset = (page - 1) * page_size
        return PageResult(items=tuple(items[offset:offset + page_size]), total_items=total, page=page, page_size=page_size)

    def _validate_pagination(self, page: int, page_size: int) -> None:
        if page < 1:
            raise ValidationFailedError("Page must be >= 1", {"page": page})
        if page_size not in ALLOWED_PAGE_SIZES:
            raise ValidationFailedError("Unsupported page size", {"page_size": page_size})

    def _to_row(self, item: RunDetailAuditDTO) -> DetailAuditRowViewModel:
        return DetailAuditRowViewModel(
            id=item.id,
            run_id=item.run_id,
            row_number=item.row_number,
            entity_key_1=item.entity_key_1,
            entity_key_2=item.entity_key_2,
            severity=item.severity,
            decision_reason=item.decision_reason,
            message=item.message,
            audit_payload_json=item.audit_payload_json,
            created_at_utc=item.created_at_utc,
        )

    def _to_file(self, item: RunFileDTO) -> RunFileViewModel:
        return RunFileViewModel(
            id=item.id,
            run_id=item.run_id,
            file_role=item.file_role,
            original_filename=item.original_filename,
            stored_filename=item.stored_filename,
            storage_relative_path=item.storage_relative_path,
            mime_type=item.mime_type,
            file_size_bytes=item.file_size_bytes,
            file_sha256=item.file_sha256,
            uploaded_at_utc=item.uploaded_at_utc,
            expires_at_utc=item.expires_at_utc,
            is_available=item.is_available,
            unavailable_reason=item.unavailable_reason,
        )

    def _to_polling(self, run: RunDTO, result_file: RunFileDTO | None = None) -> RunPollingViewModel:
        resolved = result_file or self._resolve_result_file(run)
        return RunPollingViewModel(
            id=run.id,
            public_run_number=run.public_run_number,
            store_id=run.store_id,
            operation_type=run.operation_type,
            lifecycle_status=run.lifecycle_status,
            execution_phase=self._execution_phase(run),
            business_result=run.business_result,
            module_code=run.module_code,
            short_result_text=run.short_result_text,
            result_file_id=None if resolved is None else resolved.id,
            result_file_is_available=None if resolved is None else resolved.is_available,
            result_file_unavailable_reason=None if resolved is None else resolved.unavailable_reason,
            is_locked=False,
            updated_at_utc=run.updated_at_utc,
        )

    def _resolve_result_file(self, run: RunDTO) -> RunFileDTO | None:
        if run.result_file_id is not None:
            linked = self._dependencies.run_files.get(run.result_file_id)
            if linked is not None and linked.run_id == run.id:
                return linked

        result_roles = {"wb_result_output", "ozon_result_output"}
        candidates = [
            item
            for item in self._load_run_files(run.id)
            if item.file_role in result_roles
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.id)

    def _to_header(self, run: RunDTO, result_file: RunFileDTO | None) -> RunPageHeaderViewModel:
        store = self._dependencies.stores.get(run.store_id)
        if store is None:
            raise ValidationFailedError("Store not found", {"store_id": run.store_id, "run_id": run.id})
        user = self._resolve_user(run.initiated_by_user_id)
        return RunPageHeaderViewModel(
            run_id=run.id,
            public_run_number=run.public_run_number,
            store_id=store.id,
            store_name=store.name,
            marketplace=store.marketplace,
            module_code=run.module_code,
            initiated_by_user_id=user.id,
            initiated_by_username=user.username,
            operation_type=run.operation_type,
            lifecycle_status=run.lifecycle_status,
            execution_phase=self._execution_phase(run),
            business_result=run.business_result,
            short_result_text=run.short_result_text,
            started_at_utc=run.started_at_utc,
            finished_at_utc=run.finished_at_utc,
            updated_at_utc=run.updated_at_utc,
            result_file_id=None if result_file is None else result_file.id,
            result_file_is_available=None if result_file is None else result_file.is_available,
            result_file_unavailable_reason=None if result_file is None else result_file.unavailable_reason,
            is_locked=False,
        )

    def _resolve_user(self, user_id: int) -> UserDTO:
        users_repo = getattr(self._dependencies, "users", None)
        if users_repo is None:
            raise ValidationFailedError("Users repository is required for run page", {"user_id": user_id})
        user = users_repo.get(user_id)
        if user is None:
            raise ValidationFailedError("User not found", {"user_id": user_id})
        return user

    def _execution_phase(self, run: RunDTO) -> str:
        if run.operation_type == "process":
            if run.lifecycle_status == "created":
                return "queued"
            if run.lifecycle_status == "validating":
                return "validating"
            if run.lifecycle_status == "processing":
                return "processing"
            return "finalized"
        if run.lifecycle_status == "created":
            return "queued"
        if run.lifecycle_status == "checking":
            return "checking"
        return "finalized"
