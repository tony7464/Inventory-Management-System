from __future__ import annotations

import threading
from typing import Optional

from .models import InventoryItem

SEED_CATALOG = [
    {
        "name": "Organic Almond Milk",
        "brand": "Silk",
        "barcode": "025293001577",
        "quantity": 18,
        "price": 3.49,
        "ingredients": "Filtered water, almonds, cane sugar, sea salt, locust bean gum, sunflower lecithin, gellan gum, natural flavor",
        "categories": "Plant-based milks",
        "package_size": "64 fl oz",
        "nutriscore": "b",
        "source": "seed",
    },
    {
        "name": "Nutella",
        "brand": "Ferrero",
        "barcode": "3017620422003",
        "quantity": 4,
        "price": 4.99,
        "ingredients": "Sugar, palm oil, hazelnuts, skim milk, cocoa, lecithin, vanillin",
        "categories": "Spreads, Chocolate hazelnut spreads",
        "package_size": "13 oz",
        "nutriscore": "e",
        "source": "seed",
    },
    {
        "name": "Coca-Cola",
        "brand": "Coca-Cola",
        "barcode": "5449000000996",
        "quantity": 24,
        "price": 1.25,
        "ingredients": "Carbonated water, sugar, caramel color, phosphoric acid, natural flavors, caffeine",
        "categories": "Beverages, Sodas",
        "package_size": "330 ml",
        "nutriscore": "e",
        "source": "seed",
    },
]


class DuplicateBarcodeError(ValueError):
    def __init__(self, existing: dict):
        self.existing = existing
        barcode = existing.get("barcode")
        item_id = existing.get("id")
        super().__init__(
            f"Barcode {barcode} is already stocked as item {item_id}."
        )


class InventoryStore:
    """In-memory stand-in for a database.

    The lab asks for a simulated array. A dict keyed by id keeps lookups O(1)
    while `all()` still returns a list — the structure the CLI and tests expect.
    A lock keeps mutations safe if the development server reloads threads.
    """

    def __init__(self, *, seed: bool = False):
        self._items: dict[int, InventoryItem] = {}
        self._next_id = 1
        self._lock = threading.Lock()
        if seed:
            for payload in SEED_CATALOG:
                self.create(payload)

    def all(self) -> list[dict]:
        with self._lock:
            return [item.to_dict() for item in self._items.values()]

    def get(self, item_id: int) -> Optional[dict]:
        with self._lock:
            item = self._items.get(item_id)
            return item.to_dict() if item else None

    def create(self, payload: dict) -> dict:
        with self._lock:
            barcode = payload.get("barcode")
            if barcode:
                existing = self._find_by_barcode_unlocked(str(barcode))
                if existing:
                    raise DuplicateBarcodeError(existing.to_dict())
            item_id = self._next_id
            self._next_id += 1
            item = InventoryItem.from_payload(item_id, payload)
            self._items[item_id] = item
            return item.to_dict()

    def update(self, item_id: int, fields: dict) -> Optional[dict]:
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return None
            barcode = fields.get("barcode")
            if barcode:
                other = self._find_by_barcode_unlocked(str(barcode))
                if other is not None and other.id != item_id:
                    raise DuplicateBarcodeError(other.to_dict())
            item.apply(fields)
            return item.to_dict()

    def delete(self, item_id: int) -> bool:
        with self._lock:
            return self._items.pop(item_id, None) is not None

    def low_stock(self, threshold: int) -> list[dict]:
        with self._lock:
            return [
                item.to_dict()
                for item in self._items.values()
                if item.quantity <= threshold
            ]

    def find_by_barcode(self, barcode: str) -> Optional[dict]:
        with self._lock:
            item = self._find_by_barcode_unlocked(barcode)
            return item.to_dict() if item else None

    def _find_by_barcode_unlocked(self, barcode: str) -> Optional[InventoryItem]:
        for item in self._items.values():
            if item.barcode and item.barcode == barcode:
                return item
        return None
