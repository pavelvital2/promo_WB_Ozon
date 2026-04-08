from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from promo.access.policy import AccessPolicy
from promo.access.service import AccessService, AccessServiceDependencies
from promo.audit.contracts import AuditReadDependencies
from promo.audit.service import AuditReadService
from promo.auth.contracts import SessionStore
from promo.auth.service import AuthService, InMemorySessionStore
from promo.file_storage.service import FileStorageService
from promo.history.contracts import HistoryReadDependencies
from promo.history.service import HistoryReadService
from promo.logs.contracts import LogsReadDependencies
from promo.logs.service import LogsReadService
from promo.runs.contracts import RunExecutionStrategy, RunServiceDependencies
from promo.runs.service import InMemoryRunLockManager, MarketplaceRunExecutionStrategy, RunExecutionQueue, RunService
from promo.shared.clock import utc_now
from promo.shared.config import AppConfig, load_config
from promo.shared.db import build_engine, build_session_factory
from promo.shared.logging import get_logger
from promo.shared.persistence.base import Base
from promo.shared.persistence.logging import RepositoryLogger
from promo.shared.persistence.read_queries import SqlAlchemyAuditQueryGateway, SqlAlchemyHistoryQueryGateway, SqlAlchemyLogsQueryGateway
from promo.shared.persistence.uow import RepositoryRegistry, SqlAlchemyUnitOfWork, SqlAlchemyUnitOfWorkFactory
from promo.shared.security.passwords import PasswordHasher, ScryptPasswordHasher
from promo.stores.contracts import StoreServiceDependencies
from promo.stores.service import StoresService
from promo.temp_files.contracts import TemporaryFileServiceDependencies
from promo.temp_files.service import TemporaryFileService
from promo.users.contracts import UserDirectoryDependencies
from promo.users.service import UserDirectoryService, UserManagementService


@dataclass(slots=True)
class ServiceBundle:
    uow: SqlAlchemyUnitOfWork
    user_directory: UserDirectoryService
    users: UserManagementService
    auth: AuthService
    access: AccessService
    stores: StoresService
    temp_files: TemporaryFileService
    runs: RunService
    audit: AuditReadService
    history: HistoryReadService
    logs: LogsReadService


@dataclass(slots=True)
class PersistenceAppContext:
    engine: Engine
    session_factory: sessionmaker[Session]
    uow_factory: SqlAlchemyUnitOfWorkFactory
    file_storage: FileStorageService
    policy: AccessPolicy
    password_hasher: PasswordHasher
    session_store: SessionStore
    run_lock_manager: InMemoryRunLockManager
    run_queue: RunExecutionQueue
    execution_strategy_factory: Callable[[FileStorageService], RunExecutionStrategy]
    clock: Callable[[], datetime]

    def build_services(self) -> ServiceBundle:
        uow = self.uow_factory()
        return build_service_bundle(
            uow=uow,
            file_storage=self.file_storage,
            policy=self.policy,
            password_hasher=self.password_hasher,
            session_store=self.session_store,
            run_lock_manager=self.run_lock_manager,
            run_queue=self.run_queue,
            execution_strategy=self.execution_strategy_factory(self.file_storage),
            clock=self.clock,
        )

    @contextmanager
    def request_scope(self, commit: bool = False) -> Iterator[ServiceBundle]:
        bundle = self.build_services()
        try:
            yield bundle
            if commit:
                bundle.uow.commit()
            else:
                bundle.uow.rollback()
        except Exception:
            bundle.uow.rollback()
            raise
        finally:
            bundle.uow.close()


def create_schema(engine: Engine) -> None:
    # Import models so SQLAlchemy metadata is fully populated before create_all.
    from promo.shared.persistence import models as _models  # noqa: F401

    Base.metadata.create_all(engine)


def build_app_context(
    config: AppConfig | None = None,
    *,
    file_storage_root: Path | None = None,
    clock: Callable[[], datetime] = utc_now,
    session_store: SessionStore | None = None,
    password_hasher: PasswordHasher | None = None,
    execution_strategy_factory: Callable[[FileStorageService], RunExecutionStrategy] | None = None,
) -> PersistenceAppContext:
    resolved = config or load_config()
    engine = build_engine(resolved.database.dsn)
    session_factory = build_session_factory(engine)
    return PersistenceAppContext(
        engine=engine,
        session_factory=session_factory,
        uow_factory=SqlAlchemyUnitOfWorkFactory(session_factory),
        file_storage=FileStorageService(file_storage_root or resolved.storage.root_path),
        policy=AccessPolicy(),
        password_hasher=password_hasher or ScryptPasswordHasher(),
        session_store=session_store or InMemorySessionStore(),
        run_lock_manager=InMemoryRunLockManager(),
        run_queue=RunExecutionQueue(),
        execution_strategy_factory=execution_strategy_factory or (lambda storage: MarketplaceRunExecutionStrategy(storage)),
        clock=clock,
    )


