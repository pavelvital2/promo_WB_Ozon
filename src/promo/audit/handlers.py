from __future__ import annotations

from promo.access.contracts import SessionContextDTO
from promo.audit.contracts import DetailAuditQuery
from promo.audit.presentation import DetailAuditPageViewModel, RunPageReadModel
from promo.audit.service import AuditReadService


def list_detail_audit_handler(
    service: AuditReadService,
    context: SessionContextDTO,
    run_id: int,
    query: DetailAuditQuery,
) -> DetailAuditPageViewModel:
    return service.list_detail_audit(context, run_id, query)


def get_run_audit_page_handler(
    service: AuditReadService,
    context: SessionContextDTO,
    run_id: int,
    query: DetailAuditQuery | None = None,
) -> RunPageReadModel:
    return service.get_run_page(context, run_id, query)
