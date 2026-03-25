"""Celery tasks for scraping, cleanup, and image mirroring."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.config import get_settings
from app.database import get_db, init_engine
from app.models import Listing
from app.pipeline.deduplicator import mark_inactive_stale, upsert_listing
from app.pipeline.normalizer import normalize_listing
from app.pipeline.validator import validate_listing
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

DEFAULT_CITIES = [
    "paris",
    "lyon",
    "marseille",
    "bordeaux",
    "toulouse",
    "nantes",
    "lille",
    "nice",
    "strasbourg",
]

SCRAPER_REGISTRY: dict[str, type] = {}


def _get_scraper(source_name: str):
    """Lazily import and return scraper class by name."""
    if not SCRAPER_REGISTRY:
        # Lazy import to avoid circular imports
        try:
            from app.scrapers.laforet import LaforetScraper
            SCRAPER_REGISTRY["laforet"] = LaforetScraper
        except ImportError:
            pass
        try:
            from app.scrapers.pap import PapScraper
            SCRAPER_REGISTRY["pap"] = PapScraper
        except ImportError:
            pass

    cls = SCRAPER_REGISTRY.get(source_name)
    if cls is None:
        raise ValueError(f"Unknown scraper source: {source_name}")
    return cls()


async def _run_scrape(source_name: str, city_slugs: list[str]):
    """Async implementation of the scrape pipeline."""
    init_engine()

    scraper = _get_scraper(source_name)
    total_inserted = 0
    total_skipped = 0

    async for session in get_db():
        for city_slug in city_slugs:
            logger.info("Scraping %s for city=%s", source_name, city_slug)
            try:
                raw_listings = await scraper.search(city_slug)
            except Exception:
                logger.exception("Error scraping %s / %s", source_name, city_slug)
                continue

            for raw in raw_listings:
                data = normalize_listing({
                    "source": raw.source,
                    "source_id": raw.source_id,
                    "source_url": raw.source_url,
                    "city": raw.city,
                    "address": raw.address,
                    "lat": raw.lat,
                    "lng": raw.lng,
                    "surface": raw.surface,
                    "rooms": raw.rooms,
                    "price": raw.price,
                    "images": raw.images_urls,
                })

                ok, reasons = validate_listing(data)
                if not ok:
                    logger.debug("Rejected listing %s: %s", raw.source_id, reasons)
                    total_skipped += 1
                    continue

                await upsert_listing(session, data)
                total_inserted += 1

        await session.commit()

    try:
        await scraper.close()
    except Exception:
        pass

    logger.info(
        "Scrape %s complete: %d inserted/updated, %d skipped",
        source_name,
        total_inserted,
        total_skipped,
    )


@celery_app.task(name="scrape_source")
def scrape_source(source_name: str, city_slugs: list[str]):
    """Scrape a single source for the given cities."""
    asyncio.run(_run_scrape(source_name, city_slugs))


@celery_app.task(name="scrape_all_sources")
def scrape_all_sources():
    """Scrape all known sources for all default cities."""
    scrape_source.delay("laforet", DEFAULT_CITIES)
    scrape_source.delay("pap", DEFAULT_CITIES)


async def _check_inactive():
    init_engine()
    async for session in get_db():
        await mark_inactive_stale(session)
        await session.commit()


@celery_app.task(name="check_inactive_listings")
def check_inactive_listings():
    """Mark stale listings as inactive."""
    asyncio.run(_check_inactive())


async def _mirror_images():
    settings = get_settings()
    if not settings.storage_bucket:
        logger.info("No storage bucket configured, skipping image mirroring")
        return

    init_engine()
    base_url = settings.storage_public_base_url

    async for session in get_db():
        result = await session.execute(
            select(Listing).where(Listing.is_active.is_(True))
        )
        listings = result.scalars().all()

        for listing in listings:
            needs_mirror = any(
                not url.startswith(base_url)
                for url in (listing.images or [])
                if base_url
            )
            if not needs_mirror:
                continue

            # Mirror images (placeholder for actual S3 upload logic)
            logger.info("Would mirror images for listing %s", listing.id)

        await session.commit()


@celery_app.task(name="mirror_pending_images")
def mirror_pending_images():
    """Find listings with non-mirrored images and mirror them."""
    asyncio.run(_mirror_images())
