from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

import pytest

from promo.access.contracts import AccessibleStoreDTO, SessionContextDTO
from promo.audit.contracts import AuditReadDependencies, DetailAuditQuery, PageResult
from promo.audit.service import AuditReadService
from promo.history.contracts import HistoryQuery, HistoryReadDependencies
from promo.history.presentation import HistoryItemViewModel
from promo.history.service import HistoryReadService
from promo.logs.contracts import LogsQuery, LogsReadDependencies
from promo.logs.presentation import LogItemViewModel
from promo.logs.service import LogsReadService
from promo.shared.contracts.audit import RunDetailAuditDTO, RunSummaryAuditDTO
from promo.shared.contracts.logs import SystemLogDTO
from promo.shared.contracts.runs import RunDTO, RunFileDTO
from promo.shared.contracts.stores import StoreDTO
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO
from promo.shared.enums import MarketplaceCode, RoleCode, StoreStatus, UnavailableReason
from promo.shared.errors import AccessDeniedError

T = TypeVar("T")


class MemoryRepository(Generic[T]):
    def __init__(self, items: list[T] | None = None) -> None:
        self._items: dict[int, T] = {}
        for item in items or []:
            self.add(item)

    def get(self, key: int) -> T | None:
        return self._items.get(key)

    def list(self) -> tuple[T, ...]:
        return tuple(self._items.values())

    def add(self, entity: T) -> T:
        self._items[getattr(entity, "id")] = entity
        return entity


class ExplodingListRepository(MemoryRepository[T]):
    def list(self) -> tuple[T, ...]:
        raise AssertionError("list() should not be used when query gateway is configured")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _user(user_id: int, username: str, role_id: int = 2) -> UserDTO:
    return UserDTO(
        id=user_id,
        username=username,
        password_hash="hash",
        role_id=role_id,
        is_blocked=False,
        created_at_utc=_dt("2026-04-07T09:00:00+00:00"),
        updated_at_utc=_dt("2026-04-07T09:00:00+00:00"),
        last_login_at_utc=None,
    )


def _store(store_id: int, name: str, marketplace: str) -> StoreDTO:
    return StoreDTO(
        id=store_id,
        name=name,
        marketplace=marketplace,
        status=StoreStatus.ACTIVE.value,
        wb_threshold_percent=60 if marketplace == MarketplaceCode.WB.value else None,
        wb_fallback_no_promo_percent=40 if marketplace == MarketplaceCode.WB.value else None,
        wb_fallback_over_threshold_percent=25 if marketplace == MarketplaceCode.WB.value else None,
        created_by_user_id=1,
        created_at_utc=_dt("2026-04-07T09:00:00+00:00"),
        updated_at_utc=_dt("2026-04-07T09:00:00+00:00"),
        archived_at_utc=None,
        archived_by_user_id=None,
    )


def _run(run_id: int, store_id: int, user_id: int, public_run_number: str, module_code: str, operation_type: str, started: str) -> RunDTO:
    started_at = _dt(started)
    return RunDTO(
        id=run_id,
        public_run_number=public_run_number,
        store_id=store_id,
        initiated_by_user_id=user_id,
        operation_type=operation_type,
        lifecycle_status="completed",
        business_result="completed" if operation_type == "process" else "check_passed",
        module_code=module_code,
        input_set_signature=f"sig-{run_id}",
        started_at_utc=started_at,
        finished_at_utc=started_at + timedelta(minutes=1),
        short_result_text=f"run {run_id}",
        result_file_id=1000 + run_id,
        validation_was_auto_before_process=operation_type == "process",
        created_at_utc=started_at,
        updated_at_utc=started_at + timedelta(minutes=1),
    )


