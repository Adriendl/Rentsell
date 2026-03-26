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
from app.pipeline.normalizer import normalize_listing, geocode
from app.pipeline.validator import validate_listing

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "apartments.json"


async def scrape_and_export():
    scraper = LaforetScraper()
    all_listings: list[dict] = []
    seen_keys: set[str] = set()

    cities = list(CITY_AGENCIES.keys())
    logger.info("Scraping %d cities: %s", len(cities), ", ".join(cities))

    try:
        for city in cities:
            logger.info("🏙  Scraping %s...", city)
            try:
                raw_listings = await scraper.search(city, max_pages=1)
            except Exception as exc:
                logger.warning("  ⚠ Failed to scrape %s: %s", city, exc)
                continue

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

                # Deduplicate by source_id
                source_id = data.get("source_id", "")
                if source_id in seen_keys:
                    continue
                seen_keys.add(source_id)

                # Format for frontend consumption
                listing = {
                    "id": source_id,
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

    finally:
        await scraper.close()

    # Merge with existing listings to avoid losing data on partial failures
    existing: list[dict] = []
    if OUTPUT_PATH.exists():
        try:
            existing = json.loads(OUTPUT_PATH.read_text("utf-8"))
        except (json.JSONDecodeError, ValueError):
            pass

    # Keep existing listings not found in new scrape (different source_ids)
    new_ids = {str(l["id"]) for l in all_listings}
    for old in existing:
        if str(old.get("id", "")) not in new_ids:
            all_listings.append(old)

    # Sort by city for readability
    all_listings.sort(key=lambda x: (x.get("city", ""), x.get("price", 0)))

    OUTPUT_PATH.write_text(
        json.dumps(all_listings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info("✅ Exported %d listings to %s", len(all_listings), OUTPUT_PATH.name)


if __name__ == "__main__":
    asyncio.run(scrape_and_export())
