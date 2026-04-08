from __future__ import annotations

from promo.access.contracts import SessionContextDTO
from promo.runs.presentation import RunPageViewModel, RunPollingViewModel
from promo.runs.service import RunService


def create_check_run_handler(service: RunService, context: SessionContextDTO, store_id: int):
    return service.create_check_run(context, store_id)


def create_process_run_handler(service: RunService, context: SessionContextDTO, store_id: int):
    return service.create_process_run(context, store_id)


def get_run_status_handler(service: RunService, run_id: int) -> RunPollingViewModel:
    return service.get_run_status(run_id)


def get_run_page_handler(service: RunService, run_id: int) -> RunPageViewModel:
    return service.get_run_page(run_id)


def drain_pending_runs_handler(service: RunService, limit: int | None = None) -> int:
    return service.drain_pending_jobs(limit=limit)

