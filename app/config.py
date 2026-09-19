import os


class Config:
    """Default runtime settings. Override with environment variables when needed."""

    OFF_USER_AGENT = os.environ.get(
        "OFF_USER_AGENT",
        "RetailInventoryPortal/1.0 (educational portfolio; +https://world.openfoodfacts.org)",
    )
    OFF_TIMEOUT = float(os.environ.get("OFF_TIMEOUT", "8"))
    API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000")
