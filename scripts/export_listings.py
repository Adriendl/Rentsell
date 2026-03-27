"""Scrape listings and export them to apartments.json (no database needed).

This script is designed to run in CI (GitHub Actions) to keep the static
JSON file up-to-date for the GitHub Pages frontend.

Stale listings (no longer online) are automatically purged to guarantee
that photos and source links remain valid for players.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import sys
from pathlib import Path

import httpx

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.scrapers.laforet import LaforetScraper, CITY_AGENCIES
from app.scrapers.pap import PapScraper, CITY_CODES
from app.pipeline.normalizer import normalize_listing, geocode
from app.pipeline.validator import validate_listing

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]

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


async def _check_url_alive(client: httpx.AsyncClient, url: str) -> bool:
    """Return True if URL responds with 2xx (HEAD then GET fallback)."""
    try:
        r = await client.head(url, follow_redirects=True, timeout=10)
        if r.status_code < 400:
            return True
        # Some servers reject HEAD — retry with GET
        r = await client.get(url, follow_redirects=True, timeout=10)
        return r.status_code < 400
    except Exception:
        return False


async def _verify_stale_listings(
    candidates: list[dict],
    all_listings: list[dict],
) -> tuple[int, int]:
    """Check that source URL and first image are still reachable.

    Returns (kept, dropped) counts.
    """
    kept = 0
    dropped = 0

    async with httpx.AsyncClient(
        headers={
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "fr-FR,fr;q=0.9",
        },
    ) as client:
        for listing in candidates:
            source_url = listing.get("source")
            images = listing.get("images", [])
            listing_label = (
                f"{listing.get('city', '?')} — "
                f"{listing.get('surface', '?')}m² — "
                f"{listing.get('price', '?')}€"
            )

            # 1. Check source URL (the listing page)
            source_ok = True
            if source_url:
                source_ok = await _check_url_alive(client, source_url)
                if not source_ok:
                    logger.info("  🗑  %s — annonce hors ligne", listing_label)
                    dropped += 1
                    continue

            # 2. Check first image is still reachable
            image_ok = True
            if images:
                image_ok = await _check_url_alive(client, images[0])
                if not image_ok:
                    logger.info(
                        "  🗑  %s — photo principale cassée", listing_label
                    )
                    dropped += 1
                    continue

            # 3. If no source URL and no images — drop (unusable)
            if not source_url and not images:
                logger.info("  🗑  %s — ni lien ni photo", listing_label)
                dropped += 1
                continue

            # All checks passed — keep
            logger.info("  ✅ %s — encore en ligne", listing_label)
            all_listings.append(listing)
            kept += 1

            # Polite delay between checks
            await asyncio.sleep(0.3)

    logger.info(
        "═══ Vérification terminée: %d conservées, %d supprimées ═══",
        kept, dropped,
    )
    return kept, dropped


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

    # ── Validate existing listings not found in this scrape ──────────
    existing: list[dict] = []
    if OUTPUT_PATH.exists():
        try:
            existing = json.loads(OUTPUT_PATH.read_text("utf-8"))
        except (json.JSONDecodeError, ValueError):
            pass

    new_ids = {str(l["id"]) for l in all_listings}
    stale_candidates = [
        old for old in existing
        if str(old.get("id", "")) not in new_ids
    ]

    kept = 0
    dropped = 0

    if stale_candidates:
        logger.info(
            "═══ Vérification de %d annonces non re-scrapées ═══",
            len(stale_candidates),
        )
        kept, dropped = await _verify_stale_listings(
            stale_candidates, all_listings
        )

    # ── Sort and write ──────────────────────────────────────────────
    all_listings.sort(key=lambda x: (x.get("city", ""), x.get("price", 0)))

    OUTPUT_PATH.write_text(
        json.dumps(all_listings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info(
        "✅ Exported %d listings to %s "
        "(Laforêt: %d, PAP: %d, kept: %d, dropped: %d)",
        len(all_listings), OUTPUT_PATH.name,
        laforet_count, pap_count, kept, dropped,
    )


if __name__ == "__main__":
    asyncio.run(scrape_and_export())
