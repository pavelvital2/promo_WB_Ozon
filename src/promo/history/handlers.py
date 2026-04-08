from __future__ import annotations

from promo.access.contracts import SessionContextDTO
from promo.history.contracts import HistoryQuery
from promo.history.presentation import HistoryPageViewModel
from promo.history.service import HistoryReadService


def list_history_handler(service: HistoryReadService, context: SessionContextDTO, query: HistoryQuery) -> HistoryPageViewModel:
    return service.list_history(context, query)
