from promo.shared.enums import ErrorCode, MarketplaceCode, ModuleCode, OperationType


def test_closed_enums_exist() -> None:
    assert MarketplaceCode.WB.value == "wb"
    assert ModuleCode.OZON.value == "ozon"
    assert OperationType.CHECK.value == "check"
    assert ErrorCode.ACTIVE_RUN_CONFLICT.value == "active_run_conflict"
