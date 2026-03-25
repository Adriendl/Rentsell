"""Pydantic schemas for API responses."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, computed_field


class ListingOut(BaseModel):
    """Response schema matching the frontend apartments.json contract."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    city: str
    address: str | None = None
    lat: float
    lng: float
    surface: int
    rooms: int | None = None
    price: int
    images: list[str] = []

    # Frontend expects "source" as the listing URL, not the provider name.
    # The DB model stores provider in `source` and URL in `source_url`.
    source: str | None = None  # will be populated from source_url

    @classmethod
    def from_listing(cls, listing) -> ListingOut:
        return cls(
            id=listing.id,
            city=listing.city,
            address=listing.address,
            lat=listing.lat,
            lng=listing.lng,
            surface=listing.surface,
            rooms=listing.rooms,
            price=listing.price,
            images=listing.images or [],
            source=listing.source_url,
        )


class CityOut(BaseModel):
    city_slug: str
    city: str
    count: int
