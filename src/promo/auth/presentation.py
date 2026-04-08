from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from promo.access.presentation import SessionContextViewModel


@dataclass(slots=True, frozen=True)
class LoginForm:
    username: str
    password: str


@dataclass(slots=True, frozen=True)
class ChangeOwnPasswordForm:
    current_password: str
    new_password: str


@dataclass(slots=True, frozen=True)
class AuthSessionViewModel:
    session_token: str
    context: SessionContextViewModel


@dataclass(slots=True, frozen=True)
class PasswordChangeViewModel:
    user_id: int
    changed_at_utc: datetime
