from __future__ import annotations

from promo.access.contracts import SessionContextDTO
from promo.logs.contracts import LogsQuery
from promo.logs.presentation import LogsPageViewModel
from promo.logs.service import LogsReadService


def list_logs_handler(service: LogsReadService, context: SessionContextDTO, query: LogsQuery) -> LogsPageViewModel:
    return service.list_logs(context, query)
