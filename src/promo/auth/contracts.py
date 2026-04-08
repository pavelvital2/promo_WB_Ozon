from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from promo.access.contracts import SessionContextDTO


@dataclass(slots=True, frozen=True)
class SessionRecordDTO:
    token: str
    user_id: int
    issued_at_utc: datetime
    last_seen_at_utc: datetime


@dataclass(slots=True, frozen=True)
class LoginResultDTO:
    session_token: str
    context: SessionContextDTO


@dataclass(slots=True, frozen=True)
class PasswordChangeResultDTO:
    user_id: int
    changed_at_utc: datetime


@runtime_checkable
class SessionStore(Protocol):
    def create(self, session: SessionRecordDTO) -> SessionRecordDTO: ...

    def get(self, token: str) -> SessionRecordDTO | None: ...

    def update(self, session: SessionRecordDTO) -> SessionRecordDTO: ...

    def delete(self, token: str) -> None: ...

    def list(self) -> tuple[SessionRecordDTO, ...]: ...

