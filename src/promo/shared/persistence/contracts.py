from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar, runtime_checkable

ModelT = TypeVar("ModelT")
KeyT = TypeVar("KeyT")


@runtime_checkable
class ReadRepository(Protocol[ModelT, KeyT]):
    def get(self, key: KeyT) -> ModelT | None: ...

    def list(self) -> Sequence[ModelT]: ...


@runtime_checkable
class WriteRepository(Protocol[ModelT]):
    def add(self, entity: ModelT) -> ModelT: ...

    def add_many(self, entities: Iterable[ModelT]) -> Sequence[ModelT]: ...

    def update(self, entity: ModelT) -> ModelT: ...


@runtime_checkable
class Repository(ReadRepository[ModelT, KeyT], WriteRepository[ModelT], Protocol[ModelT, KeyT]):
    def delete(self, key: KeyT) -> None: ...


@runtime_checkable
class UnitOfWork(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...
