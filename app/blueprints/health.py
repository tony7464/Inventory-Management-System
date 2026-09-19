from flask import Blueprint, jsonify

from ..deps import get_store

health_bp = Blueprint("health", __name__)


@health_bp.get("/")
def index():
    return jsonify(
        {
            "service": "Retail Inventory API",
            "health": "/health",
            "inventory": "/inventory",
            "low_stock": "/inventory/low-stock?threshold=5",
            "lookup": "/products/barcode/<barcode>",
            "search": "/products/search?q=nutella",
            "import": "POST /inventory/import",
        }
    )


@health_bp.get("/health")
def health():
    store = get_store()
    return jsonify(
        {
            "status": "ok",
            "service": "retail-inventory-api",
            "item_count": len(store.all()),
        }
    )
