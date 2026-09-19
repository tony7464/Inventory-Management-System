from unittest.mock import Mock

from cli import ApiError, InventoryClient, handle_find_and_import, handle_list, run


def _json_response(payload, status=200):
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    response.text = ""
    return response


def test_client_list_items():
    session = Mock()
    session.request.return_value = _json_response({"count": 1, "items": [{"id": 1, "name": "Tea"}]})
    client = InventoryClient("http://example.test", session=session)
    payload = client.list_items()
    assert payload["count"] == 1
    session.request.assert_called_once()
    assert session.request.call_args.args[0] == "GET"
    assert session.request.call_args.args[1].endswith("/inventory")


def test_client_raises_api_error_on_404():
    session = Mock()
    session.request.return_value = _json_response({"error": "Item 9 not found."}, status=404)
    client = InventoryClient("http://example.test", session=session)
    try:
        client.get_item(9)
        assert False, "expected ApiError"
    except ApiError as exc:
        assert exc.status_code == 404
        assert "not found" in str(exc).lower()


def test_client_connection_error_is_friendly():
    session = Mock()
    session.request.side_effect = __import__("requests").ConnectionError()
    client = InventoryClient("http://127.0.0.1:5000", session=session)
    try:
        client.health()
        assert False, "expected ApiError"
    except ApiError as exc:
        assert "python run.py" in str(exc)


def test_handle_list_prints_table():
    api = Mock()
    api.list_items.return_value = {
        "count": 1,
        "items": [
            {
                "id": 1,
                "name": "Nutella",
                "brand": "Ferrero",
                "quantity": 4,
                "price": 4.99,
                "barcode": "3017620422003",
                "source": "seed",
            }
        ],
    }
    lines = []
    handle_list(api, input, lines.append)
    output = "\n".join(lines)
    assert "Nutella" in output
    assert "1 item" in output


def test_handle_find_and_import_by_barcode():
    api = Mock()
    api.lookup_barcode.return_value = {
        "barcode": "3017620422003",
        "name": "Nutella",
        "brand": "Ferrero",
        "ingredients": "Sugar",
        "package_size": "400 g",
        "nutriscore": "e",
    }
    api.import_barcode.return_value = {
        "id": 4,
        "name": "Nutella",
        "quantity": 6,
        "price": 4.5,
        "barcode": "3017620422003",
        "brand": "Ferrero",
        "source": "openfoodfacts",
    }
    answers = iter(["b", "3017620422003", "y", "6", "4.50"])
    lines = []
    handle_find_and_import(api, lambda _prompt: next(answers), lines.append)
    api.lookup_barcode.assert_called_once_with("3017620422003")
    api.import_barcode.assert_called_once_with("3017620422003", 6, 4.5)
    assert any("Imported" in line for line in lines)


def test_run_exits_on_zero():
    api = Mock()
    api.base_url = "http://127.0.0.1:5000"
    api.health.return_value = {"status": "ok"}
    answers = iter(["0"])
    lines = []
    run(client=api, reader=lambda _prompt: next(answers), writer=lines.append)
    assert any("Goodbye" in line for line in lines)
