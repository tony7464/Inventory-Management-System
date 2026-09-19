import pytest

from app import create_app
from app.openfoodfacts import OpenFoodFactsError, ProductNotFound
from app.storage import InventoryStore


class FakeOFFClient:
    def __init__(self, products=None, fail=False):
        self.products = products or {}
        self.fail = fail
        self.calls = []

    def get_by_barcode(self, barcode):
        self.calls.append(("barcode", barcode))
        if self.fail:
            raise OpenFoodFactsError("Open Food Facts is down.")
        product = self.products.get(barcode)
        if product is None:
            raise ProductNotFound(f"No Open Food Facts product for barcode {barcode}.")
        return product

    def search_by_name(self, query, page_size=5):
        self.calls.append(("search", query))
        if self.fail:
            raise OpenFoodFactsError("Open Food Facts is down.")
        matches = [
            product
            for product in self.products.values()
            if query.lower() in product["name"].lower()
        ]
        return matches[:page_size]


NUTELLA = {
    "barcode": "3017620422003",
    "name": "Nutella",
    "brand": "Ferrero",
    "ingredients": "Sugar, palm oil, hazelnuts",
    "categories": "Spreads",
    "image_url": "https://example.com/nutella.jpg",
    "package_size": "400 g",
    "nutriscore": "e",
    "source": "openfoodfacts",
}


@pytest.fixture
def store():
    return InventoryStore(seed=False)


@pytest.fixture
def off_client():
    return FakeOFFClient(products={"3017620422003": NUTELLA})


@pytest.fixture
def app(store, off_client):
    application = create_app(inventory=store, off_client=off_client, seed=False)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()
