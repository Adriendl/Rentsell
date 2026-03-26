"""Manual scraper runner CLI."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure backend is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.scrapers.laforet import LaforetScraper
from app.scrapers.pap import PapScraper
from app.pipeline.normalizer import normalize_listing, geocode
from app.pipeline.validator import validate_listing
from app.pipeline.deduplicator import compute_dedup_hash

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CITIES = [
    "paris", "lyon", "marseille", "bordeaux", "toulouse",
    "nantes", "lille", "nice", "strasbourg",
]

SCRAPERS = {
    "laforet": LaforetScraper,
    "pap": PapScraper,
}


async def run(source: str, cities: list[str], max_pages: int):
    scraper_cls = SCRAPERS.get(source)
    if not scraper_cls:
        logger.error("Unknown source: %s (available: %s)", source, list(SCRAPERS))
        return

    scraper = scraper_cls()
    total_found, valid, invalid = 0, 0, 0

    try:
        for city in cities:
            logger.info("Scraping %s — %s", source, city)
            raw_listings = await scraper.search(city, max_pages=max_pages)
            total_found += len(raw_listings)

            for raw in raw_listings:
                # Convert RawListing to dict and map images_urls → images
                raw_dict = raw.__dict__.copy()
                raw_dict["images"] = raw_dict.pop("images_urls", [])

                # Normalize
                data = normalize_listing(raw_dict)

                # Geocode if lat/lng missing
                if data.get("lat") is None or data.get("lng") is None:
                    city_name = data.get("city", "")
                    address = data.get("address") or city_name
                    coords = await geocode(address, city_name)
                    if coords:
                        data["lat"], data["lng"] = coords
                        logger.info("  📍 Geocoded %s → %.4f, %.4f", city_name, coords[0], coords[1])
                    else:
                        logger.warning("  ⚠ Could not geocode: %s", city_name)

                is_valid, reasons = validate_listing(data)
                if is_valid:
                    valid += 1
                    dedup = compute_dedup_hash(
                        data["city_slug"], data["surface"],
                        data.get("rooms"), data["price"],
                    )
                    logger.info(
                        "  ✓ %s — %d m² — %d € — %d imgs — hash=%s",
                        data["city"], data["surface"], data["price"],
                        len(data.get("images", [])), dedup[:12],
                    )
                else:
                    invalid += 1
                    logger.warning("  ✗ Rejected: %s", ", ".join(reasons))
    finally:
        await scraper.close()

    logger.info(
        "Done: %d found, %d valid, %d rejected",
        total_found, valid, invalid,
    )


def main():
    parser = argparse.ArgumentParser(description="Run a scraper manually")
    parser.add_argument("--source", required=True, choices=list(SCRAPERS))
    parser.add_argument("--cities", default=",".join(DEFAULT_CITIES),
                        help="Comma-separated city slugs")
    parser.add_argument("--max-pages", type=int, default=3)
    args = parser.parse_args()

    cities = [c.strip() for c in args.cities.split(",")]
    asyncio.run(run(args.source, cities, args.max_pages))


if __name__ == "__main__":
    main()
