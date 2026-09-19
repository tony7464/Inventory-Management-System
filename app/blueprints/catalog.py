from flask import Blueprint, jsonify, request

from ..deps import get_off, get_store
from ..openfoodfacts import OpenFoodFactsError, ProductNotFound
from ..storage import DuplicateBarcodeError
from ..validation import ValidationError, coerce_item_fields

catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.get("/products/barcode/<barcode>")
def lookup_barcode(barcode):
    try:
        product = get_off().get_by_barcode(barcode)
    except ProductNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except OpenFoodFactsError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify(product)


@catalog_bp.get("/products/search")
def search_products():
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({"error": "Query parameter 'q' must be at least 2 characters."}), 400
    try:
        products = get_off().search_by_name(query)
    except OpenFoodFactsError as extra:
        return jsonify({"error": str(extra)}), 502
    return jsonify({"query": query, "count": len(products), "products": products})


@catalog_bp.post("/inventory/import")
def import_product():
    """Look up a barcode on Open Food Facts and append it to inventory."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    barcode = str(data.get("barcode") or "").strip()
    if not barcode:
        return jsonify({"error": "'barcode' is required."}), 400

    try:
        product = get_off().get_by_barcode(barcode)
    except ProductNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except OpenFoodFactsError as extra:
        return jsonify({"error": str(extra)}), 502

    extras = {key: data[key] for key in ("quantity", "price") if key in data}
    try:
        stock = coerce_item_fields(
            {
                "name": product["name"],
                "brand": product.get("brand") or "",
                "barcode": product.get("barcode") or barcode,
                "ingredients": product.get("ingredients") or "",
                "categories": product.get("categories") or "",
                "image_url": product.get("image_url") or "",
                "package_size": product.get("package_size") or "",
                "nutriscore": product.get("nutriscore") or "",
                "source": "openfoodfacts",
                "quantity": extras.get("quantity", 1),
                "price": extras.get("price", 0.0),
            },
            partial=False,
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        item = get_store().create(stock)
    except DuplicateBarcodeError as dup:
        return jsonify({"error": str(dup), "existing_id": dup.existing["id"]}), 409
    return jsonify(item), 201
