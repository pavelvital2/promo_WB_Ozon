from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True, frozen=True)
class PageRequestDTO:
    page: int = 1
    page_size: int = 50


@dataclass(slots=True, frozen=True)
class SortSpecDTO:
    field: str
    descending: bool = True


@dataclass(slots=True, frozen=True)
class PageResultDTO(Generic[T]):
    items: list[T]
    total_items: int
    page: int
    page_size: int


@dataclass(slots=True, frozen=True)
class ErrorResponseDTO:
    error_code: str
    error_message: str
    details: dict[str, object]
