"""Server-side client for DigiKey Product Information API v4."""

import os
import time
from urllib.parse import quote

import requests
from flask import current_app


API_BASE = "https://api.digikey.com"
TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"


class DigiKeyAPIError(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def _config(name, default=None):
    return current_app.config.get(name) or os.getenv(name) or default


def _value(obj, key):
    return obj.get(key) if isinstance(obj, dict) else None


def _named(obj):
    if isinstance(obj, dict):
        return obj.get("Name") or obj.get("ProductDescription") or obj.get("Code") or ""
    return obj or ""


def _list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _integer(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _api_error(response, operation):
    status = response.status_code
    if status == 401:
        return DigiKeyAPIError("DigiKey authentication failed. Check the server credentials.", 502)
    if status == 403:
        return DigiKeyAPIError("DigiKey denied this request. Check API access and subscription.", 502)
    if status == 429:
        return DigiKeyAPIError("DigiKey rate limit reached. Wait briefly and search again.", 429)
    if status == 404:
        return DigiKeyAPIError("DigiKey did not find this product.", 404)
    current_app.logger.warning("DigiKey %s returned HTTP %s", operation, status)
    return DigiKeyAPIError("DigiKey product lookup is temporarily unavailable.", 502)


def _request_json(method, url, *, operation, **kwargs):
    try:
        response = requests.request(method, url, timeout=10, **kwargs)
    except requests.Timeout as exc:
        raise DigiKeyAPIError("DigiKey request timed out. Try again.", 504) from exc
    except requests.RequestException as exc:
        current_app.logger.warning("DigiKey %s request failed: %s", operation, exc)
        raise DigiKeyAPIError("DigiKey product lookup is temporarily unavailable.", 502) from exc
    if not response.ok and response.status_code != 404:
        raise _api_error(response, operation)
    if response.status_code == 404:
        return {
            "ProductsCount": 0,
            "ProductPricings": [],
            "SettingsUsed": {
                "SearchLocale": {
                    "Currency": kwargs.get("headers", {}).get("X-DIGIKEY-Locale-Currency")
                }
            },
        }
    try:
        return response.json()
    except ValueError as exc:
        raise DigiKeyAPIError("DigiKey returned an unreadable response.", 502) from exc


def _access_token():
    client_id = _config("DIGIKEY_CLIENT_ID")
    client_secret = _config("DIGIKEY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise DigiKeyAPIError("DigiKey API credentials are not configured on the server.", 503)

    cached = current_app.extensions.get("digikey_oauth_token")
    if cached and cached["expires_at"] > time.monotonic() + 30:
        return cached["value"]

    body = _request_json(
        "POST", _config("DIGIKEY_TOKEN_URL", TOKEN_URL), operation="token request",
        data={"grant_type": "client_credentials"}, auth=(client_id, client_secret),
    )
    token = body.get("access_token") if isinstance(body, dict) else None
    if not token:
        raise DigiKeyAPIError("DigiKey did not return an access token.", 502)
    current_app.extensions["digikey_oauth_token"] = {
        "value": token,
        "expires_at": time.monotonic() + int(body.get("expires_in", 600)),
    }
    return token


def _parse_variation(variation, currency):
    my_pricing = variation.get("MyPricing")
    standard_pricing = variation.get("StandardPricing")
    # Customer pricing is authoritative when it contains usable tiers. If it
    # is absent or empty, retain DigiKey's standard variation pricing.
    usable_customer_tiers = [
        tier for tier in _list(my_pricing)
        if isinstance(tier, dict)
        and _integer(tier.get("BreakQuantity")) is not None
        and _number(tier.get("UnitPrice")) is not None
    ]
    pricing_key = "MyPricing" if usable_customer_tiers else "StandardPricing"
    selected_pricing = my_pricing if pricing_key == "MyPricing" else standard_pricing
    tiers = []
    for tier in _list(selected_pricing):
        quantity = _integer(tier.get("BreakQuantity"))
        unit_price = _number(tier.get("UnitPrice"))
        if quantity is not None and quantity > 0 and unit_price is not None:
            tiers.append({
                "break_quantity": quantity,
                "unit_price": unit_price,
                "total_price": _number(tier.get("TotalPrice")),
                "currency": currency,
                "source": pricing_key,
            })
    tiers.sort(key=lambda tier: tier["break_quantity"])
    return {
        "digikey_product_number": variation.get("DigiKeyProductNumber"),
        "package_type": _named(variation.get("PackageType")),
        "available_quantity": _integer(variation.get("QuantityAvailableforPackageType")),
        "minimum_order_quantity": _integer(variation.get("MinimumOrderQuantity")),
        "max_quantity_for_distribution": _integer(variation.get("MaxQuantityForDistribution")),
        "pricing_tiers": tiers,
        "pricing_source": pricing_key if tiers else None,
    }


def select_price_tier(pricing_tiers, quantity):
    """Select the highest applicable DigiKey break, or the base break below it."""
    valid = []
    for tier in pricing_tiers if isinstance(pricing_tiers, list) else []:
        if not isinstance(tier, dict):
            continue
        break_quantity = _integer(tier.get("break_quantity"))
        unit_price = _number(tier.get("unit_price"))
        currency = tier.get("currency")
        if break_quantity and break_quantity > 0 and unit_price is not None and unit_price >= 0 and currency:
            valid.append((break_quantity, tier))
    if not valid:
        return None
    requested = _integer(quantity)
    if requested is None or requested < 1:
        return None
    applicable = [item for item in valid if item[0] <= requested]
    return max(applicable, key=lambda item: item[0])[1] if applicable else min(valid, key=lambda item: item[0])[1]


def select_package_variation(variations):
    """Mirror DigiKey normalization: use the variation with the lowest MOQ."""
    valid = [item for item in variations if isinstance(item, dict)] if isinstance(variations, list) else []
    if not valid:
        return None
    return min(valid, key=lambda item: item.get("minimum_order_quantity") or 0)


def _parse_product(product, currency, requested_mpn):
    manufacturer_mpn = str(product.get("ManufacturerProductNumber") or "")
    normalize = lambda value: "".join(str(value).casefold().split())
    description = product.get("Description")
    details = {
        "manufacturer_part_number": manufacturer_mpn,
        "manufacturer": _named(product.get("Manufacturer")),
        "digikey_part_number": product.get("DigiKeyProductNumber"),
        "description": _named(description),
        "detailed_description": _value(description, "DetailedDescription") if isinstance(description, dict) else None,
        "category": _named(product.get("Category")),
        "currency": currency,
        "available_quantity": _integer(product.get("QuantityAvailable")),
        "variations": [_parse_variation(item, currency) for item in _list(product.get("ProductVariations"))],
        "exact_mpn_match": normalize(manufacturer_mpn) == normalize(requested_mpn),
    }
    return details


def lookup_product_details(mpn, requested_currency=None):
    """Return Search API pricing matches; price tiers remain package-specific."""
    client_id = _config("DIGIKEY_CLIENT_ID")
    token = _access_token()
    locale_currency = requested_currency or _config("DIGIKEY_LOCALE_CURRENCY", "INR")
    headers = {
        "X-DIGIKEY-Client-Id": client_id,
        "Authorization": f"Bearer {token}",
        "X-DIGIKEY-Locale-Site": _config("DIGIKEY_LOCALE_SITE", "IN"),
        "X-DIGIKEY-Locale-Language": _config("DIGIKEY_LOCALE_LANGUAGE", "en"),
        "X-DIGIKEY-Locale-Currency": locale_currency,
        "Accept": "application/json",
    }
    customer_id = _config("DIGIKEY_CUSTOMER_ID")
    if customer_id:
        headers["X-DIGIKEY-Customer-Id"] = customer_id
    url = f"{_config('DIGIKEY_API_BASE', API_BASE)}/products/v4/search/{quote(mpn, safe='')}/pricing"
    body = _request_json("GET", url, operation="product pricing lookup", headers=headers)
    settings = body.get("SettingsUsed") if isinstance(body, dict) else None
    locale = _value(settings, "SearchLocale") or {}
    currency = _value(locale, "Currency")
    products = _list(_value(body, "ProductPricings"))
    matches = [_parse_product(item, currency, mpn) for item in products if isinstance(item, dict)]
    matches.sort(key=lambda item: not item["exact_mpn_match"])
    return {
        "matches": matches,
        "products_count": _integer(_value(body, "ProductsCount")),
        "currency": currency,
    }
