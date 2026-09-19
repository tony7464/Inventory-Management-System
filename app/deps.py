from flask import current_app

from .openfoodfacts import OpenFoodFactsClient
from .storage import InventoryStore


def get_store() -> InventoryStore:
    return current_app.extensions["inventory"]


def get_off() -> OpenFoodFactsClient:
    return current_app.extensions["off"]
