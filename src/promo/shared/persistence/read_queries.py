from __future__ import annotations

from collections import defaultdict
from dataclasses import fields

from sqlalchemy import String, and_, cast, exists, func, literal, or_, select
from sqlalchemy.orm import Session

from promo.audit.contracts import DetailAuditQuery, PageResult
from promo.history.contracts import HistoryQuery
from promo.history.presentation import HistoryItemViewModel
from promo.logs.contracts import LogsQuery
from promo.logs.presentation import LogItemViewModel
from promo.shared.contracts.audit import RunDetailAuditDTO, RunSummaryAuditDTO
from promo.shared.contracts.runs import RunFileDTO
from promo.shared.errors import ValidationFailedError
from promo.shared.persistence.models import RunDetailAuditModel, RunFileModel, RunModel, RunSummaryAuditModel, StoreModel, SystemLogModel, UserModel


def _dto_from_model(model: object, dto_type):
    return dto_type(**{field.name: getattr(model, field.name) for field in fields(dto_type)})


def _page_offset(page: int, page_size: int) -> int:
    return (page - 1) * page_size


def _pattern(value: str | None) -> str | None:
    if not value:
        return None
    return f"%{value.casefold()}%"


class SqlAlchemyHistoryQueryGateway:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_history(self, query: HistoryQuery, accessible_store_ids: tuple[int, ...] | None) -> PageResult[HistoryItemViewModel]:
        if accessible_store_ids is not None and not accessible_store_ids:
            return PageResult(items=(), total_items=0, page=query.page, page_size=query.page_size)

        stmt = (
            select(
                RunModel.id.label("run_id"),
                RunModel.public_run_number,
                RunModel.store_id,
                StoreModel.name.label("store_name"),
                StoreModel.marketplace.label("store_marketplace"),
                StoreModel.status.label("store_status"),
                RunModel.initiated_by_user_id,
                UserModel.username.label("initiated_by_username"),
                RunModel.operation_type,
                RunModel.lifecycle_status,
                RunModel.business_result,
                RunModel.module_code,
                RunModel.started_at_utc,
                RunModel.finished_at_utc,
                RunModel.short_result_text,
            )
            .select_from(RunModel)
            .join(StoreModel, StoreModel.id == RunModel.store_id)
            .join(UserModel, UserModel.id == RunModel.initiated_by_user_id)
        )
        stmt = self._apply_history_filters(stmt, query, accessible_store_ids)
        total_items = self._session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        stmt = stmt.order_by(*self._history_sort(query))
        stmt = stmt.offset(_page_offset(query.page, query.page_size)).limit(query.page_size)

        rows = self._session.execute(stmt).all()
        run_ids = [row.run_id for row in rows]
        filenames = self._load_original_filenames(run_ids)
        items = tuple(
            HistoryItemViewModel(
                run_id=row.run_id,
                public_run_number=row.public_run_number,
                store_id=row.store_id,
                store_name=row.store_name,
                store_marketplace=row.store_marketplace,
                store_status=row.store_status,
                initiated_by_user_id=row.initiated_by_user_id,
                initiated_by_username=row.initiated_by_username,
                operation_type=row.operation_type,
                lifecycle_status=row.lifecycle_status,
                business_result=row.business_result,
                module_code=row.module_code,
                started_at_utc=row.started_at_utc,
                finished_at_utc=row.finished_at_utc,
                short_result_text=row.short_result_text,
                original_filenames=filenames.get(row.run_id, ()),
            )
            for row in rows
        )
        return PageResult(items=items, total_items=total_items, page=query.page, page_size=query.page_size)

    def get_history_item_by_public_run_number(
        self,
        public_run_number: str,
        accessible_store_ids: tuple[int, ...] | None,
    ) -> HistoryItemViewModel | None:
        if accessible_store_ids is not None and not accessible_store_ids:
            return None
        stmt = (
            select(
                RunModel.id.label("run_id"),
                RunModel.public_run_number,
                RunModel.store_id,
                StoreModel.name.label("store_name"),
                StoreModel.marketplace.label("store_marketplace"),
                StoreModel.status.label("store_status"),
                RunModel.initiated_by_user_id,
                UserModel.username.label("initiated_by_username"),
                RunModel.operation_type,
                RunModel.lifecycle_status,
                RunModel.business_result,
                RunModel.module_code,
                RunModel.started_at_utc,
                RunModel.finished_at_utc,
                RunModel.short_result_text,
            )
            .select_from(RunModel)
            .join(StoreModel, StoreModel.id == RunModel.store_id)
            .join(UserModel, UserModel.id == RunModel.initiated_by_user_id)
            .where(RunModel.public_run_number == public_run_number)
            .limit(1)
        )
        if accessible_store_ids is not None:
            stmt = stmt.where(RunModel.store_id.in_(accessible_store_ids))
        row = self._session.execute(stmt).one_or_none()
        if row is None:
            return None
        filenames = self._load_original_filenames([row.run_id]).get(row.run_id, ())
        return HistoryItemViewModel(
            run_id=row.run_id,
            public_run_number=row.public_run_number,
            store_id=row.store_id,
            store_name=row.store_name,
            store_marketplace=row.store_marketplace,
            store_status=row.store_status,
            initiated_by_user_id=row.initiated_by_user_id,
            initiated_by_username=row.initiated_by_username,
            operation_type=row.operation_type,
            lifecycle_status=row.lifecycle_status,
            business_result=row.business_result,
            module_code=row.module_code,
            started_at_utc=row.started_at_utc,
            finished_at_utc=row.finished_at_utc,
            short_result_text=row.short_result_text,
            original_filenames=filenames,
        )

    def _apply_history_filters(self, stmt, query: HistoryQuery, accessible_store_ids: tuple[int, ...] | None):
        conditions = []
        if accessible_store_ids is not None:
            conditions.append(RunModel.store_id.in_(accessible_store_ids))
        if query.store_id is not None:
            conditions.append(RunModel.store_id == query.store_id)
        if query.initiated_by_user_id is not None:
            conditions.append(RunModel.initiated_by_user_id == query.initiated_by_user_id)
        if query.marketplace is not None:
            conditions.append(StoreModel.marketplace == query.marketplace)
        if query.module_code is not None:
            conditions.append(RunModel.module_code == query.module_code)
        if query.operation_type is not None:
            conditions.append(RunModel.operation_type == query.operation_type)
        if query.lifecycle_status is not None:
            conditions.append(RunModel.lifecycle_status == query.lifecycle_status)
        if query.business_result is not None:
            conditions.append(RunModel.business_result == query.business_result)
        if query.store_status is not None:
            conditions.append(StoreModel.status == query.store_status)
        if query.started_from_utc is not None:
            conditions.append(RunModel.started_at_utc >= query.started_from_utc)
        if query.started_to_utc is not None:
            conditions.append(RunModel.started_at_utc <= query.started_to_utc)
        pattern = _pattern(query.search)
        if pattern is not None:
            file_match = exists(
                select(literal(1))
                .select_from(RunFileModel)
                .where(
                    and_(
                        RunFileModel.run_id == RunModel.id,
                        func.lower(RunFileModel.original_filename).like(pattern),
                    )
                )
            )
            conditions.append(
                or_(
                    func.lower(RunModel.public_run_number).like(pattern),
                    func.lower(StoreModel.name).like(pattern),
                    func.lower(func.coalesce(RunModel.short_result_text, "")).like(pattern),
                    func.lower(UserModel.username).like(pattern),
                    file_match,
                )
            )
        if conditions:
            stmt = stmt.where(*conditions)
        return stmt

    def _history_sort(self, query: HistoryQuery) -> tuple:
        mapping = {
            "started_at_utc": RunModel.started_at_utc,
            "finished_at_utc": RunModel.finished_at_utc,
            "public_run_number": RunModel.public_run_number,
            "store_name": StoreModel.name,
            "initiated_by_username": UserModel.username,
            "operation_type": RunModel.operation_type,
            "lifecycle_status": RunModel.lifecycle_status,
            "business_result": RunModel.business_result,
        }
        column = mapping.get(query.sort_field)
        if column is None:
            raise ValidationFailedError("Unsupported history sort field", {"sort_field": query.sort_field})
        ordered = column.desc() if query.descending else column.asc()
        return (ordered, RunModel.id.desc())

    def _load_original_filenames(self, run_ids: list[int]) -> dict[int, tuple[str, ...]]:
        if not run_ids:
            return {}
        stmt = (
            select(RunFileModel.run_id, RunFileModel.original_filename)
            .where(RunFileModel.run_id.in_(run_ids))
            .order_by(RunFileModel.run_id.asc(), RunFileModel.original_filename.asc(), RunFileModel.id.asc())
        )
        grouped: dict[int, list[str]] = defaultdict(list)
        for run_id, original_filename in self._session.execute(stmt):
            grouped[run_id].append(original_filename)
        return {run_id: tuple(items) for run_id, items in grouped.items()}


