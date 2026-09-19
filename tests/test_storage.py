from app.storage import DuplicateBarcodeError, InventoryStore, SEED_CATALOG


def test_seed_loads_expected_count():
    store = InventoryStore(seed=True)
    items = store.all()
    assert len(items) == len(SEED_CATALOG)
    assert items[0]["id"] == 1
    assert all(item["id"] for item in items)


def test_create_get_update_delete_round_trip():
    store = InventoryStore(seed=False)
    created = store.create({"name": "Oat Milk", "quantity": 6, "price": 4.25, "brand": "Oatly"})
    assert created["id"] == 1
    assert store.get(1)["name"] == "Oat Milk"

    updated = store.update(1, {"quantity": 2, "price": 3.75})
    assert updated["quantity"] == 2
    assert updated["price"] == 3.75
    assert updated["name"] == "Oat Milk"

    assert store.delete(1) is True
    assert store.get(1) is None
    assert store.delete(1) is False


def test_duplicate_barcode_is_rejected():
    store = InventoryStore(seed=False)
    store.create({"name": "Cola", "barcode": "123", "quantity": 1, "price": 1.0})
    try:
        store.create({"name": "Other Cola", "barcode": "123", "quantity": 1, "price": 1.0})
        assert False, "expected DuplicateBarcodeError"
    except DuplicateBarcodeError as exc:
        assert exc.existing["id"] == 1


def test_low_stock_threshold():
    store = InventoryStore(seed=False)
    store.create({"name": "High", "quantity": 20, "price": 1})
    store.create({"name": "Low", "quantity": 2, "price": 1})
    low = store.low_stock(5)
    assert len(low) == 1
    assert low[0]["name"] == "Low"
