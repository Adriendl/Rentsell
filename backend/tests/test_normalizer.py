"""Tests for the normalizer module."""

from app.pipeline.normalizer import make_city_slug, parse_price, parse_surface


class TestParseSurface:
    def test_with_m2_space(self):
        assert parse_surface("58 m2") == 58

    def test_with_comma_m2(self):
        assert parse_surface("33,5 m²") == 33

    def test_with_dot_no_space(self):
        assert parse_surface("68.5m2") == 68

    def test_int_string(self):
        assert parse_surface("120") == 120


class TestParsePrice:
    def test_with_spaces_and_euro(self):
        assert parse_price("300 000 €") == 300_000

    def test_plain_int_string(self):
        assert parse_price("282000") == 282_000

    def test_million_with_spaces(self):
        assert parse_price("1 200 000€") == 1_200_000


class TestMakeCitySlug:
    def test_paris_arrondissement(self):
        assert make_city_slug("Paris 15e - Lourmel") == "paris-15e-lourmel"

    def test_lyon_eme(self):
        assert make_city_slug("Lyon 2ème") == "lyon-2eme"
