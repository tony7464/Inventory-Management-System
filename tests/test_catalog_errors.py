from app import create_app
from app.openfoodfacts import OpenFoodFactsError
from tests.conftest import FakeOFFClient


def test_lookup_returns_502_when_catalog_is_down():
    app = create_app(off_client=FakeOFFClient(fail=True), seed=False)
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/products/barcode/3017620422003")
    assert response.status_code == 502
    assert "down" in response.get_json()["error"].lower() or "Open Food Facts" in response.get_json()["error"]


def test_search_returns_502_when_catalog_is_down():
    app = create_app(off_client=FakeOFFClient(fail=True), seed=False)
    client = app.test_client()
    response = client.get("/products/search?q=milk")
    assert response.status_code == 502


def test_import_returns_502_when_catalog_is_down():
    app = create_app(off_client=FakeOFFClient(fail=True), seed=False)
    client = app.test_client()
    response = client.post("/inventory/import", json={"barcode": "1", "quantity": 1, "price": 1})
    assert response.status_code == 502


def test_openfoodfacts_error_is_distinct():
    assert issubclass(OpenFoodFactsError, Exception)
