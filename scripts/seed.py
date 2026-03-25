"""Seed the database with apartments.json data."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

# Ensure backend is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.pipeline.deduplicator import compute_dedup_hash
from app.pipeline.normalizer import make_city_slug

from sqlalchemy import select


def extract_source_id(url: str) -> str:
    """Extract numeric ID from a Laforet listing URL."""
    match = re.search(r"/(\d{5,})", url)
    return match.group(1) if match else url.split("/")[-1]


async def seed():
    # Import and init engine, then grab the live references
    from app.database import Base, init_engine, engine as _eng
    init_engine()

    # Re-import after init to get the actual objects (not the initial None)
    import app.database as db
    from app.models import Listing, PriceHistory

    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    json_path = Path(__file__).resolve().parent.parent / "apartments.json"
    if not json_path.exists():
        print(f"❌ {json_path} not found")
        return

    apartments = json.loads(json_path.read_text("utf-8"))
    inserted, skipped = 0, 0

    async with db.async_session_maker() as session:
        for apt in apartments:
            city_slug = make_city_slug(apt["city"])
            price = int(apt["price"])
            surface = int(apt["surface"])
            rooms = apt.get("rooms")
            dedup_hash = compute_dedup_hash(city_slug, surface, rooms, price)

            exists = await session.execute(
                select(Listing).where(Listing.dedup_hash == dedup_hash)
            )
            if exists.scalar_one_or_none():
                skipped += 1
                continue

            listing = Listing(
                source="laforet",
                source_id=extract_source_id(apt.get("source", "")),
                dedup_hash=dedup_hash,
                city=apt["city"],
                city_slug=city_slug,
                address=apt.get("address"),
                lat=float(apt["lat"]),
                lng=float(apt["lng"]),
                surface=surface,
                rooms=rooms,
                price=price,
                price_sqm=price // surface if surface > 0 else 0,
                images=apt.get("images", []),
                source_url=apt.get("source"),
                is_active=True,
            )
            history = PriceHistory(price=price)
            listing.price_history.append(history)
            session.add(listing)
            inserted += 1

        await session.commit()

    print(f"✅ Seed complete: {inserted} inserted, {skipped} skipped (already exist)")


if __name__ == "__main__":
    asyncio.run(seed())
