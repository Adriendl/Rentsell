"""Tests for the deduplicator module."""

import pytest

from app.models import Listing
from app.pipeline.deduplicator import compute_dedup_hash, upsert_listing


class TestComputeDedupHash:
    def test_deterministic(self):
        h1 = compute_dedup_hash("paris-15e", 60, 3, 300_000)
        h2 = compute_dedup_hash("paris-15e", 60, 3, 300_000)
        assert h1 == h2

    def test_different_price_buckets(self):
        h1 = compute_dedup_hash("paris-15e", 60, 3, 200_000)
        h2 = compute_dedup_hash("paris-15e", 60, 3, 400_000)
        assert h1 != h2

    def test_same_price_bucket(self):
        # Both 299000 and 301000 round to 300000 (nearest 5000)
        h1 = compute_dedup_hash("paris-15e", 60, 3, 299_000)
        h2 = compute_dedup_hash("paris-15e", 60, 3, 301_000)
        assert h1 == h2


@pytest.mark.asyncio
class TestUpsertListing:
    async def test_insert_then_upsert(self, async_session):
        data = {
            "source": "laforet",
            "source_id": "123",
            "source_url": "https://example.com/123",
            "city": "Paris 15e",
            "city_slug": "paris-15e",
            "address": "20 rue test",
            "lat": 48.85,
            "lng": 2.29,
            "surface": 60,
            "rooms": 3,
            "price": 300_000,
            "price_sqm": 5000,
            "images": ["https://example.com/img.jpg"],
        }

        # First insert
        listing1 = await upsert_listing(async_session, data)
        await async_session.commit()
        assert listing1.id is not None
        first_seen = listing1.last_seen_at

        # Upsert same hash - should update last_seen_at
        listing2 = await upsert_listing(async_session, data)
        await async_session.commit()
        assert listing2.id == listing1.id
        assert listing2.last_seen_at >= first_seen
