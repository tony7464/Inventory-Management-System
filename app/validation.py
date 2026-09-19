from __future__ import annotations

from typing import Any


ALLOWED_FIELDS = {
    "name",
    "brand",
    "barcode",
    "quantity",
    "price",
    "ingredients",
    "categories",
    "image_url",
    "package_size",
    "nutriscore",
    "source",
}


class ValidationError(ValueError):
    """Raised when a request body cannot be turned into an inventory item."""


def coerce_item_fields(data: Any, *, partial: bool = False) -> dict[str, Any]:
    """Validate and normalize JSON from POST/PATCH bodies.

    `partial=True` is for PATCH: omitted fields stay unchanged.
    """
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")

    unknown = set(data) - ALLOWED_FIELDS - {"id"}
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValidationError(f"Unknown field(s): {names}.")

    cleaned: dict[str, Any] = {}

    if "name" in data:
        name = str(data["name"]).strip()
        if not name:
            raise ValidationError("'name' cannot be empty.")
        cleaned["name"] = name

    if "brand" in data:
        cleaned["brand"] = str(data["brand"] or "").strip()

    if "barcode" in data:
        barcode = data["barcode"]
        cleaned["barcode"] = None if barcode in (None, "") else str(barcode).strip()

    if "quantity" in data:
        cleaned["quantity"] = _as_non_negative_int(data["quantity"], "quantity")

    if "price" in data:
        cleaned["price"] = _as_non_negative_float(data["price"], "price")

    for text_field in ("ingredients", "categories", "image_url", "package_size", "nutriscore", "source"):
        if text_field in data:
            cleaned[text_field] = str(data[text_field] or "").strip()

    if not partial:
        if "name" not in cleaned:
            raise ValidationError("'name' is required.")
        cleaned.setdefault("quantity", 0)
        cleaned.setdefault("price", 0.0)
        cleaned.setdefault("source", "manual")

    if partial and not cleaned:
        raise ValidationError("PATCH body must include at least one updatable field.")

    return cleaned


def _as_non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"'{field}' must be a number.")
    if value < 0 or int(value) != value:
        raise ValidationError(f"'{field}' must be a non-negative integer.")
    return int(value)


def _as_non_negative_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"'{field}' must be a number.")
    if value < 0:
        raise ValidationError(f"'{field}' cannot be negative.")
    return round(float(value), 2)
