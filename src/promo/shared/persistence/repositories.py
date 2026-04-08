from __future__ import annotations

from dataclasses import fields
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from promo.shared.contracts.audit import RunDetailAuditDTO, RunSummaryAuditDTO
from promo.shared.contracts.files import TemporaryUploadedFileDTO
from promo.shared.contracts.logs import SystemLogDTO
from promo.shared.contracts.runs import RunDTO, RunFileDTO
from promo.shared.contracts.stores import StoreDTO, UserStoreAccessDTO
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO, UserPermissionDTO
from promo.shared.persistence.models import (
    PermissionModel,
    RoleModel,
    RunDetailAuditModel,
    RunFileModel,
    RunModel,
    RunSummaryAuditModel,
    StoreModel,
    SystemLogModel,
    TemporaryUploadedFileModel,
    UserModel,
    UserPermissionModel,
    UserStoreAccessModel,
)

DTO = TypeVar("DTO")
MODEL = TypeVar("MODEL")


def _dto_values(entity: object) -> dict[str, Any]:
    return {field.name: getattr(entity, field.name) for field in fields(entity)}


def _to_dto(model: object, dto_type: type[DTO]) -> DTO:
    return dto_type(**{field.name: getattr(model, field.name) for field in fields(dto_type)})  # type: ignore[arg-type]


class SqlAlchemyRepository(Generic[DTO, MODEL]):
    def __init__(self, session: Session, model_type: type[MODEL], dto_type: type[DTO]) -> None:
        self._session = session
        self._model_type = model_type
        self._dto_type = dto_type

    def get(self, key: int) -> DTO | None:
        model = self._session.get(self._model_type, key)
        if model is None:
            return None
        return _to_dto(model, self._dto_type)

    def list(self) -> tuple[DTO, ...]:
        statement = select(self._model_type).order_by(getattr(self._model_type, "id"))
        return tuple(_to_dto(model, self._dto_type) for model in self._session.scalars(statement).all())

    def add(self, entity: DTO) -> DTO:
        model = self._model_type(**_dto_values(entity))
        self._session.add(model)
        self._session.flush()
        return _to_dto(model, self._dto_type)

    def add_many(self, entities: list[DTO]) -> tuple[DTO, ...]:
        return tuple(self.add(entity) for entity in entities)

    def update(self, entity: DTO) -> DTO:
        model = self._session.get(self._model_type, getattr(entity, "id"))
        values = _dto_values(entity)
        if model is None:
            model = self._model_type(**values)
            self._session.add(model)
        else:
            for key, value in values.items():
                setattr(model, key, value)
        self._session.flush()
        return _to_dto(model, self._dto_type)

    def delete(self, key: int) -> None:
        model = self._session.get(self._model_type, key)
        if model is None:
            return
        self._session.delete(model)
        self._session.flush()


class RoleRepository(SqlAlchemyRepository[RoleDTO, RoleModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RoleModel, RoleDTO)


class PermissionRepository(SqlAlchemyRepository[PermissionDTO, PermissionModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, PermissionModel, PermissionDTO)


class UserRepository(SqlAlchemyRepository[UserDTO, UserModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, UserModel, UserDTO)


class UserPermissionRepository(SqlAlchemyRepository[UserPermissionDTO, UserPermissionModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, UserPermissionModel, UserPermissionDTO)


class StoreRepository(SqlAlchemyRepository[StoreDTO, StoreModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StoreModel, StoreDTO)


class UserStoreAccessRepository(SqlAlchemyRepository[UserStoreAccessDTO, UserStoreAccessModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, UserStoreAccessModel, UserStoreAccessDTO)


class TemporaryUploadedFileRepository(SqlAlchemyRepository[TemporaryUploadedFileDTO, TemporaryUploadedFileModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, TemporaryUploadedFileModel, TemporaryUploadedFileDTO)


class RunRepository(SqlAlchemyRepository[RunDTO, RunModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RunModel, RunDTO)


class RunFileRepository(SqlAlchemyRepository[RunFileDTO, RunFileModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RunFileModel, RunFileDTO)


class RunSummaryAuditRepository(SqlAlchemyRepository[RunSummaryAuditDTO, RunSummaryAuditModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RunSummaryAuditModel, RunSummaryAuditDTO)


class RunDetailAuditRepository(SqlAlchemyRepository[RunDetailAuditDTO, RunDetailAuditModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RunDetailAuditModel, RunDetailAuditDTO)


class SystemLogRepository(SqlAlchemyRepository[SystemLogDTO, SystemLogModel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, SystemLogModel, SystemLogDTO)

    def add(self, entity: SystemLogDTO) -> SystemLogDTO:
        values = _dto_values(entity)
        values.pop("id", None)
        model = self._model_type(**values)
        self._session.add(model)
        self._session.flush()
        return _to_dto(model, self._dto_type)
