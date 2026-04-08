from __future__ import annotations

from dataclasses import dataclass

from promo.access.contracts import SessionContextDTO
from promo.access.policy import AccessPolicy
from promo.audit.contracts import ALLOWED_PAGE_SIZES, PageResult
from promo.history.contracts import HistoryQuery, HistoryReadDependencies
from promo.history.presentation import HistoryItemViewModel, HistoryPageViewModel
from promo.shared.contracts.runs import RunDTO
from promo.shared.errors import AccessDeniedError, ValidationFailedError


class HistoryReadService:
    def __init__(self, dependencies: HistoryReadDependencies, policy: AccessPolicy | None = None) -> None:
        self._dependencies = dependencies
        self._policy = policy or AccessPolicy()

    def list_history(self, context: SessionContextDTO, query: HistoryQuery) -> HistoryPageViewModel:
        visibility = self._policy.can_view_history(context)
        if not visibility.allowed:
            raise AccessDeniedError("History is not accessible", visibility.details)
        self._validate_pagination(query.page, query.page_size)
        query_gateway = self._dependencies.query_gateway
        if query_gateway is not None:
            store_scope = None if context.is_admin else tuple(item.id for item in context.accessible_stores)
            page_result = query_gateway.list_history(query, store_scope)
            return HistoryPageViewModel(
                items=page_result.items,
                total_items=page_result.total_items,
                page=page_result.page,
                page_size=page_result.page_size,
            )

        items = [run for run in self._dependencies.runs.list() if self._is_in_scope(context, run.store_id)]
        items = self._apply_filters(items, query)
        items = self._apply_search(items, query.search)
        items = self._apply_sort(items, query)
        page_result = self._paginate(items, query.page, query.page_size)
        return HistoryPageViewModel(
            items=tuple(self._to_item(run) for run in page_result.items),
            total_items=page_result.total_items,
            page=page_result.page,
            page_size=page_result.page_size,
        )

    def get_history_item_by_public_run_number(self, context: SessionContextDTO, public_run_number: str) -> HistoryItemViewModel | None:
        visibility = self._policy.can_view_history(context)
        if not visibility.allowed:
            raise AccessDeniedError("History is not accessible", visibility.details)
        query_gateway = self._dependencies.query_gateway
        if query_gateway is not None:
            store_scope = None if context.is_admin else tuple(item.id for item in context.accessible_stores)
            return query_gateway.get_history_item_by_public_run_number(public_run_number, store_scope)

        for run in self._dependencies.runs.list():
            if run.public_run_number != public_run_number:
                continue
            if not self._is_in_scope(context, run.store_id):
                continue
            return self._to_item(run)
        return None

    def _is_in_scope(self, context: SessionContextDTO, store_id: int) -> bool:
        if context.is_admin:
            return True
        return any(item.id == store_id for item in context.accessible_stores)

    def _apply_filters(self, items: list[RunDTO], query: HistoryQuery) -> list[RunDTO]:
        filtered: list[RunDTO] = []
        for item in items:
            store = self._dependencies.stores.get(item.store_id)
            if store is None:
                continue
            if query.store_id is not None and item.store_id != query.store_id:
                continue
            if query.initiated_by_user_id is not None and item.initiated_by_user_id != query.initiated_by_user_id:
                continue
            if query.marketplace is not None and store.marketplace != query.marketplace:
                continue
            if query.module_code is not None and item.module_code != query.module_code:
                continue
            if query.operation_type is not None and item.operation_type != query.operation_type:
                continue
            if query.lifecycle_status is not None and item.lifecycle_status != query.lifecycle_status:
                continue
            if query.business_result is not None and item.business_result != query.business_result:
                continue
            if query.store_status is not None and store.status != query.store_status:
                continue
            if query.started_from_utc is not None and item.started_at_utc < query.started_from_utc:
                continue
            if query.started_to_utc is not None and item.started_at_utc > query.started_to_utc:
                continue
            filtered.append(item)
        return filtered

    def _apply_search(self, items: list[RunDTO], search: str | None) -> list[RunDTO]:
        if not search:
            return items
        needle = search.casefold()
        result: list[RunDTO] = []
        for item in items:
            store = self._dependencies.stores.get(item.store_id)
            user = self._dependencies.users.get(item.initiated_by_user_id)
            filenames = self._original_filenames(item.id)
            haystack = (
                item.public_run_number,
                "" if store is None else store.name,
                item.short_result_text or "",
                "" if user is None else user.username,
                " ".join(filenames),
            )
            if any(needle in value.casefold() for value in haystack):
                result.append(item)
        return result

    def _apply_sort(self, items: list[RunDTO], query: HistoryQuery) -> list[RunDTO]:
        field = query.sort_field or "started_at_utc"
        allowed = {
            "started_at_utc",
            "finished_at_utc",
            "public_run_number",
            "store_name",
            "initiated_by_username",
            "operation_type",
            "lifecycle_status",
            "business_result",
        }
        if field not in allowed:
            raise ValidationFailedError("Unsupported history sort field", {"sort_field": field})
        return sorted(items, key=lambda item: self._sort_value(item, field), reverse=query.descending)

    def _sort_value(self, item: RunDTO, field: str):
        store = self._dependencies.stores.get(item.store_id)
        user = self._dependencies.users.get(item.initiated_by_user_id)
        if field == "started_at_utc":
            return item.started_at_utc
        if field == "finished_at_utc":
            return item.finished_at_utc or item.started_at_utc
        if field == "public_run_number":
            return item.public_run_number
        if field == "store_name":
            return "" if store is None else store.name
        if field == "initiated_by_username":
            return "" if user is None else user.username
        if field == "operation_type":
            return item.operation_type
        if field == "lifecycle_status":
            return item.lifecycle_status
        return item.business_result or ""

    def _paginate(self, items: list[RunDTO], page: int, page_size: int) -> PageResult[RunDTO]:
        self._validate_pagination(page, page_size)
        total = len(items)
        offset = (page - 1) * page_size
        return PageResult(items=tuple(items[offset:offset + page_size]), total_items=total, page=page, page_size=page_size)

    def _validate_pagination(self, page: int, page_size: int) -> None:
        if page < 1:
            raise ValidationFailedError("Page must be >= 1", {"page": page})
        if page_size not in ALLOWED_PAGE_SIZES:
            raise ValidationFailedError("Unsupported page size", {"page_size": page_size})

    def _original_filenames(self, run_id: int) -> tuple[str, ...]:
        return tuple(sorted(item.original_filename for item in self._dependencies.run_files.list() if item.run_id == run_id))

    def _to_item(self, run: RunDTO) -> HistoryItemViewModel:
        store = self._dependencies.stores.get(run.store_id)
        user = self._dependencies.users.get(run.initiated_by_user_id)
        if store is None or user is None:
            raise ValidationFailedError("History item is missing related entities", {"run_id": run.id})
        return HistoryItemViewModel(
            run_id=run.id,
            public_run_number=run.public_run_number,
            store_id=store.id,
            store_name=store.name,
            store_marketplace=store.marketplace,
            store_status=store.status,
            initiated_by_user_id=user.id,
            initiated_by_username=user.username,
            operation_type=run.operation_type,
            lifecycle_status=run.lifecycle_status,
            business_result=run.business_result,
            module_code=run.module_code,
            started_at_utc=run.started_at_utc,
            finished_at_utc=run.finished_at_utc,
            short_result_text=run.short_result_text,
            original_filenames=self._original_filenames(run.id),
        )
