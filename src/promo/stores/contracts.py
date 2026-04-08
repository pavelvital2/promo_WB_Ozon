from __future__ import annotations

from dataclasses import dataclass

from promo.shared.contracts.stores import StoreDTO, UserStoreAccessDTO
from promo.shared.persistence.contracts import Repository


@dataclass(slots=True, frozen=True)
class StoreServiceDependencies:
    stores: Repository[StoreDTO, int]
    user_store_access: Repository[UserStoreAccessDTO, int]

