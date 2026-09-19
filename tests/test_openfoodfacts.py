from unittest.mock import Mock

import requests

from app.openfoodfacts import (
    OpenFoodFactsClient,
    OpenFoodFactsError,
    ProductNotFound,
    simplify_product,
)


def test_simplify_product_maps_off_fields():
    raw = {
        "code": "3017620422003",
        "product_name": "Nutella",
        "brands": "Ferrero",
        "ingredients_text": "Sugar, palm oil, hazelnuts",
        "categories": "Spreads",
        "image_front_url": "https://example.com/n.jpg",
        "quantity": "400 g",
        "nutriscore_grade": "e",
    }
    item = simplify_product(raw)
    assert item["barcode"] == "3017620422003"
    assert item["name"] == "Nutella"
    assert item["package_size"] == "400 g"
    assert item["source"] == "openfoodfacts"


def test_get_by_barcode_success():
    session = Mock()
    response = Mock()
    response.json.return_value = {
        "status": 1,
        "product": {"code": "3017620422003", "product_name": "Nutella", "brands": "Ferrero"},
    }
    response.raise_for_status.return_value = None
    session.get.return_value = response

    client = OpenFoodFactsClient(session=session)
    product = client.get_by_barcode("3017620422003")
    assert product["name"] == "Nutella"
    session.get.assert_called_once()
    assert "3017620422003" in session.get.call_args.args[0]


def test_get_by_barcode_not_found():
    session = Mock()
    response = Mock()
    response.json.return_value = {"status": 0, "status_verbose": "product not found"}
    response.raise_for_status.return_value = None
    session.get.return_value = response

    client = OpenFoodFactsClient(session=session)
    try:
        client.get_by_barcode("000")
        assert False, "expected ProductNotFound"
    except ProductNotFound:
        pass


def test_search_by_name_returns_simplified_list():
    session = Mock()
    response = Mock()
    response.json.return_value = {
        "products": [
            {"code": "1", "product_name": "Almond Milk", "brands": "Silk"},
            {"code": "2", "product_name": "Almond Butter", "brands": "Barney"},
        ]
    }
    response.raise_for_status.return_value = None
    session.get.return_value = response

    client = OpenFoodFactsClient(session=session)
    results = client.search_by_name("almond")
    assert len(results) == 2
    assert results[0]["brand"] == "Silk"
    session.get.assert_called_once()
    assert session.get.call_args.kwargs["params"]["search_terms"] == "almond"


def test_search_falls_back_when_cgi_is_unavailable():
    cgi_response = Mock()
    error = requests.HTTPError("503")
    error.response = Mock(status_code=503)
    cgi_response.raise_for_status.side_effect = error

    engine_response = Mock()
    engine_response.raise_for_status.return_value = None
    engine_response.json.return_value = {
        "hits": [
            {
                "code": "20050894",
                "product_name": "Almond Drink",
                "brands": ["Milbona"],
                "quantity": "1 l",
                "nutriscore_grade": "b",
            }
        ]
    }

    session = Mock()

    def fake_get(url, params=None, timeout=None):
        if "cgi/search.pl" in url:
            return cgi_response
        return engine_response

    session.get.side_effect = fake_get
    client = OpenFoodFactsClient(session=session)
    results = client.search_by_name("almond milk")
    assert len(results) == 1
    assert results[0]["name"] == "Almond Drink"
    assert results[0]["brand"] == "Milbona"
    assert session.get.call_count == 2


def test_timeout_becomes_openfoodfacts_error():
    session = Mock()
    session.get.side_effect = requests.Timeout()
    client = OpenFoodFactsClient(session=session)
    try:
        client.get_by_barcode("123")
        assert False, "expected OpenFoodFactsError"
    except OpenFoodFactsError as exc:
        assert "timed out" in str(exc)