def build_service_bundle(
    *,
    uow: SqlAlchemyUnitOfWork,
    file_storage: FileStorageService,
    policy: AccessPolicy,
    password_hasher: PasswordHasher,
    session_store: SessionStore,
    run_lock_manager: InMemoryRunLockManager,
    run_queue: RunExecutionQueue,
    execution_strategy: RunExecutionStrategy,
    clock: Callable[[], datetime] = utc_now,
) -> ServiceBundle:
    repos = uow.repositories
    user_directory = _build_user_directory(repos, clock=clock)
    logger = RepositoryLogger(repos.logs, clock=clock, fallback=get_logger("promo.persistence"))
    return ServiceBundle(
        uow=uow,
        user_directory=user_directory,
        users=UserManagementService(
            UserDirectoryDependencies(
                users=repos.users,
                roles=repos.roles,
                permissions=repos.permissions,
                user_permissions=repos.user_permissions,
                stores=repos.stores,
                user_store_access=repos.user_store_access,
            ),
            password_hasher=password_hasher,
            policy=policy,
            clock=clock,
            logger=logger,
        ),
        auth=AuthService(
            user_directory=user_directory,
            session_store=session_store,
            password_hasher=password_hasher,
            policy=policy,
            clock=clock,
            logger=logger,
        ),
        access=AccessService(
            AccessServiceDependencies(
                users=repos.users,
                stores=repos.stores,
                user_store_access=repos.user_store_access,
                user_directory=user_directory,
            ),
            policy=policy,
            clock=clock,
            logger=logger,
        ),
        stores=StoresService(
            StoreServiceDependencies(
                stores=repos.stores,
                user_store_access=repos.user_store_access,
            ),
            policy=policy,
            clock=clock,
            logger=logger,
        ),
        temp_files=TemporaryFileService(
            TemporaryFileServiceDependencies(
                temporary_files=repos.temporary_files,
                file_storage=file_storage,
            ),
            clock=clock,
            logger=logger,
        ),
        runs=RunService(
            RunServiceDependencies(
                runs=repos.runs,
                run_files=repos.run_files,
                run_summary_audits=repos.run_summary_audits,
                run_detail_audits=repos.run_detail_audits,
                stores=repos.stores,
                temporary_files=repos.temporary_files,
                file_storage=file_storage,
            ),
            policy=policy,
            clock=clock,
            lock_manager=run_lock_manager,
            queue=run_queue,
            execution_strategy=execution_strategy,
            logger=logger,
        ),
        audit=AuditReadService(
            AuditReadDependencies(
                runs=repos.runs,
                run_files=repos.run_files,
                run_summary_audits=repos.run_summary_audits,
                run_detail_audits=repos.run_detail_audits,
                stores=repos.stores,
                users=repos.users,
                query_gateway=SqlAlchemyAuditQueryGateway(uow.session),
            ),
            policy=policy,
        ),
        history=HistoryReadService(
            HistoryReadDependencies(
                runs=repos.runs,
                run_files=repos.run_files,
                stores=repos.stores,
                users=repos.users,
                query_gateway=SqlAlchemyHistoryQueryGateway(uow.session),
            ),
            policy=policy,
        ),
        logs=LogsReadService(
            LogsReadDependencies(
                logs=repos.logs,
                runs=repos.runs,
                stores=repos.stores,
                users=repos.users,
                query_gateway=SqlAlchemyLogsQueryGateway(uow.session),
            ),
            policy=policy,
        ),
    )


def _build_user_directory(repositories: RepositoryRegistry, *, clock: Callable[[], datetime]) -> UserDirectoryService:
    return UserDirectoryService(
        UserDirectoryDependencies(
            users=repositories.users,
            roles=repositories.roles,
            permissions=repositories.permissions,
            user_permissions=repositories.user_permissions,
            stores=repositories.stores,
            user_store_access=repositories.user_store_access,
        ),
        clock=clock,
    )
