from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import MetaData
from sqlalchemy.dialects import postgresql


def enum_types() -> dict[str, postgresql.ENUM]:
    return {
        "marketplace_code": postgresql.ENUM("wb", "ozon", name="marketplace_code", create_type=False),
        "store_status": postgresql.ENUM("active", "archived", name="store_status", create_type=False),
        "module_code": postgresql.ENUM("wb", "ozon", name="module_code", create_type=False),
        "operation_type": postgresql.ENUM("check", "process", name="operation_type", create_type=False),
        "run_lifecycle_status": postgresql.ENUM(
            "created",
            "checking",
            "validating",
            "processing",
            "completed",
            "failed",
            name="run_lifecycle_status",
            create_type=False,
        ),
        "business_result": postgresql.ENUM(
            "check_passed",
            "check_passed_with_warnings",
            "check_failed",
            "validation_failed",
            "completed",
            "completed_with_warnings",
            "failed",
            name="business_result",
            create_type=False,
        ),
        "file_role": postgresql.ENUM(
            "wb_price_input",
            "wb_promo_input",
            "wb_result_output",
            "ozon_input",
            "ozon_result_output",
            name="file_role",
            create_type=False,
        ),
        "severity": postgresql.ENUM("info", "warning", "error", name="severity", create_type=False),
        "unavailable_reason": postgresql.ENUM(
            "expired",
            "superseded",
            "deleted_by_retention_rule",
            name="unavailable_reason",
            create_type=False,
        ),
    }


def create_all_types(bind) -> None:
    for enum_type in enum_types().values():
        enum_type.create(bind, checkfirst=True)


def drop_all_types(bind) -> None:
    for enum_type in reversed(list(enum_types().values())):
        enum_type.drop(bind, checkfirst=True)

