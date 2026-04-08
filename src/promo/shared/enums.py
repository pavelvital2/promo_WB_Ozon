from __future__ import annotations

from enum import StrEnum


class MarketplaceCode(StrEnum):
    WB = "wb"
    OZON = "ozon"


class StoreStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class RoleCode(StrEnum):
    ADMIN = "admin"
    MANAGER_LEAD = "manager_lead"
    MANAGER = "manager"


class PermissionCode(StrEnum):
    CREATE_STORE = "create_store"
    EDIT_STORE = "edit_store"


class ModuleCode(StrEnum):
    WB = "wb"
    OZON = "ozon"


class OperationType(StrEnum):
    CHECK = "check"
    PROCESS = "process"


class RunLifecycleStatus(StrEnum):
    CREATED = "created"
    CHECKING = "checking"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BusinessResult(StrEnum):
    CHECK_PASSED = "check_passed"
    CHECK_PASSED_WITH_WARNINGS = "check_passed_with_warnings"
    CHECK_FAILED = "check_failed"
    VALIDATION_FAILED = "validation_failed"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class FileRole(StrEnum):
    WB_PRICE_INPUT = "wb_price_input"
    WB_PROMO_INPUT = "wb_promo_input"
    WB_RESULT_OUTPUT = "wb_result_output"
    OZON_INPUT = "ozon_input"
    OZON_RESULT_OUTPUT = "ozon_result_output"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class UnavailableReason(StrEnum):
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    DELETED_BY_RETENTION_RULE = "deleted_by_retention_rule"


class ErrorCode(StrEnum):
    ACCESS_DENIED = "access_denied"
    VALIDATION_FAILED = "validation_failed"
    SYSTEM_ERROR = "system_error"
    ARCHIVED_STORE_FORBIDDEN = "archived_store_forbidden"
    PERMISSION_DENIED = "permission_denied"
    FILE_LIMIT_EXCEEDED = "file_limit_exceeded"
    ACTIVE_RUN_CONFLICT = "active_run_conflict"

