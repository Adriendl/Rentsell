"""Scrape listings and export them to apartments.json (no database needed).

This script is designed to run in CI (GitHub Actions) to keep the static
JSON file up-to-date for the GitHub Pages frontend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.scrapers.laforet import LaforetScraper, CITY_AGENCIES
from app.scrapers.pap import PapScraper, CITY_CODES
from app.pipeline.normalizer import normalize_listing, geocode
from app.pipeline.validator import validate_listing

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "apartments.json"


async def _process_raw_listings(raw_listings, all_listings, seen_keys):
    """Normalize, geocode, validate, deduplicate a batch of RawListings."""
    count = 0
    for raw in raw_listings:
        raw_dict = raw.__dict__.copy()
        raw_dict["images"] = raw_dict.pop("images_urls", [])

        # Normalize
        data = normalize_listing(raw_dict)

        # Geocode if needed
        if data.get("lat") is None or data.get("lng") is None:
            city_name = data.get("city", "")
            address = data.get("address") or city_name
            try:
                coords = await geocode(address, city_name)
                if coords:
                    data["lat"], data["lng"] = coords
            except Exception:
                pass

        # Validate
        is_valid, reasons = validate_listing(data)
        if not is_valid:
            continue

        # Deduplicate by source + source_id
        dedup_key = f"{data.get('source', '')}:{data.get('source_id', '')}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        # Format for frontend consumption
        listing = {
            "id": data.get("source_id", ""),
            "city": data["city"],
            "lat": data["lat"],
            "lng": data["lng"],
            "surface": data["surface"],
            "rooms": data.get("rooms"),
            "price": data["price"],
            "images": data.get("images", []),
            "source": data.get("source_url"),
        }
        all_listings.append(listing)
        count += 1

    return count


async def scrape_and_export():
    all_listings: list[dict] = []
    seen_keys: set[str] = set()

    # ── Laforêt ──────────────────────────────────────────────────────
    laforet = LaforetScraper()
    laforet_cities = list(CITY_AGENCIES.keys())
    logger.info("═══ Laforêt: scraping %d cities ═══", len(laforet_cities))

    try:
        for city in laforet_cities:
            logger.info("🏙  Laforêt — %s", city)
            try:
                raw = await laforet.search(city, max_pages=1)
                added = await _process_raw_listings(raw, all_listings, seen_keys)
                logger.info("  ✓ %d valid listings added", added)
            except Exception as exc:
                logger.warning("  ⚠ Failed: %s", exc)
    finally:
        await laforet.close()

    laforet_count = len(all_listings)
    logger.info("═══ Laforêt total: %d listings ═══\n", laforet_count)

    # ── PAP ──────────────────────────────────────────────────────────
    pap = PapScraper()
    pap_cities = list(CITY_CODES.keys())
    logger.info("═══ PAP: scraping %d cities ═══", len(pap_cities))

    try:
        for city in pap_cities:
            logger.info("🏙  PAP — %s", city)
            try:
                raw = await pap.search(city, max_pages=2)
                added = await _process_raw_listings(raw, all_listings, seen_keys)
                logger.info("  ✓ %d valid listings added", added)
            except Exception as exc:
                logger.warning("  ⚠ Failed: %s", exc)
    finally:
        await pap.close()

    pap_count = len(all_listings) - laforet_count
    logger.info("═══ PAP total: %d listings ═══\n", pap_count)

    # ── Merge with existing data ─────────────────────────────────────
    existing: list[dict] = []
    if OUTPUT_PATH.exists():
        try:
            existing = json.loads(OUTPUT_PATH.read_text("utf-8"))
        except (json.JSONDecodeError, ValueError):
            pass

    # Keep existing listings not found in new scrape
    new_ids = {str(l["id"]) for l in all_listings}
    kept = 0
    for old in existing:
        if str(old.get("id", "")) not in new_ids:
            all_listings.append(old)
            kept += 1

    if kept:
        logger.info("Kept %d existing listings not found in this scrape", kept)

    # Sort by city for readability
    all_listings.sort(key=lambda x: (x.get("city", ""), x.get("price", 0)))

    OUTPUT_PATH.write_text(
        json.dumps(all_listings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info(
        "✅ Exported %d listings to %s (Laforêt: %d, PAP: %d, existing: %d)",
        len(all_listings), OUTPUT_PATH.name, laforet_count, pap_count, kept,
    )


if __name__ == "__main__":
    asyncio.run(scrape_and_export())
