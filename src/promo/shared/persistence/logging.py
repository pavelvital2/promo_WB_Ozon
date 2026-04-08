from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from promo.shared.clock import utc_now
from promo.shared.contracts.logs import SystemLogDTO
from promo.shared.persistence.repositories import SystemLogRepository


class RepositoryLogger:
    def __init__(
        self,
        repository: SystemLogRepository,
        clock: Callable[[], datetime] = utc_now,
        fallback: logging.Logger | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._fallback = fallback or logging.getLogger(__name__)

    def info(self, message: str, *args) -> None:
        self._write("info", message, *args)

    def warning(self, message: str, *args) -> None:
        self._write("warning", message, *args)

    def error(self, message: str, *args) -> None:
        self._write("error", message, *args)

    def exception(self, message: str, *args) -> None:
        self._write("error", message, *args)

    def _write(self, severity: str, message: str, *args) -> None:
        rendered = message % args if args else message
        event_type, payload = self._parse_message(rendered)
        log_record = SystemLogDTO(
            id=self._next_id(),
            event_time_utc=self._clock(),
            user_id=self._parse_optional_int(payload.pop("user_id", None)),
            store_id=self._parse_optional_int(payload.pop("store_id", None)),
            run_id=self._parse_optional_int(payload.pop("run_id", None)),
            module_code=self._parse_optional_text(payload.pop("module_code", None)),
            event_type=event_type,
            severity=severity,
            message=rendered,
            payload_json=payload or None,
        )
        self._repository.add(log_record)
        self._fallback.log(self._to_level(severity), rendered)

    def _next_id(self) -> int:
        return max((item.id for item in self._repository.list()), default=0) + 1

    def _parse_message(self, rendered: str) -> tuple[str, dict[str, object]]:
        if not rendered:
            return "system.unknown", {}
        tokens = rendered.split()
        event_type = tokens[0]
        payload: dict[str, object] = {}
        for token in tokens[1:]:
            if "=" not in token:
                continue
            key, raw_value = token.split("=", 1)
            payload[key] = raw_value
        return event_type, payload

    def _parse_optional_int(self, value: object | None) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(str(value))
        except ValueError:
            return None

    def _parse_optional_text(self, value: object | None) -> str | None:
        if value in (None, ""):
            return None
        return str(value)

    def _to_level(self, severity: str) -> int:
        if severity == "warning":
            return logging.WARNING
        if severity == "error":
            return logging.ERROR
        return logging.INFO
