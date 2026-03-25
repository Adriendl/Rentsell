"""Validate normalised listing data before persistence."""

from __future__ import annotations


def validate_listing(data: dict) -> tuple[bool, list[str]]:
    """Return ``(True, [])`` when *data* is acceptable, otherwise
    ``(False, [reasons])`` listing every violated constraint.
    """
    reasons: list[str] = []

    # price per square metre
    price_sqm = data.get("price_sqm", 0)
    if not (800 <= price_sqm <= 30_000):
        reasons.append(
            f"price_sqm {price_sqm} outside allowed range [800, 30000]"
        )

    # surface
    surface = data.get("surface", 0)
    if not (8 <= surface <= 500):
        reasons.append(
            f"surface {surface} outside allowed range [8, 500]"
        )

    # images
    images = data.get("images")
    if not images:
        reasons.append("images list is empty")

    # latitude
    lat = data.get("lat")
    if lat is None or not (41.3 <= lat <= 51.1):
        reasons.append(
            f"lat {lat} outside allowed range [41.3, 51.1]"
        )

    # longitude
    lng = data.get("lng")
    if lng is None or not (-5.2 <= lng <= 9.6):
        reasons.append(
            f"lng {lng} outside allowed range [-5.2, 9.6]"
        )

    return (len(reasons) == 0, reasons)
