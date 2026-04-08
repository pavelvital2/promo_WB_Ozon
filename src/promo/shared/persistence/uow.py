from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from promo.shared.persistence.contracts import UnitOfWork
from promo.shared.persistence.repositories import (
    PermissionRepository,
    RoleRepository,
    RunDetailAuditRepository,
    RunFileRepository,
    RunRepository,
    RunSummaryAuditRepository,
    StoreRepository,
    SystemLogRepository,
    TemporaryUploadedFileRepository,
    UserPermissionRepository,
    UserRepository,
    UserStoreAccessRepository,
)


@dataclass(slots=True)
class RepositoryRegistry:
    roles: RoleRepository
    permissions: PermissionRepository
    users: UserRepository
    user_permissions: UserPermissionRepository
    stores: StoreRepository
    user_store_access: UserStoreAccessRepository
    temporary_files: TemporaryUploadedFileRepository
    runs: RunRepository
    run_files: RunFileRepository
    run_summary_audits: RunSummaryAuditRepository
    run_detail_audits: RunDetailAuditRepository
    logs: SystemLogRepository


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repositories = RepositoryRegistry(
            roles=RoleRepository(session),
            permissions=PermissionRepository(session),
            users=UserRepository(session),
            user_permissions=UserPermissionRepository(session),
            stores=StoreRepository(session),
            user_store_access=UserStoreAccessRepository(session),
            temporary_files=TemporaryUploadedFileRepository(session),
            runs=RunRepository(session),
            run_files=RunFileRepository(session),
            run_summary_audits=RunSummaryAuditRepository(session),
            run_detail_audits=RunDetailAuditRepository(session),
            logs=SystemLogRepository(session),
        )

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def close(self) -> None:
        self.session.close()


class SqlAlchemyUnitOfWorkFactory:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory())
