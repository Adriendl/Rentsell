"""City endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Listing
from app.schemas import CityOut

router = APIRouter()


@router.get("/cities", response_model=list[CityOut])
async def get_cities(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(
            Listing.city_slug,
            Listing.city,
            func.count().label("count"),
        )
        .where(Listing.is_active.is_(True))
        .group_by(Listing.city_slug, Listing.city)
        .having(func.count() >= 5)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [CityOut(city_slug=r.city_slug, city=r.city, count=r.count) for r in rows]