def _run_file(file_id: int, run_id: int, original_filename: str) -> RunFileDTO:
    return RunFileDTO(
        id=file_id,
        run_id=run_id,
        file_role="wb_price_input",
        original_filename=original_filename,
        stored_filename=f"{file_id}.xlsx",
        storage_relative_path=f"runs/file-{file_id}.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_size_bytes=100,
        file_sha256=f"sha-{file_id}",
        uploaded_at_utc=_dt("2026-04-07T09:00:00+00:00"),
        expires_at_utc=_dt("2026-04-12T09:00:00+00:00"),
        is_available=True,
        unavailable_reason=None,
        created_at_utc=_dt("2026-04-07T09:00:00+00:00"),
    )


def _summary(run_id: int) -> RunSummaryAuditDTO:
    return RunSummaryAuditDTO(id=run_id, run_id=run_id, audit_json={"run_id": run_id}, created_at_utc=_dt("2026-04-07T09:00:00+00:00"))


def _detail(detail_id: int, run_id: int, row_number: int, severity: str = "info") -> RunDetailAuditDTO:
    return RunDetailAuditDTO(
        id=detail_id,
        run_id=run_id,
        row_number=row_number,
        entity_key_1=f"entity-{row_number}" if row_number % 2 else None,
        entity_key_2=None,
        severity=severity,
        decision_reason="reason-a" if row_number % 2 else "reason-b",
        message=f"detail row {row_number}",
        audit_payload_json={"row_number": row_number},
        created_at_utc=_dt("2026-04-07T09:00:00+00:00"),
    )


def _log(log_id: int, run_id: int | None, user_id: int | None, store_id: int | None, message: str, event_time: str) -> SystemLogDTO:
    return SystemLogDTO(
        id=log_id,
        event_time_utc=_dt(event_time),
        user_id=user_id,
        store_id=store_id,
        run_id=run_id,
        module_code="wb" if store_id == 1 else "ozon",
        event_type="process_finished",
        severity="info",
        message=message,
        payload_json=None,
    )


def _context_admin(*stores: StoreDTO) -> SessionContextDTO:
    return SessionContextDTO(
        user=_user(1, "admin", role_id=1),
        role=RoleDTO(id=1, code=RoleCode.ADMIN.value, name="Администратор"),
        permissions=(
            PermissionDTO(id=1, code="create_store", name="create_store"),
            PermissionDTO(id=2, code="edit_store", name="edit_store"),
        ),
        accessible_stores=tuple(
            AccessibleStoreDTO(id=store.id, name=store.name, marketplace=MarketplaceCode(store.marketplace), status=StoreStatus(store.status))
            for store in stores
        ),
        is_admin=True,
        can_create_store=True,
        can_edit_store=True,
        is_blocked=False,
    )


def _context_manager(user_id: int, username: str, *stores: StoreDTO) -> SessionContextDTO:
    return SessionContextDTO(
        user=_user(user_id, username),
        role=RoleDTO(id=2, code=RoleCode.MANAGER.value, name="Менеджер"),
        permissions=(),
        accessible_stores=tuple(
            AccessibleStoreDTO(id=store.id, name=store.name, marketplace=MarketplaceCode(store.marketplace), status=StoreStatus(store.status))
            for store in stores
        ),
        is_admin=False,
        can_create_store=False,
        can_edit_store=False,
        is_blocked=False,
    )


