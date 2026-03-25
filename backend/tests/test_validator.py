"""Tests for the validator module."""

from app.pipeline.validator import validate_listing


def _valid_data(**overrides) -> dict:
    base = {
        "price_sqm": 5000,
        "surface": 60,
        "images": ["https://example.com/img.jpg"],
        "lat": 48.85,
        "lng": 2.35,
    }
    base.update(overrides)
    return base


class TestValidListing:
    def test_valid_passes(self):
        ok, reasons = validate_listing(_valid_data())
        assert ok is True
        assert reasons == []


class TestPriceSqmBounds:
    def test_too_low(self):
        ok, reasons = validate_listing(_valid_data(price_sqm=500))
        assert ok is False
        assert any("price_sqm" in r for r in reasons)

    def test_too_high(self):
        ok, reasons = validate_listing(_valid_data(price_sqm=35000))
        assert ok is False
        assert any("price_sqm" in r for r in reasons)


class TestSurfaceBounds:
    def test_too_small(self):
        ok, reasons = validate_listing(_valid_data(surface=5))
        assert ok is False
        assert any("surface" in r for r in reasons)

    def test_too_large(self):
        ok, reasons = validate_listing(_valid_data(surface=600))
        assert ok is False
        assert any("surface" in r for r in reasons)


class TestImages:
    def test_empty_images(self):
        ok, reasons = validate_listing(_valid_data(images=[]))
        assert ok is False
        assert any("images" in r for r in reasons)


class TestLatLng:
    def test_lat_outside_france(self):
        ok, reasons = validate_listing(_valid_data(lat=30.0))
        assert ok is False
        assert any("lat" in r for r in reasons)

    def test_lng_outside_france(self):
        ok, reasons = validate_listing(_valid_data(lng=15.0))
        assert ok is False
        assert any("lng" in r for r in reasons)
