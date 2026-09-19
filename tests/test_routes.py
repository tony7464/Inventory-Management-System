from tests.conftest import NUTELLA


def test_health_and_index(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json()["status"] == "ok"

    index = client.get("/")
    assert index.status_code == 200
    assert "inventory" in index.get_json()


def test_crud_lifecycle(client):
    created = client.post(
        "/inventory",
        json={"name": "Oat Milk", "brand": "Oatly", "quantity": 10, "price": 3.99},
    )
    assert created.status_code == 201
    item = created.get_json()
    item_id = item["id"]
    assert item["source"] == "manual"

    listing = client.get("/inventory")
    assert listing.status_code == 200
    body = listing.get_json()
    assert body["count"] == 1
    assert body["items"][0]["name"] == "Oat Milk"

    fetched = client.get(f"/inventory/{item_id}")
    assert fetched.status_code == 200
    assert fetched.get_json()["brand"] == "Oatly"

    patched = client.patch(f"/inventory/{item_id}", json={"quantity": 4, "price": 3.5})
    assert patched.status_code == 200
    assert patched.get_json()["quantity"] == 4
    assert patched.get_json()["price"] == 3.5

    deleted = client.delete(f"/inventory/{item_id}")
    assert deleted.status_code == 200
    assert client.get(f"/inventory/{item_id}").status_code == 404


def test_get_missing_item(client):
    response = client.get("/inventory/99")
    assert response.status_code == 404
    assert "not found" in response.get_json()["error"].lower()


def test_create_requires_name(client):
    response = client.post("/inventory", json={"quantity": 1, "price": 1})
    assert response.status_code == 400
    assert "name" in response.get_json()["error"]


def test_create_rejects_boolean_quantity(client):
    response = client.post("/inventory", json={"name": "X", "quantity": True, "price": 1})
    assert response.status_code == 400


def test_create_rejects_negative_price(client):
    response = client.post("/inventory", json={"name": "X", "quantity": 1, "price": -2})
    assert response.status_code == 400


def test_duplicate_barcode_conflict(client):
    first = client.post("/inventory", json={"name": "A", "barcode": "111", "quantity": 1, "price": 1})
    assert first.status_code == 201
    second = client.post("/inventory", json={"name": "B", "barcode": "111", "quantity": 1, "price": 1})
    assert second.status_code == 409
    assert second.get_json()["existing_id"] == first.get_json()["id"]


def test_patch_missing_and_empty_body(client):
    created = client.post("/inventory", json={"name": "Tea", "quantity": 3, "price": 2})
    item_id = created.get_json()["id"]
    empty = client.patch(f"/inventory/{item_id}", json={})
    assert empty.status_code == 400
    missing = client.patch("/inventory/404", json={"quantity": 1})
    assert missing.status_code == 404


def test_low_stock_helper_route(client):
    client.post("/inventory", json={"name": "Plenty", "quantity": 40, "price": 1})
    client.post("/inventory", json={"name": "Almost gone", "quantity": 1, "price": 1})
    response = client.get("/inventory/low-stock?threshold=5")
    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 1
    assert data["items"][0]["name"] == "Almost gone"


def test_low_stock_bad_threshold(client):
    response = client.get("/inventory/low-stock?threshold=nope")
    assert response.status_code == 400


def test_lookup_barcode_success(client):
    response = client.get("/products/barcode/3017620422003")
    assert response.status_code == 200
    assert response.get_json()["name"] == "Nutella"


def test_lookup_barcode_not_found(client):
    response = client.get("/products/barcode/000")
    assert response.status_code == 404


def test_search_requires_query(client):
    response = client.get("/products/search")
    assert response.status_code == 400


def test_search_by_name(client):
    response = client.get("/products/search?q=nut")
    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 1
    assert data["products"][0]["barcode"] == "3017620422003"


def test_import_from_openfoodfacts(client):
    response = client.post(
        "/inventory/import",
        json={"barcode": "3017620422003", "quantity": 12, "price": 4.99},
    )
    assert response.status_code == 201
    item = response.get_json()
    assert item["name"] == NUTELLA["name"]
    assert item["quantity"] == 12
    assert item["price"] == 4.99
    assert item["source"] == "openfoodfacts"
    listing = client.get("/inventory").get_json()
    assert listing["count"] == 1


def test_import_duplicate_barcode(client):
    first = client.post("/inventory/import", json={"barcode": "3017620422003", "quantity": 1, "price": 1})
    assert first.status_code == 201
    second = client.post("/inventory/import", json={"barcode": "3017620422003", "quantity": 1, "price": 1})
    assert second.status_code == 409


def test_import_unknown_barcode(client):
    response = client.post("/inventory/import", json={"barcode": "000", "quantity": 1, "price": 1})
    assert response.status_code == 404


def test_unknown_route_is_json(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert "error" in response.get_json()
