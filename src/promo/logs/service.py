from __future__ import annotations

from promo.access.contracts import SessionContextDTO
from promo.access.policy import AccessPolicy
from promo.audit.contracts import ALLOWED_PAGE_SIZES, PageResult
from promo.logs.contracts import LogsQuery, LogsReadDependencies
from promo.logs.presentation import LogItemViewModel, LogsPageViewModel
from promo.shared.contracts.logs import SystemLogDTO
from promo.shared.errors import AccessDeniedError, ValidationFailedError


class LogsReadService:
    def __init__(self, dependencies: LogsReadDependencies, policy: AccessPolicy | None = None) -> None:
        self._dependencies = dependencies
        self._policy = policy or AccessPolicy()

    def list_logs(self, context: SessionContextDTO, query: LogsQuery) -> LogsPageViewModel:
        decision = self._policy.can_view_logs(context)
        if not decision.allowed:
            raise AccessDeniedError("Logs are admin-only", decision.details)

        self._validate_pagination(query.page, query.page_size)
        query_gateway = self._dependencies.query_gateway
        if query_gateway is not None:
            page_result = query_gateway.list_logs(query)
            return LogsPageViewModel(
                items=page_result.items,
                total_items=page_result.total_items,
                page=page_result.page,
                page_size=page_result.page_size,
            )

        items = list(self._dependencies.logs.list())
        items = self._apply_filters(items, query)
        items = self._apply_search(items, query.search)
        items = self._apply_sort(items, query)
        page_result = self._paginate(items, query.page, query.page_size)
        return LogsPageViewModel(
            items=tuple(self._to_item(item) for item in page_result.items),
            total_items=page_result.total_items,
            page=page_result.page,
            page_size=page_result.page_size,
        )

    def _apply_filters(self, items: list[SystemLogDTO], query: LogsQuery) -> list[SystemLogDTO]:
        filtered: list[SystemLogDTO] = []
        for item in items:
            if query.user_id is not None and item.user_id != query.user_id:
                continue
            if query.store_id is not None and item.store_id != query.store_id:
                continue
            if query.module_code is not None and item.module_code != query.module_code:
                continue
            if query.event_type is not None and item.event_type != query.event_type:
                continue
            if query.severity is not None and item.severity != query.severity:
                continue
            if query.run_id is not None and item.run_id != query.run_id:
                continue
            if query.public_run_number is not None:
                run = None if item.run_id is None else self._dependencies.runs.get(item.run_id)
                if run is None or run.public_run_number != query.public_run_number:
                    continue
            if query.event_from_utc is not None and item.event_time_utc < query.event_from_utc:
                continue
            if query.event_to_utc is not None and item.event_time_utc > query.event_to_utc:
                continue
            filtered.append(item)
        return filtered

    def _apply_search(self, items: list[SystemLogDTO], search: str | None) -> list[SystemLogDTO]:
        if not search:
            return items
        needle = search.casefold()
        result: list[SystemLogDTO] = []
        for item in items:
            user = None if item.user_id is None else self._dependencies.users.get(item.user_id)
            run = None if item.run_id is None else self._dependencies.runs.get(item.run_id)
            haystack = (
                item.message,
                "" if user is None else user.username,
                "" if run is None else run.public_run_number,
            )
            if any(needle in value.casefold() for value in haystack):
                result.append(item)
        return result

    def _apply_sort(self, items: list[SystemLogDTO], query: LogsQuery) -> list[SystemLogDTO]:
        field = query.sort_field or "event_time_utc"
        allowed = {"event_time_utc", "severity", "event_type", "username", "store_name"}
        if field not in allowed:
            raise ValidationFailedError("Unsupported logs sort field", {"sort_field": field})
        return sorted(items, key=lambda item: self._sort_value(item, field), reverse=query.descending)

    def _sort_value(self, item: SystemLogDTO, field: str):
        if field == "event_time_utc":
            return item.event_time_utc
        if field == "severity":
            return item.severity
        if field == "event_type":
            return item.event_type
        if field == "username":
            user = None if item.user_id is None else self._dependencies.users.get(item.user_id)
            return "" if user is None else user.username
        store = None if item.store_id is None else self._dependencies.stores.get(item.store_id)
        return "" if store is None else store.name

    def _paginate(self, items: list[SystemLogDTO], page: int, page_size: int) -> PageResult[SystemLogDTO]:
        self._validate_pagination(page, page_size)
        total = len(items)
        offset = (page - 1) * page_size
        return PageResult(items=tuple(items[offset:offset + page_size]), total_items=total, page=page, page_size=page_size)

    def _validate_pagination(self, page: int, page_size: int) -> None:
        if page < 1:
            raise ValidationFailedError("Page must be >= 1", {"page": page})
        if page_size not in ALLOWED_PAGE_SIZES:
            raise ValidationFailedError("Unsupported page size", {"page_size": page_size})

    def _to_item(self, item: SystemLogDTO) -> LogItemViewModel:
        user = None if item.user_id is None else self._dependencies.users.get(item.user_id)
        store = None if item.store_id is None else self._dependencies.stores.get(item.store_id)
        run = None if item.run_id is None else self._dependencies.runs.get(item.run_id)
        return LogItemViewModel(
            id=item.id,
            event_time_utc=item.event_time_utc,
            user_id=item.user_id,
            username=None if user is None else user.username,
            store_id=item.store_id,
            store_name=None if store is None else store.name,
            run_id=item.run_id,
            public_run_number=None if run is None else run.public_run_number,
            module_code=item.module_code,
            event_type=item.event_type,
            severity=item.severity,
            message=item.message,
            payload_json=item.payload_json,
        )
