from __future__ import annotations

from dataclasses import dataclass

from promo.shared.config import DEFAULT_RUN_FILE_RETENTION_DAYS, DEFAULT_TEMPORARY_FILE_TTL_HOURS


@dataclass(slots=True, frozen=True)
class TemporaryFileRetentionPolicy:
    ttl_hours: int = DEFAULT_TEMPORARY_FILE_TTL_HOURS


@dataclass(slots=True, frozen=True)
class RunFileRetentionPolicy:
    ttl_days: int = DEFAULT_RUN_FILE_RETENTION_DAYS

