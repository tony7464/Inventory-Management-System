from flask import Blueprint, jsonify, request

from ..deps import get_store
from ..storage import DuplicateBarcodeError
from ..validation import ValidationError, coerce_item_fields

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.get("/inventory")
def list_inventory():
    items = get_store().all()
    return jsonify({"count": len(items), "items": items})


@inventory_bp.get("/inventory/low-stock")
def low_stock():
    raw = request.args.get("threshold", 5)
    try:
        threshold = int(raw)
    except (TypeError, ValueError):
        return jsonify({"error": "threshold must be an integer."}), 400
    if threshold < 0:
        return jsonify({"error": "threshold cannot be negative."}), 400
    items = get_store().low_stock(threshold)
    return jsonify({"threshold": threshold, "count": len(items), "items": items})


@inventory_bp.get("/inventory/<int:item_id>")
def get_item(item_id):
    item = get_store().get(item_id)
    if item is None:
        return jsonify({"error": f"Item {item_id} not found."}), 404
    return jsonify(item)


@inventory_bp.post("/inventory")
def create_item():
    payload, error = _validated_body(partial=False)
    if error:
        return error
    try:
        item = get_store().create(payload)
    except DuplicateBarcodeError as exc:
        return jsonify({"error": str(exc), "existing_id": exc.existing["id"]}), 409
    return jsonify(item), 201


@inventory_bp.patch("/inventory/<int:item_id>")
def update_item(item_id):
    payload, error = _validated_body(partial=True)
    if error:
        return error
    try:
        item = get_store().update(item_id, payload)
    except DuplicateBarcodeError as extra:
        return jsonify({"error": str(extra), "existing_id": extra.existing["id"]}), 409
    if item is None:
        return jsonify({"error": f"Item {item_id} not found."}), 404
    return jsonify(item)


@inventory_bp.delete("/inventory/<int:item_id>")
def delete_item(item_id):
    deleted = get_store().delete(item_id)
    if not deleted:
        return jsonify({"error": f"Item {item_id} not found."}), 404
    return jsonify({"message": f"Item {item_id} deleted."})


def _validated_body(partial: bool):
    data = request.get_json(silent=True)
    try:
        return coerce_item_fields(data, partial=partial), None
    except ValidationError as exc:
        return None, (jsonify({"error": str(exc)}), 400)
