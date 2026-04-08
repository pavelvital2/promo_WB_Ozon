from __future__ import annotations

import secrets
from dataclasses import replace

from promo.access.contracts import SessionContextDTO
from promo.access.policy import AccessPolicy, SessionContextInputDTO
from promo.auth.contracts import LoginResultDTO, PasswordChangeResultDTO, SessionRecordDTO, SessionStore
from promo.shared.clock import utc_now
from promo.shared.errors import AccessDeniedError, ValidationFailedError
from promo.shared.logging import get_logger
from promo.shared.security.passwords import PasswordHasher, ScryptPasswordHasher
from promo.users.contracts import UserIdentitySnapshotDTO
from promo.users.service import UserDirectoryService


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecordDTO] = {}

    def create(self, session: SessionRecordDTO) -> SessionRecordDTO:
        self._sessions[session.token] = session
        return session

    def get(self, token: str) -> SessionRecordDTO | None:
        return self._sessions.get(token)

    def update(self, session: SessionRecordDTO) -> SessionRecordDTO:
        self._sessions[session.token] = session
        return session

    def delete(self, token: str) -> None:
        self._sessions.pop(token, None)

    def list(self) -> tuple[SessionRecordDTO, ...]:
        return tuple(self._sessions.values())


class AuthService:
    def __init__(
        self,
        user_directory: UserDirectoryService,
        session_store: SessionStore,
        password_hasher: PasswordHasher | None = None,
        policy: AccessPolicy | None = None,
        clock=utc_now,
        logger=None,
    ) -> None:
        self._user_directory = user_directory
        self._session_store = session_store
        self._password_hasher = password_hasher or ScryptPasswordHasher()
        self._policy = policy or AccessPolicy()
        self._clock = clock
        self._logger = logger or get_logger(__name__)

    def login(self, username: str, password: str) -> LoginResultDTO:
        try:
            identity = self._load_identity_or_deny(username)
            if identity.user.is_blocked:
                raise AccessDeniedError("User is blocked", {"username": username, "auth_reason": "blocked_user"})
            if not self._password_hasher.verify_password(password, identity.user.password_hash):
                raise AccessDeniedError("Invalid credentials", {"username": username, "auth_reason": "invalid_credentials"})
        except AccessDeniedError as exc:
            self._logger.warning(
                "failed_login username=%s auth_reason=%s",
                username,
                exc.details.get("auth_reason", "access_denied") if isinstance(exc.details, dict) else "access_denied",
            )
            raise

        now = self._clock()
        self._user_directory.mark_last_login(identity.user.id)
        context = self._policy.build_session_context(
            SessionContextInputDTO(
                user=identity.user,
                role=identity.role,
                permissions=identity.permissions,
                accessible_stores=identity.accessible_stores,
            )
        )
        record = SessionRecordDTO(
            token=secrets.token_urlsafe(32),
            user_id=identity.user.id,
            issued_at_utc=now,
            last_seen_at_utc=now,
        )
        self._session_store.create(record)
        self._logger.info("successful_login user_id=%s username=%s", identity.user.id, identity.user.username)
        return LoginResultDTO(session_token=record.token, context=context)

    def logout(self, session_token: str) -> None:
        session = self._session_store.get(session_token)
        self._session_store.delete(session_token)
        if session is not None:
            self._logger.info("logout user_id=%s session_token=%s", session.user_id, session_token)
        else:
            self._logger.warning("logout_missing_session session_token=%s", session_token)

    def current_session_context(self, session_token: str) -> SessionContextDTO:
        session = self._session_store.get(session_token)
        if session is None:
            raise AccessDeniedError("Invalid session", {"session_token": session_token})

        identity = self._user_directory.load_identity(session.user_id)
        if identity is None:
            raise AccessDeniedError("Invalid session", {"session_token": session_token})
        if identity.user.is_blocked:
            raise AccessDeniedError("User is blocked", {"user_id": identity.user.id})

        self._session_store.update(replace(session, last_seen_at_utc=self._clock()))
        return self._policy.build_session_context(
            SessionContextInputDTO(
                user=identity.user,
                role=identity.role,
                permissions=identity.permissions,
                accessible_stores=identity.accessible_stores,
            )
        )

    def change_own_password(self, session_token: str, current_password: str, new_password: str) -> PasswordChangeResultDTO:
        session = self._session_store.get(session_token)
        if session is None:
            raise AccessDeniedError("Invalid session", {"session_token": session_token})

        identity = self._user_directory.load_identity(session.user_id)
        if identity is None:
            raise AccessDeniedError("Invalid session", {"session_token": session_token})
        if identity.user.is_blocked:
            raise AccessDeniedError("User is blocked", {"user_id": identity.user.id})
        if not self._password_hasher.verify_password(current_password, identity.user.password_hash):
            raise AccessDeniedError("Invalid current password", {"user_id": identity.user.id})
        if not new_password.strip():
            raise ValidationFailedError("New password is required", {"user_id": identity.user.id})

        self._user_directory.change_password(identity.user.id, self._password_hasher.hash_password(new_password))
        return PasswordChangeResultDTO(user_id=identity.user.id, changed_at_utc=self._clock())

    def _load_identity_or_deny(self, username: str) -> UserIdentitySnapshotDTO:
        identity = self._user_directory.load_identity_by_username(username)
        if identity is None:
            raise AccessDeniedError("Invalid credentials", {"username": username})
        return identity
