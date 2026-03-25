"""Normalize raw listing data coming from scrapers."""

from __future__ import annotations

import re

import httpx
from slugify import slugify

# ── Canonical city slugs ────────────────────────────────────────────────
_CANONICAL: dict[str, str] = {}

# Paris arrondissements
for _i in range(1, 21):
    _CANONICAL[f"paris {_i}e"] = f"paris-{_i}e"
    _CANONICAL[f"paris {_i}e arrondissement"] = f"paris-{_i}e"
    _CANONICAL[f"paris {_i}eme"] = f"paris-{_i}e"
    _CANONICAL[f"paris {_i}eme arrondissement"] = f"paris-{_i}e"
    if _i == 1:
        _CANONICAL["paris 1er"] = "paris-1e"
        _CANONICAL["paris 1er arrondissement"] = "paris-1e"

# Lyon arrondissements
for _i in range(1, 10):
    _CANONICAL[f"lyon {_i}e"] = f"lyon-{_i}e"
    _CANONICAL[f"lyon {_i}e arrondissement"] = f"lyon-{_i}e"
    _CANONICAL[f"lyon {_i}eme"] = f"lyon-{_i}e"
    if _i == 1:
        _CANONICAL["lyon 1er"] = "lyon-1e"

# Marseille arrondissements
for _i in range(1, 17):
    _CANONICAL[f"marseille {_i}e"] = f"marseille-{_i}e"
    _CANONICAL[f"marseille {_i}e arrondissement"] = f"marseille-{_i}e"
    _CANONICAL[f"marseille {_i}eme"] = f"marseille-{_i}e"
    if _i == 1:
        _CANONICAL["marseille 1er"] = "marseille-1e"

# Other major cities
for _city in (
    "Bordeaux",
    "Toulouse",
    "Nantes",
    "Lille",
    "Nice",
    "Strasbourg",
):
    _CANONICAL[_city.lower()] = slugify(_city)


# ── Parsers ─────────────────────────────────────────────────────────────


def parse_surface(value: str | int | float) -> int:
    """Parse surface strings like '58 m2', '33,5 m²', '68.5m2', 68 → int."""
    if isinstance(value, (int, float)):
        return int(value)
    cleaned = str(value).strip().lower()
    cleaned = cleaned.replace(",", ".")
    cleaned = cleaned.replace("m²", "").replace("m2", "").strip()
    return int(float(cleaned))


def parse_price(value: str | int) -> int:
    """Remove spaces / € / FAI and return an int.  '300 000 €' → 300000."""
    if isinstance(value, int):
        return value
    cleaned = str(value).strip()
    cleaned = cleaned.upper().replace("FAI", "").replace("€", "")
    cleaned = re.sub(r"[^\d]", "", cleaned)
    return int(cleaned)


def make_city_slug(city: str) -> str:
    """Return a canonical city slug using python-slugify."""
    key = city.strip().lower()
    if key in _CANONICAL:
        return _CANONICAL[key]
    return slugify(city)


async def geocode(address: str, city: str) -> tuple[float, float] | None:
    """Call the French government geocoding API, return (lat, lng) or None."""
    query = f"{address} {city}".strip()
    url = "https://api-adresse.data.gouv.fr/search/"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params={"q": query, "limit": 1})
        if resp.status_code != 200:
            return None
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        coords = features[0]["geometry"]["coordinates"]  # [lng, lat]
        return (coords[1], coords[0])


def normalize_listing(raw_data: dict) -> dict:
    """Apply all normalisations to a raw listing dict.

    Expected keys in *raw_data*: ``price``, ``surface``, ``city``,
    ``images``, and optionally ``address``, ``rooms``, ``source``,
    ``source_id``, ``source_url``.

    Returns a new dict augmented with ``price_sqm`` and ``city_slug``.
    """
    data = dict(raw_data)

    data["price"] = parse_price(data["price"])
    data["surface"] = parse_surface(data["surface"])
    data["city_slug"] = make_city_slug(data["city"])

    if data["surface"] > 0:
        data["price_sqm"] = data["price"] // data["surface"]
    else:
        data["price_sqm"] = 0

    return data