def test_history_read_side_is_server_scoped_and_searchable() -> None:
    store_wb = _store(1, "VitalEmb", MarketplaceCode.WB.value)
    store_ozon = _store(2, "OzonShop", MarketplaceCode.OZON.value)
    users = MemoryRepository([_user(1, "admin", role_id=1), _user(2, "manager")])
    runs = MemoryRepository(
        [
            _run(1, 1, 1, "RUN-000001", "wb", "check", "2026-04-07T10:00:00+00:00"),
            _run(2, 2, 2, "RUN-000002", "ozon", "process", "2026-04-07T11:00:00+00:00"),
        ]
    )
    run_files = MemoryRepository(
        [
            _run_file(11, 1, "price.xlsx"),
            _run_file(12, 1, "promo.xlsx"),
            _run_file(21, 2, "ozon.xlsx"),
        ]
    )
    service = HistoryReadService(
        HistoryReadDependencies(
            runs=runs,
            run_files=run_files,
            stores=MemoryRepository([store_wb, store_ozon]),
            users=users,
        )
    )

    manager_context = _context_manager(2, "manager", store_wb)
    page = service.list_history(manager_context, HistoryQuery(search="price", sort_field="public_run_number", descending=False))
    assert page.total_items == 1
    assert page.items[0].store_id == 1
    assert page.items[0].public_run_number == "RUN-000001"

    admin_context = _context_admin(store_wb, store_ozon)
    full_page = service.list_history(admin_context, HistoryQuery(sort_field="started_at_utc", descending=True))
    assert full_page.total_items == 2
    assert full_page.items[0].public_run_number == "RUN-000002"


def test_logs_read_side_is_admin_only_and_filterable() -> None:
    store_wb = _store(1, "VitalEmb", MarketplaceCode.WB.value)
    users = MemoryRepository([_user(1, "admin", role_id=1), _user(2, "manager")])
    runs = MemoryRepository([_run(1, 1, 1, "RUN-000001", "wb", "check", "2026-04-07T10:00:00+00:00")])
    logs = MemoryRepository(
        [
            _log(1, 1, 1, 1, "run completed", "2026-04-07T10:01:00+00:00"),
            _log(2, None, 2, 1, "other message", "2026-04-07T10:02:00+00:00"),
        ]
    )
    service = LogsReadService(
        LogsReadDependencies(
            logs=logs,
            runs=runs,
            stores=MemoryRepository([store_wb]),
            users=users,
        )
    )

    with pytest.raises(AccessDeniedError):
        service.list_logs(_context_manager(2, "manager", store_wb), LogsQuery())

    page = service.list_logs(_context_admin(store_wb), LogsQuery(search="RUN-000001", sort_field="event_time_utc", descending=False))
    assert page.total_items == 1
    assert page.items[0].public_run_number == "RUN-000001"
    assert page.items[0].username == "admin"


def test_audit_read_side_is_paged_and_run_page_uses_same_source() -> None:
    store_wb = _store(1, "VitalEmb", MarketplaceCode.WB.value)
    run = _run(1, 1, 1, "RUN-000001", "wb", "process", "2026-04-07T10:00:00+00:00")
    detail_rows = [_detail(idx, 1, idx, severity="warning" if idx % 3 == 0 else "info") for idx in range(1, 31)]
    run_files = [
        _run_file(11, 1, "price.xlsx"),
        replace(_run_file(12, 1, "result.xlsx"), file_role="wb_result_output", unavailable_reason=UnavailableReason.SUPERSEDED.value, is_available=False),
    ]
    service = AuditReadService(
        AuditReadDependencies(
            runs=MemoryRepository([run]),
            run_files=MemoryRepository(run_files),
            run_summary_audits=MemoryRepository([_summary(1)]),
            run_detail_audits=MemoryRepository(detail_rows),
            stores=MemoryRepository([store_wb]),
            users=MemoryRepository([_user(1, "admin", role_id=1), _user(2, "manager")]),
        )
    )

    context = _context_manager(2, "manager", store_wb)
    detail_page = service.list_detail_audit(
        context,
        1,
        DetailAuditQuery(page=1, page_size=25, severity="warning", sort_field="row_number", descending=False),
    )
    assert detail_page.total_items == 10
    assert len(detail_page.items) == 10
    assert detail_page.items[0].row_number == 3

    run_page = service.get_run_page(
        context,
        1,
        DetailAuditQuery(page=1, page_size=25, severity="warning", sort_field="row_number", descending=False),
    )
    assert run_page.run.store_name == "VitalEmb"
    assert run_page.run.marketplace == "wb"
    assert run_page.run.module_code == "wb"
    assert run_page.run.initiated_by_username == "admin"
    assert run_page.run.started_at_utc == run.started_at_utc
    assert run_page.run.finished_at_utc == run.finished_at_utc
    assert run_page.summary_audit_json == {"run_id": 1}
    assert run_page.detail_audit.total_items == detail_page.total_items
    assert run_page.detail_audit.items[0].row_number == detail_page.items[0].row_number
    assert run_page.files[-1].is_available is False
    assert run_page.run.result_file_is_available is False
    assert run_page.polling.result_file_is_available is False


