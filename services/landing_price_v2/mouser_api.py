"""Server-side client for Mouser's Search API."""

import os
import re

import requests
from flask import current_app

from .digikey_api import DigiKeyAPIError, select_price_tier


def _available_quantity(product):
    raw = product.get("AvailabilityInStock")
    if raw is not None and str(raw).strip():
        text = str(raw).replace(",", "").strip()
        if text.isdigit():
            return int(text)
    availability = str(product.get("Availability") or "")
    match = re.search(r"([\d,]+)\s*(?:in\s+stock|available)", availability, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def lookup_product_details(mpn, quantity):
    api_key = (
        current_app.config.get("MOUSER_API_KEY")
        or current_app.config.get("MOUSER_SEARCH_API_KEY")
        or os.getenv("MOUSER_API_KEY")
        or os.getenv("MOUSER_SEARCH_API_KEY")
        or os.getenv("search_api_key")
    )
    base_url = current_app.config.get("MOUSER_BASE_URL") or os.getenv(
        "MOUSER_BASE_URL", os.getenv("mouser_base_url", "https://api.mouser.com/api/v1")
    )
    if not api_key:
        raise DigiKeyAPIError("Mouser API credentials are not configured on the server.", 503)
    url = f"{base_url.rstrip('/')}/search/partnumber"
    try:
        response = requests.post(
            url,
            params={"apiKey": api_key},
            json={"SearchByPartRequest": {"mouserPartNumber": mpn, "partSearchOptions": "None"}},
            timeout=10,
        )
    except requests.Timeout as exc:
        raise DigiKeyAPIError("Mouser request timed out. Try again.", 504) from exc
    except requests.RequestException as exc:
        current_app.logger.warning("Mouser product lookup failed: %s", exc)
        raise DigiKeyAPIError("Mouser product lookup is temporarily unavailable.", 502) from exc
    if response.status_code == 401 or response.status_code == 403:
        raise DigiKeyAPIError("Mouser authentication failed. Check the server API key.", 502)
    if response.status_code == 429:
        raise DigiKeyAPIError("Mouser rate limit reached. Wait briefly and search again.", 429)
    if not response.ok:
        current_app.logger.warning("Mouser search returned HTTP %s", response.status_code)
        raise DigiKeyAPIError("Mouser product lookup is temporarily unavailable.", 502)
    try:
        body = response.json()
    except ValueError as exc:
        raise DigiKeyAPIError("Mouser returned an unreadable response.", 502) from exc

    search = body.get("SearchResults") or {}
    products = search.get("Parts") or []
    normalized = lambda value: "".join(str(value or "").casefold().split())
    matches = []
    for product in products:
        if not isinstance(product, dict):
            continue
        tiers = []
        for entry in product.get("PriceBreaks") or []:
            try:
                price = float(str(entry.get("Price", "")).replace("$", "").replace(",", "").strip())
                break_quantity = int(entry.get("Quantity") or 0)
            except (TypeError, ValueError):
                continue
            if break_quantity > 0 and price >= 0:
                tiers.append({"break_quantity": break_quantity, "unit_price": price, "currency": "USD"})
        tier = select_price_tier(tiers, quantity)
        manufacturer_mpn = product.get("ManufacturerPartNumber") or ""
        available_quantity = _available_quantity(product)
        matches.append({
            "manufacturer_part_number": manufacturer_mpn,
            "manufacturer": product.get("Manufacturer") or "",
            "description": product.get("Description") or "",
            "category": product.get("Category") or "",
            "mouser_part_number": product.get("MouserPartNumber") or "",
            "exact_mpn_match": normalized(manufacturer_mpn) == normalized(mpn),
            "unit_price": tier["unit_price"] if tier else None,
            "break_quantity": tier["break_quantity"] if tier else None,
            "currency": "USD",
            "availability": product.get("Availability") or "",
            "available_quantity": available_quantity,
        })
    matches.sort(key=lambda item: (not item["exact_mpn_match"], item["unit_price"] is None))
    return matches
