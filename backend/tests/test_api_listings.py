"""Tests for the listings and cities API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.models import Listing
from app.pipeline.deduplicator import compute_dedup_hash


@pytest.fixture
async def sample_listings(async_session):
    """Insert sample listings for testing."""
    listings = []
    for i in range(6):
        city = "Paris 15e" if i < 5 else "Lyon 3e"
        city_slug = "paris-15e" if i < 5 else "lyon-3e"
        price = 200_000 + i * 50_000
        surface = 30 + i * 10
        listing = Listing(
            source="test",
            source_id=f"test-{i}",
            dedup_hash=compute_dedup_hash(city_slug, surface, 2, price),
            city=city,
            city_slug=city_slug,
            address=f"{i} rue de Test",
            lat=48.85 + i * 0.001,
            lng=2.29 + i * 0.001,
            surface=surface,
            rooms=2,
            price=price,
            price_sqm=price // surface,
            images=[f"https://example.com/img{i}.jpg"],
            source_url=f"https://example.com/listing/{i}",
            is_active=True,
        )
        async_session.add(listing)
        listings.append(listing)
    await async_session.commit()
    for l in listings:
        await async_session.refresh(l)
    return listings


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_listings_empty(client):
    resp = await client.get("/listings")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_listings_returns_data(client, sample_listings):
    resp = await client.get("/listings")
    data = resp.json()
    assert len(data) == 6


@pytest.mark.asyncio
async def test_listings_limit(client, sample_listings):
    resp = await client.get("/listings?limit=2")
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_listings_by_id(client, sample_listings):
    lid = sample_listings[0].id
    resp = await client.get(f"/listings/{lid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == lid


@pytest.mark.asyncio
async def test_listings_by_id_not_found(client):
    resp = await client.get("/listings/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_listings_source_is_url(client, sample_listings):
    """Frontend expects 'source' to be the listing URL."""
    resp = await client.get("/listings")
    data = resp.json()
    assert data[0]["source"].startswith("https://")


@pytest.mark.asyncio
async def test_cities_empty_below_threshold(client, sample_listings):
    """Only cities with >= 5 active listings should appear."""
    resp = await client.get("/cities")
    data = resp.json()
    slugs = [c["city_slug"] for c in data]
    assert "paris-15e" in slugs  # 5 listings
    assert "lyon-3e" not in slugs  # only 1 listing