def test_run_page_header_falls_back_to_result_output_file_when_link_is_missing() -> None:
    store_wb = _store(1, "VitalEmb", MarketplaceCode.WB.value)
    run = replace(
        _run(1, 1, 1, "RUN-000001", "wb", "process", "2026-04-07T10:00:00+00:00"),
        result_file_id=9999,
    )
    input_file = _run_file(11, 1, "price.xlsx")
    result_file = replace(
        _run_file(12, 1, "result.xlsx"),
        file_role="wb_result_output",
        is_available=False,
        unavailable_reason=UnavailableReason.SUPERSEDED.value,
    )
    service = AuditReadService(
        AuditReadDependencies(
            runs=MemoryRepository([run]),
            run_files=MemoryRepository([input_file, result_file]),
            run_summary_audits=MemoryRepository([_summary(1)]),
            run_detail_audits=MemoryRepository([_detail(1, 1, 1)]),
            stores=MemoryRepository([store_wb]),
            users=MemoryRepository([_user(1, "admin", role_id=1), _user(2, "manager")]),
        )
    )

    page = service.get_run_page(_context_manager(2, "manager", store_wb), 1, DetailAuditQuery(page=1, page_size=25))
    assert page.files[-1].file_role == "wb_result_output"
    assert page.files[-1].is_available is False
    assert page.run.result_file_id == 12
    assert page.run.result_file_is_available is False
    assert page.run.result_file_unavailable_reason == UnavailableReason.SUPERSEDED.value
    assert page.polling.result_file_id == 12
    assert page.polling.result_file_is_available is False
    assert page.run.store_name == "VitalEmb"
    assert page.run.marketplace == "wb"
    assert page.run.module_code == "wb"
    assert page.run.initiated_by_username == "admin"
    assert page.run.started_at_utc == run.started_at_utc
    assert page.run.finished_at_utc == run.finished_at_utc


def test_audit_read_side_denies_run_from_foreign_store() -> None:
    store_wb = _store(1, "VitalEmb", MarketplaceCode.WB.value)
    foreign_store = _store(2, "Other", MarketplaceCode.OZON.value)
    service = AuditReadService(
        AuditReadDependencies(
            runs=MemoryRepository([_run(1, 2, 1, "RUN-000001", "ozon", "check", "2026-04-07T10:00:00+00:00")]),
            run_files=MemoryRepository([]),
            run_summary_audits=MemoryRepository([]),
            run_detail_audits=MemoryRepository([]),
            stores=MemoryRepository([store_wb, foreign_store]),
            users=MemoryRepository([_user(1, "admin", role_id=1), _user(2, "manager")]),
        )
    )

    with pytest.raises(AccessDeniedError):
        service.get_run_page(_context_manager(2, "manager", store_wb), 1, DetailAuditQuery(page_size=25))


