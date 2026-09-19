from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class InventoryItem:
    """One row in the store's inventory.

    Open Food Facts describes a *product* (name, brand, package size).
    This object is a *stock record*: how many units we hold and at what price.
    Those two ideas must not be mixed — `package_size` is "400 g", `quantity` is "12 bottles on the shelf".
    """

    id: int
    name: str
    quantity: int
    price: float
    brand: str = ""
    barcode: Optional[str] = None
    ingredients: str = ""
    categories: str = ""
    image_url: str = ""
    package_size: str = ""
    nutriscore: str = ""
    source: str = "manual"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def apply(self, fields: dict[str, Any]) -> None:
        for key, value in fields.items():
            if key == "id":
                continue
            if hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    def from_payload(cls, item_id: int, payload: dict[str, Any]) -> InventoryItem:
        return cls(
            id=item_id,
            name=str(payload["name"]).strip(),
            quantity=int(payload.get("quantity", 0)),
            price=float(payload.get("price", 0.0)),
            brand=str(payload.get("brand") or "").strip(),
            barcode=_optional_barcode(payload.get("barcode")),
            ingredients=str(payload.get("ingredients") or "").strip(),
            categories=str(payload.get("categories") or "").strip(),
            image_url=str(payload.get("image_url") or "").strip(),
            package_size=str(payload.get("package_size") or "").strip(),
            nutriscore=str(payload.get("nutriscore") or "").strip(),
            source=str(payload.get("source") or "manual").strip(),
        )


def _optional_barcode(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
