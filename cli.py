#!/usr/bin/env python3
"""Command-line administrator portal for the Retail Inventory API.

The CLI never touches the in-memory store directly. Every action is an HTTP
call so the same rules apply whether you use this menu, curl, or Postman.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Callable, Optional

import requests

DEFAULT_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000")

Reader = Callable[[str], str]
Writer = Callable[[str], None]


class ApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class InventoryClient:
    """Thin HTTP wrapper used by the menu and by tests."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, session: Optional[requests.Session] = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

    def health(self) -> dict:
        return self._request("GET", "/health")

    def list_items(self) -> dict:
        return self._request("GET", "/inventory")

    def get_item(self, item_id: int) -> dict:
        return self._request("GET", f"/inventory/{item_id}")

    def create_item(self, payload: dict) -> dict:
        return self._request("POST", "/inventory", json=payload)

    def update_item(self, item_id: int, payload: dict) -> dict:
        return self._request("PATCH", f"/inventory/{item_id}", json=payload)

    def delete_item(self, item_id: int) -> dict:
        return self._request("DELETE", f"/inventory/{item_id}")

    def low_stock(self, threshold: int) -> dict:
        return self._request("GET", "/inventory/low-stock", params={"threshold": threshold})

    def lookup_barcode(self, barcode: str) -> dict:
        return self._request("GET", f"/products/barcode/{barcode}")

    def search_products(self, query: str) -> dict:
        return self._request("GET", "/products/search", params={"q": query})

    def import_barcode(self, barcode: str, quantity: int, price: float) -> dict:
        return self._request(
            "POST",
            "/inventory/import",
            json={"barcode": barcode, "quantity": quantity, "price": price},
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.ConnectionError as exc:
            raise ApiError(
                f"Cannot reach the API at {self.base_url}. Start it with: python run.py"
            ) from exc
        except requests.Timeout as extra:
            raise ApiError("The API did not respond in time.") from extra
        except requests.RequestException as extra:
            raise ApiError(f"Request failed: {extra}") from extra

        payload: Any
        try:
            payload = response.json()
        except ValueError:
            payload = {"error": response.text or "Non-JSON response from API."}

        if response.status_code >= 400:
            message = payload.get("error") if isinstance(payload, dict) else str(payload)
            raise ApiError(message or f"HTTP {response.status_code}", response.status_code, payload)
        if not isinstance(payload, dict):
            raise ApiError("API returned an unexpected payload.", response.status_code, payload)
        return payload


MENU = """
============================================================
  RETAIL INVENTORY  ·  Administrator Portal
============================================================
  1. View all inventory
  2. View item by ID
  3. Add item manually
  4. Update price or stock
  5. Delete item
  6. Find on Open Food Facts  (optionally add to inventory)
  7. Low-stock report
  0. Exit
------------------------------------------------------------
"""


def run(
    client: Optional[InventoryClient] = None,
    reader: Reader = input,
    writer: Writer = print,
) -> None:
    client = client or InventoryClient()
    writer(MENU.strip("\n"))
    try:
        client.health()
        writer(f"Connected to {client.base_url}")
    except ApiError as exc:
        writer(str(exc))
        writer("You can still open the menu; commands will fail until the server is up.")

    while True:
        writer("")
        choice = _ask(reader, "Choose an option: ")
        if choice in {"0", "q", "quit", "exit"}:
            writer("Goodbye.")
            return
        handlers = {
            "1": handle_list,
            "2": handle_get,
            "3": handle_create,
            "4": handle_update,
            "5": handle_delete,
            "6": handle_find_and_import,
            "7": handle_low_stock,
        }
        action = handlers.get(choice)
        if action is None:
            writer("Please enter a number from the menu.")
            continue
        try:
            action(client, reader, writer)
        except ApiError as exc:
            writer(f"Error: {exc}")
        except (EOFError, KeyboardInterrupt):
            writer("\nGoodbye.")
            return


def handle_list(client: InventoryClient, reader: Reader, writer: Writer) -> None:
    payload = client.list_items()
    items = payload.get("items") or []
    writer(f"{payload.get('count', len(items))} item(s) in inventory.")
    writer(_table(items))


def handle_get(client: InventoryClient, reader: Reader, writer: Writer) -> None:
    item_id = _ask_int(reader, writer, "Item ID: ")
    if item_id is None:
        return
    writer(_detail(client.get_item(item_id)))


def handle_create(client: InventoryClient, reader: Reader, writer: Writer) -> None:
    name = _ask(reader, "Name: ")
    if not name:
        writer("Name is required.")
        return
    brand = _ask(reader, "Brand (optional): ")
    barcode = _ask(reader, "Barcode (optional): ")
    quantity = _ask_int(reader, writer, "Quantity on hand: ", default=0)
    if quantity is None:
        return
    price = _ask_float(reader, writer, "Price: ", default=0.0)
    if price is None:
        return
    payload = {
        "name": name,
        "brand": brand,
        "quantity": quantity,
        "price": price,
        "source": "manual",
    }
    if barcode:
        payload["barcode"] = barcode
    item = client.create_item(payload)
    writer("Created:")
    writer(_detail(item))


def handle_update(client: InventoryClient, reader: Reader, writer: Writer) -> None:
    item_id = _ask_int(reader, writer, "Item ID to update: ")
    if item_id is None:
        return
    writer("Leave a field blank to keep the current value.")
    current = client.get_item(item_id)
    writer(_detail(current))
    patch: dict[str, Any] = {}
    qty_raw = _ask(reader, f"New quantity [{current.get('quantity')}]: ")
    if qty_raw:
        quantity = _parse_int(qty_raw, writer, "quantity")
        if quantity is None:
            return
        patch["quantity"] = quantity
    price_raw = _ask(reader, f"New price [{current.get('price')}]: ")
    if price_raw:
        price = _parse_float(price_raw, writer, "price")
        if price is None:
            return
        patch["price"] = price
    if not patch:
        writer("Nothing to update.")
        return
    writer(_detail(client.update_item(item_id, patch)))


def handle_delete(client: InventoryClient, reader: Reader, writer: Writer) -> None:
    item_id = _ask_int(reader, writer, "Item ID to delete: ")
    if item_id is None:
        return
    confirm = _ask(reader, f"Delete item {item_id}? [y/N]: ").lower()
    if confirm not in {"y", "yes"}:
        writer("Cancelled.")
        return
    result = client.delete_item(item_id)
    writer(result.get("message", "Deleted."))


def handle_find_and_import(client: InventoryClient, reader: Reader, writer: Writer) -> None:
    writer("Search Open Food Facts by barcode or by product name.")
    mode = _ask(reader, "Barcode or name? [b/n]: ").lower()
    product = None
    if mode in {"b", "barcode"}:
        barcode = _ask(reader, "Barcode: ")
        if not barcode:
            writer("Barcode is required.")
            return
        product = client.lookup_barcode(barcode)
        writer(_product_card(product))
    elif mode in {"n", "name"}:
        query = _ask(reader, "Product name: ")
        if len(query) < 2:
            writer("Enter at least 2 characters.")
            return
        payload = client.search_products(query)
        products = payload.get("products") or []
        if not products:
            writer("No products matched that name.")
            return
        writer(f"{len(products)} result(s):")
        for index, item in enumerate(products, start=1):
            writer(
                f"  {index}. {item.get('name')} · {item.get('brand') or 'unknown brand'} · {item.get('barcode') or 'no barcode'}"
            )
        pick = _ask_int(reader, writer, "Choose a number (0 to cancel): ", default=0)
        if pick is None or pick == 0:
            writer("Cancelled.")
            return
        if pick < 1 or pick > len(products):
            writer("That number is not in the list.")
            return
        product = products[pick - 1]
        writer(_product_card(product))
    else:
        writer("Enter 'b' for barcode or 'n' for name.")
        return

    if _ask(reader, "Add this product to inventory? [y/N]: ").lower() not in {"y", "yes"}:
        writer("Not added.")
        return
    barcode = product.get("barcode")
    if not barcode:
        writer("This result has no barcode, so it cannot be imported. Add it manually instead.")
        return
    quantity = _ask_int(reader, writer, "Quantity to stock: ", default=1)
    if quantity is None:
        return
    price = _ask_float(reader, writer, "Shelf price: ", default=0.0)
    if price is None:
        return
    item = client.import_barcode(str(barcode), quantity, price)
    writer("Imported into inventory:")
    writer(_detail(item))


def handle_low_stock(client: InventoryClient, reader: Reader, writer: Writer) -> None:
    threshold = _ask_int(reader, writer, "Alert when quantity is at or below: ", default=5)
    if threshold is None:
        return
    payload = client.low_stock(threshold)
    items = payload.get("items") or []
    writer(f"{len(items)} item(s) at or below {threshold}.")
    writer(_table(items))


def _ask(reader: Reader, prompt: str) -> str:
    return reader(prompt).strip()


def _ask_int(reader: Reader, writer: Writer, prompt: str, default: Optional[int] = None) -> Optional[int]:
    raw = _ask(reader, prompt)
    if raw == "" and default is not None:
        return default
    return _parse_int(raw, writer, "value")


def _ask_float(reader: Reader, writer: Writer, prompt: str, default: Optional[float] = None) -> Optional[float]:
    raw = _ask(reader, prompt)
    if raw == "" and default is not None:
        return default
    return _parse_float(raw, writer, "value")


def _parse_int(raw: str, writer: Writer, label: str) -> Optional[int]:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        writer(f"'{label}' must be a whole number.")
        return None
    if value < 0:
        writer(f"'{label}' cannot be negative.")
        return None
    return value


def _parse_float(raw: str, writer: Writer, label: str) -> Optional[float]:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        writer(f"'{label}' must be a number.")
        return None
    if value < 0:
        writer(f"'{label}' cannot be negative.")
        return None
    return round(value, 2)


def _table(items: list[dict]) -> str:
    if not items:
        return "(empty)"
    headers = ("ID", "NAME", "BRAND", "QTY", "PRICE", "BARCODE", "SOURCE")
    rows = [
        (
            str(item.get("id", "")),
            _clip(item.get("name"), 28),
            _clip(item.get("brand"), 16),
            str(item.get("quantity", "")),
            f"${float(item.get('price') or 0):.2f}",
            str(item.get("barcode") or "—"),
            str(item.get("source") or ""),
        )
        for item in items
    ]
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    line = "  ".join(headers[i].ljust(widths[i]) for i in range(len(headers)))
    rule = "  ".join("-" * widths[i] for i in range(len(headers)))
    body = "\n".join("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))) for row in rows)
    return f"{line}\n{rule}\n{body}"


def _detail(item: dict) -> str:
    price = float(item.get("price") or 0)
    lines = [
        f"  ID:           {item.get('id')}",
        f"  Name:         {item.get('name')}",
        f"  Brand:        {item.get('brand') or '—'}",
        f"  Quantity:     {item.get('quantity')}",
        f"  Price:        ${price:.2f}",
        f"  Barcode:      {item.get('barcode') or '—'}",
        f"  Package:      {item.get('package_size') or '—'}",
        f"  Nutri-Score:  {item.get('nutriscore') or '—'}",
        f"  Source:       {item.get('source') or '—'}",
    ]
    if item.get("ingredients"):
        lines.append(f"  Ingredients:  {_clip(item.get('ingredients'), 80)}")
    return "\n".join(lines)


def _product_card(product: dict) -> str:
    return "\n".join(
        [
            "Open Food Facts result:",
            f"  Name:         {product.get('name')}",
            f"  Brand:        {product.get('brand') or '—'}",
            f"  Barcode:      {product.get('barcode') or '—'}",
            f"  Package:      {product.get('package_size') or '—'}",
            f"  Nutri-Score:  {product.get('nutriscore') or '—'}",
            f"  Ingredients:  {_clip(product.get('ingredients'), 80) or '—'}",
        ]
    )


def _clip(value: Any, width: int) -> str:
    text = "" if value is None else str(value)
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        sys.stdout.write("\nGoodbye.\n")