def test_history_service_uses_query_gateway_without_python_list_filtering() -> None:
    store_wb = _store(1, "VitalEmb", MarketplaceCode.WB.value)
    expected_item = HistoryItemViewModel(
        run_id=1,
        public_run_number="RUN-000001",
        store_id=1,
        store_name=store_wb.name,
        store_marketplace=store_wb.marketplace,
        store_status=store_wb.status,
        initiated_by_user_id=1,
        initiated_by_username="admin",
        operation_type="process",
        lifecycle_status="completed",
        business_result="completed",
        module_code="wb",
        started_at_utc=_dt("2026-04-07T10:00:00+00:00"),
        finished_at_utc=_dt("2026-04-07T10:01:00+00:00"),
        short_result_text="done",
        original_filenames=("price.xlsx",),
    )

    class Gateway:
        def list_history(self, query, accessible_store_ids):
            assert accessible_store_ids == (1,)
            return PageResult(items=(expected_item,), total_items=1, page=query.page, page_size=query.page_size)

    service = HistoryReadService(
        HistoryReadDependencies(
            runs=ExplodingListRepository([]),
            run_files=ExplodingListRepository([]),
            stores=ExplodingListRepository([]),
            users=ExplodingListRepository([]),
            query_gateway=Gateway(),
        )
    )

    page = service.list_history(_context_manager(2, "manager", store_wb), HistoryQuery(page=1, page_size=25))
    assert page.total_items == 1
    assert page.items[0].public_run_number == "RUN-000001"


def test_logs_service_uses_query_gateway_without_python_list_filtering() -> None:
    expected_item = LogItemViewModel(
        id=1,
        event_time_utc=_dt("2026-04-07T10:01:00+00:00"),
        user_id=1,
        username="admin",
        store_id=1,
        store_name="VitalEmb",
        run_id=1,
        public_run_number="RUN-000001",
        module_code="wb",
        event_type="process_finished",
        severity="info",
        message="done",
        payload_json=None,
    )

    class Gateway:
        def list_logs(self, query):
            return PageResult(items=(expected_item,), total_items=1, page=query.page, page_size=query.page_size)

    service = LogsReadService(
        LogsReadDependencies(
            logs=ExplodingListRepository([]),
            runs=ExplodingListRepository([]),
            stores=ExplodingListRepository([]),
            users=ExplodingListRepository([]),
            query_gateway=Gateway(),
        )
    )

    page = service.list_logs(_context_admin(_store(1, "VitalEmb", MarketplaceCode.WB.value)), LogsQuery(page=1, page_size=25))
    assert page.total_items == 1
    assert page.items[0].event_type == "process_finished"


def test_audit_service_uses_query_gateway_without_python_list_filtering() -> None:
    store_wb = _store(1, "VitalEmb", MarketplaceCode.WB.value)
    run = _run(1, 1, 1, "RUN-000001", "wb", "process", "2026-04-07T10:00:00+00:00")
    detail = _detail(1, 1, 1)
    summary = _summary(1)
    result_file = replace(
        _run_file(12, 1, "result.xlsx"),
        file_role="wb_result_output",
        is_available=False,
        unavailable_reason=UnavailableReason.SUPERSEDED.value,
    )

    class Gateway:
        def list_detail_audit(self, run_id, query):
            assert run_id == 1
            return PageResult(items=(detail,), total_items=1, page=query.page, page_size=query.page_size)

        def get_summary_audit(self, run_id):
            assert run_id == 1
            return summary

        def list_run_files(self, run_id):
            assert run_id == 1
            return (result_file,)

    service = AuditReadService(
        AuditReadDependencies(
            runs=MemoryRepository([run]),
            run_files=ExplodingListRepository([]),
            run_summary_audits=ExplodingListRepository([]),
            run_detail_audits=ExplodingListRepository([]),
            stores=MemoryRepository([store_wb]),
            users=MemoryRepository([_user(1, "admin", role_id=1), _user(2, "manager")]),
            query_gateway=Gateway(),
        )
    )

    page = service.get_run_page(_context_manager(2, "manager", store_wb), 1, DetailAuditQuery(page=1, page_size=25))
    assert page.summary_audit_json == {"run_id": 1}
    assert page.detail_audit.total_items == 1
    assert page.run.result_file_unavailable_reason == UnavailableReason.SUPERSEDED.value
