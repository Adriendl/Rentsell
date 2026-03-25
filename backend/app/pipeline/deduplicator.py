"""Deduplicate listings using a content-based hash and upsert logic."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing, PriceHistory


def compute_dedup_hash(
    city_slug: str,
    surface: int,
    rooms: int | None,
    price: int,
) -> str:
    """SHA-256 of ``city_slug|surface|rooms|price_bucket``.

    *price_bucket* rounds the price to the nearest 5 000.
    """
    price_bucket = round(price / 5000) * 5000
    raw = f"{city_slug}|{surface}|{rooms}|{price_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def upsert_listing(session: AsyncSession, data: dict) -> Listing:
    """Insert or update a listing based on its *dedup_hash*.

    If the hash already exists the existing row is refreshed
    (``last_seen_at``, ``is_active``).  A new :class:`PriceHistory` entry
    is added when the price has changed.

    If the hash is new a fresh :class:`Listing` and an initial
    :class:`PriceHistory` row are created.
    """
    dedup_hash = compute_dedup_hash(
        data["city_slug"],
        data["surface"],
        data.get("rooms"),
        data["price"],
    )

    stmt = select(Listing).where(Listing.dedup_hash == dedup_hash)
    result = await session.execute(stmt)
    existing: Listing | None = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing is not None:
        existing.last_seen_at = now
        existing.is_active = True

        if existing.price != data["price"]:
            existing.price = data["price"]
            existing.price_sqm = data.get("price_sqm")
            session.add(
                PriceHistory(listing_id=existing.id, price=data["price"])
            )

        await session.flush()
        return existing

    listing = Listing(
        source=data.get("source", "unknown"),
        source_id=data.get("source_id", ""),
        dedup_hash=dedup_hash,
        city=data["city"],
        city_slug=data["city_slug"],
        insee_code=data.get("insee_code"),
        address=data.get("address"),
        lat=data["lat"],
        lng=data["lng"],
        surface=data["surface"],
        rooms=data.get("rooms"),
        price=data["price"],
        price_sqm=data.get("price_sqm"),
        images=data.get("images", []),
        source_url=data.get("source_url"),
        is_active=True,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(listing)
    await session.flush()

    session.add(PriceHistory(listing_id=listing.id, price=data["price"]))
    await session.flush()

    return listing


async def mark_inactive_stale(
    session: AsyncSession,
    cutoff_days: int = 7,
) -> None:
    """Set ``is_active=False`` and ``sold_at=now()`` for listings whose
    ``last_seen_at`` is older than *cutoff_days* days.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=cutoff_days)

    stmt = select(Listing).where(
        Listing.is_active.is_(True),
        Listing.last_seen_at < cutoff,
    )
    result = await session.execute(stmt)
    stale_listings = result.scalars().all()

    for listing in stale_listings:
        listing.is_active = False
        listing.sold_at = now

    await session.flush()
