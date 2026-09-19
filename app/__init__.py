from flask import Flask, jsonify

from .blueprints.catalog import catalog_bp
from .blueprints.health import health_bp
from .blueprints.inventory import inventory_bp
from .config import Config
from .openfoodfacts import OpenFoodFactsClient
from .storage import InventoryStore


def create_app(
    *,
    config=None,
    inventory=None,
    off_client=None,
    seed: bool = True,
):
    """Application factory so tests can inject an empty store and a fake catalog."""
    app = Flask(__name__)
    app.config.from_object(config or Config)

    app.extensions["inventory"] = inventory or InventoryStore(seed=seed)
    app.extensions["off"] = off_client or OpenFoodFactsClient(
        user_agent=app.config["OFF_USER_AGENT"],
        timeout=app.config["OFF_TIMEOUT"],
    )

    app.register_blueprint(health_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(catalog_bp)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "Method not allowed."}), 405

    return app
