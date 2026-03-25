"""Listing endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from slugify import slugify
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import func

from app.database import get_db
from app.models import Listing
from app.schemas import ListingOut

router = APIRouter()


@router.get("/listings", response_model=list[ListingOut])
async def get_listings(
    city: str | None = None,
    limit: int = Query(default=10, le=50),
    random: bool = False,
    exclude_recent: bool = True,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Listing).where(Listing.is_active.is_(True))

    if city:
        city_slug = slugify(city)
        stmt = stmt.where(Listing.city_slug == city_slug)

    if exclude_recent:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = stmt.where(
            (Listing.last_served_at.is_(None)) | (Listing.last_served_at < cutoff)
        )

    if random:
        stmt = stmt.order_by(func.random())

    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    listings = result.scalars().all()

    # Batch update last_served_at for random queries
    if random and listings:
        ids = [l.id for l in listings]
        await db.execute(
            update(Listing)
            .where(Listing.id.in_(ids))
            .values(last_served_at=datetime.now(timezone.utc))
        )
        await db.flush()

    return [ListingOut.from_listing(l) for l in listings]


@router.get("/listings/{listing_id}", response_model=ListingOut)
async def get_listing(listing_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return ListingOut.from_listing(listing)