class SqlAlchemyLogsQueryGateway:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_logs(self, query: LogsQuery) -> PageResult[LogItemViewModel]:
        stmt = (
            select(
                SystemLogModel.id,
                SystemLogModel.event_time_utc,
                SystemLogModel.user_id,
                UserModel.username,
                SystemLogModel.store_id,
                StoreModel.name.label("store_name"),
                SystemLogModel.run_id,
                RunModel.public_run_number,
                SystemLogModel.module_code,
                SystemLogModel.event_type,
                SystemLogModel.severity,
                SystemLogModel.message,
                SystemLogModel.payload_json,
            )
            .select_from(SystemLogModel)
            .outerjoin(UserModel, UserModel.id == SystemLogModel.user_id)
            .outerjoin(StoreModel, StoreModel.id == SystemLogModel.store_id)
            .outerjoin(RunModel, RunModel.id == SystemLogModel.run_id)
        )
        stmt = self._apply_logs_filters(stmt, query)
        total_items = self._session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        stmt = stmt.order_by(*self._logs_sort(query))
        stmt = stmt.offset(_page_offset(query.page, query.page_size)).limit(query.page_size)
        rows = self._session.execute(stmt).all()
        items = tuple(
            LogItemViewModel(
                id=row.id,
                event_time_utc=row.event_time_utc,
                user_id=row.user_id,
                username=row.username,
                store_id=row.store_id,
                store_name=row.store_name,
                run_id=row.run_id,
                public_run_number=row.public_run_number,
                module_code=row.module_code,
                event_type=row.event_type,
                severity=row.severity,
                message=row.message,
                payload_json=row.payload_json,
            )
            for row in rows
        )
        return PageResult(items=items, total_items=total_items, page=query.page, page_size=query.page_size)

    def _apply_logs_filters(self, stmt, query: LogsQuery):
        conditions = []
        if query.user_id is not None:
            conditions.append(SystemLogModel.user_id == query.user_id)
        if query.store_id is not None:
            conditions.append(SystemLogModel.store_id == query.store_id)
        if query.module_code is not None:
            conditions.append(SystemLogModel.module_code == query.module_code)
        if query.event_type is not None:
            conditions.append(SystemLogModel.event_type == query.event_type)
        if query.severity is not None:
            conditions.append(SystemLogModel.severity == query.severity)
        if query.run_id is not None:
            conditions.append(SystemLogModel.run_id == query.run_id)
        if query.public_run_number is not None:
            conditions.append(RunModel.public_run_number == query.public_run_number)
        if query.event_from_utc is not None:
            conditions.append(SystemLogModel.event_time_utc >= query.event_from_utc)
        if query.event_to_utc is not None:
            conditions.append(SystemLogModel.event_time_utc <= query.event_to_utc)
        pattern = _pattern(query.search)
        if pattern is not None:
            conditions.append(
                or_(
                    func.lower(SystemLogModel.message).like(pattern),
                    func.lower(func.coalesce(UserModel.username, "")).like(pattern),
                    func.lower(func.coalesce(RunModel.public_run_number, "")).like(pattern),
                )
            )
        if conditions:
            stmt = stmt.where(*conditions)
        return stmt

    def _logs_sort(self, query: LogsQuery) -> tuple:
        mapping = {
            "event_time_utc": SystemLogModel.event_time_utc,
            "severity": SystemLogModel.severity,
            "event_type": SystemLogModel.event_type,
            "username": UserModel.username,
            "store_name": StoreModel.name,
        }
        column = mapping.get(query.sort_field)
        if column is None:
            raise ValidationFailedError("Unsupported logs sort field", {"sort_field": query.sort_field})
        ordered = column.desc() if query.descending else column.asc()
        return (ordered, SystemLogModel.id.desc())


