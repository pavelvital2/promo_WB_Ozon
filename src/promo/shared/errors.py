from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from promo.shared.enums import ErrorCode


@dataclass(slots=True)
class AppError(Exception):
    error_code: ErrorCode
    error_message: str
    details: Any | None = None
    http_status: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code.value,
            "error_message": self.error_message,
            "details": _normalize_error_details(self.details),
        }


class AccessDeniedError(AppError):
    def __init__(self, message: str = "Access denied", details: Any | None = None, *, status_code: int | None = None) -> None:
        super().__init__(ErrorCode.ACCESS_DENIED, message, details, status_code)


class ValidationFailedError(AppError):
    def __init__(self, message: str = "Validation failed", details: Any | None = None, *, status_code: int | None = None) -> None:
        super().__init__(ErrorCode.VALIDATION_FAILED, message, details, status_code)


class PermissionDeniedError(AppError):
    def __init__(self, message: str = "Permission denied", details: Any | None = None, *, status_code: int | None = None) -> None:
        super().__init__(ErrorCode.PERMISSION_DENIED, message, details, status_code)


class ArchivedStoreForbiddenError(AppError):
    def __init__(self, message: str = "Archived store forbidden", details: Any | None = None, *, status_code: int | None = None) -> None:
        super().__init__(ErrorCode.ARCHIVED_STORE_FORBIDDEN, message, details, status_code)


class ActiveRunConflictError(AppError):
    def __init__(self, message: str = "Active run conflict", details: Any | None = None, *, status_code: int | None = None) -> None:
        super().__init__(ErrorCode.ACTIVE_RUN_CONFLICT, message, details, status_code)


def _normalize_error_details(details: Any | None) -> dict[str, Any]:
    if details is None:
        return {}
    if isinstance(details, dict):
        return details
    return {"value": details}
