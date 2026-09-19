from __future__ import annotations

from typing import Any, Optional

import requests


class OpenFoodFactsError(Exception):
    """The upstream catalog could not be reached or returned a bad payload."""


class ProductNotFound(OpenFoodFactsError):
    """Open Food Facts has no record for this barcode or the search was empty."""


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(part) for part in value if part)
    return str(value).strip()


def simplify_product(product: dict[str, Any]) -> dict[str, Any]:
    """Keep the handful of fields an inventory clerk actually needs.

    Raw Open Food Facts documents are huge. Mapping them here means the rest of
    the app never depends on OFF's nested shape — only on our own schema.
    """
    barcode = str(product.get("code") or product.get("_id") or "").strip()
    name = (
        product.get("product_name")
        or product.get("product_name_en")
        or product.get("generic_name")
        or "Unknown product"
    )
    return {
        "barcode": barcode or None,
        "name": str(name).strip(),
        "brand": _as_text(product.get("brands")),
        "ingredients": _as_text(
            product.get("ingredients_text") or product.get("ingredients_text_en")
        ),
        "categories": _as_text(product.get("categories")),
        "image_url": _as_text(product.get("image_url") or product.get("image_front_url")),
        "package_size": _as_text(product.get("quantity")),
        "nutriscore": _as_text(
            product.get("nutriscore_grade") or product.get("nutrition_grades")
        ),
        "source": "openfoodfacts",
    }


class OpenFoodFactsClient:
    PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
    SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
    SEARCH_ENGINE_URL = "https://search.openfoodfacts.org/search"

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        user_agent: str = "RetailInventoryPortal/1.0",
        timeout: float = 8.0,
    ):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.update({"User-Agent": user_agent})

    def get_by_barcode(self, barcode: str) -> dict[str, Any]:
        code = (barcode or "").strip()
        if not code:
            raise ProductNotFound("Barcode is empty.")

        payload = self._get_json(self.PRODUCT_URL.format(code=code))
        if payload.get("status") != 1 or not payload.get("product"):
            raise ProductNotFound(f"No Open Food Facts product for barcode {code}.")
        simplified = simplify_product(payload["product"])
        if not simplified.get("barcode"):
            simplified["barcode"] = code
        return simplified

    def search_by_name(self, query: str, page_size: int = 5) -> list[dict[str, Any]]:
        term = (query or "").strip()
        if len(term) < 2:
            return []

        try:
            payload = self._get_json(
                self.SEARCH_URL,
                params={
                    "search_terms": term,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": page_size,
                },
            )
            products = payload.get("products") or []
        except OpenFoodFactsError:
            # The legacy CGI search occasionally returns 503. Search-a-licious is the fallback.
            payload = self._get_json(
                self.SEARCH_ENGINE_URL,
                params={"q": term, "page_size": page_size},
            )
            products = payload.get("hits") or []

        results = [simplify_product(product) for product in products]
        return [item for item in results if item.get("name")]

    def _get_json(self, url: str, params: Optional[dict] = None) -> dict[str, Any]:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise OpenFoodFactsError("Open Food Facts request timed out.") from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            raise OpenFoodFactsError(f"Open Food Facts HTTP {status}.") from exc
        except requests.RequestException as exc:
            raise OpenFoodFactsError("Unable to reach Open Food Facts.") from exc
        except ValueError as exc:
            raise OpenFoodFactsError("Open Food Facts returned invalid JSON.") from exc

        if not isinstance(data, dict):
            raise OpenFoodFactsError("Open Food Facts returned an unexpected payload.")
        return data