class SqlAlchemyAuditQueryGateway:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_detail_audit(self, run_id: int, query: DetailAuditQuery) -> PageResult[RunDetailAuditDTO]:
        stmt = select(RunDetailAuditModel).where(RunDetailAuditModel.run_id == run_id)
        stmt = self._apply_detail_filters(stmt, query)
        total_items = self._session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        stmt = stmt.order_by(*self._detail_sort(query))
        stmt = stmt.offset(_page_offset(query.page, query.page_size)).limit(query.page_size)
        items = tuple(
            _dto_from_model(model, RunDetailAuditDTO)
            for model in self._session.scalars(stmt).all()
        )
        return PageResult(items=items, total_items=total_items, page=query.page, page_size=query.page_size)

    def get_summary_audit(self, run_id: int) -> RunSummaryAuditDTO | None:
        stmt = select(RunSummaryAuditModel).where(RunSummaryAuditModel.run_id == run_id).order_by(RunSummaryAuditModel.id.desc()).limit(1)
        model = self._session.scalar(stmt)
        if model is None:
            return None
        return _dto_from_model(model, RunSummaryAuditDTO)

    def list_run_files(self, run_id: int) -> tuple[RunFileDTO, ...]:
        stmt = select(RunFileModel).where(RunFileModel.run_id == run_id).order_by(RunFileModel.id.asc())
        return tuple(_dto_from_model(model, RunFileDTO) for model in self._session.scalars(stmt).all())

    def _apply_detail_filters(self, stmt, query: DetailAuditQuery):
        conditions = []
        if query.severity is not None:
            conditions.append(RunDetailAuditModel.severity == query.severity)
        if query.decision_reason is not None:
            conditions.append(RunDetailAuditModel.decision_reason == query.decision_reason)
        if query.row_number_from is not None:
            conditions.append(RunDetailAuditModel.row_number >= query.row_number_from)
        if query.row_number_to is not None:
            conditions.append(RunDetailAuditModel.row_number <= query.row_number_to)
        if query.has_entity_key_1 is True:
            conditions.append(RunDetailAuditModel.entity_key_1.is_not(None))
        if query.has_entity_key_1 is False:
            conditions.append(RunDetailAuditModel.entity_key_1.is_(None))
        pattern = _pattern(query.search)
        if pattern is not None:
            conditions.append(
                or_(
                    cast(RunDetailAuditModel.row_number, String).like(pattern),
                    func.lower(func.coalesce(RunDetailAuditModel.entity_key_1, "")).like(pattern),
                    func.lower(func.coalesce(RunDetailAuditModel.entity_key_2, "")).like(pattern),
                    func.lower(RunDetailAuditModel.message).like(pattern),
                    func.lower(func.coalesce(RunDetailAuditModel.decision_reason, "")).like(pattern),
                )
            )
        if conditions:
            stmt = stmt.where(*conditions)
        return stmt

    def _detail_sort(self, query: DetailAuditQuery) -> tuple:
        mapping = {
            "row_number": RunDetailAuditModel.row_number,
            "severity": RunDetailAuditModel.severity,
            "decision_reason": RunDetailAuditModel.decision_reason,
            "entity_key_1": RunDetailAuditModel.entity_key_1,
        }
        column = mapping.get(query.sort_field)
        if column is None:
            raise ValidationFailedError("Unsupported audit sort field", {"sort_field": query.sort_field})
        ordered = column.desc() if query.descending else column.asc()
        return (ordered, RunDetailAuditModel.id.asc())
