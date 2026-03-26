"""Scraper for laforet.com apartment sale listings.

Strategy: Laforêt's search page is a SPA (results loaded via JS), so we
scrape **agency pages** instead, which contain static HTML with GTM
data-attributes providing structured data (price, surface, rooms, city,
zipcode, id).

For each target city we maintain a list of known agency slugs. The
agency page at /agence-immobiliere/{slug} lists all properties handled
by that office.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.scrapers.base import AbstractScraper, RawListing
from app.scrapers.http_scraper import HttpScraperMixin

logger = logging.getLogger(__name__)

BASE_URL = "https://www.laforet.com"
CDN_BASE = "https://laforetbusiness.laforet-intranet.com"

# ── Known agency slugs per city ──────────────────────────────────────
# Each agency's page lists the properties they manage (statically rendered).
# When the scraper runs it fetches each agency page for the requested city.
# This list can be extended over time.
CITY_AGENCIES: dict[str, list[str]] = {
    "paris": [
        "paris6", "paris-batignolles", "paris-convention",
        "paris-marais", "paris-republique", "paris-daumesnil",
        "paris-nation", "paris-auteuil", "boulogne-nord",
    ],
    "lyon": [
        "lyon2-bellecour", "lyon3", "lyon6", "lyon7",
        "lyon8", "villeurbanne",
    ],
    "marseille": [
        "marseille-castellane", "marseille-13008",
        "marseille-saint-barnabe", "aubagne",
    ],
    "bordeaux": [
        "bordeaux-saint-seurin", "bordeaux-cauderan",
        "bordeaux-chartrons", "pessac",
    ],
    "toulouse": [
        "toulouse-capitole", "toulouse-minimes",
        "toulouse-rangueil", "blagnac",
    ],
    "nantes": [
        "nantes", "reze",
    ],
    "lille": [
        "lille", "lille-fives", "villeneuve-d-ascq",
    ],
    "nice": [
        "nice", "nice-ouest", "antibes",
    ],
    "strasbourg": [
        "strasbourg", "strasbourg-neudorf", "illkirch",
    ],
}


def _slugify_city(city: str) -> str:
    slug = unicodedata.normalize("NFD", city)
    slug = slug.encode("ascii", "ignore").decode("ascii")
    slug = slug.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    return slug


class LaforetScraper(HttpScraperMixin, AbstractScraper):
    """Scraper for laforet.com — apartment purchases via agency pages."""

    source_name = "laforet"

    # ------------------------------------------------------------------
    # Search — iterate over agency pages for the requested city
    # ------------------------------------------------------------------

    async def search(self, city: str, max_pages: int = 5) -> list[RawListing]:
        city_key = _slugify_city(city)
        agencies = CITY_AGENCIES.get(city_key, [])

        if not agencies:
            logger.warning("No known agencies for city '%s'", city)
            return []

        all_listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for agency_slug in agencies:
            url = f"{BASE_URL}/agence-immobiliere/{agency_slug}"
            logger.info("  Fetching agency page: %s", agency_slug)

            try:
                soup = await self._soup(url)
            except Exception as exc:
                logger.warning("  Failed to fetch %s: %s", url, exc)
                continue

            cards = self._parse_gtm_cards(soup, city)

            for card in cards:
                if card.source_id not in seen_ids:
                    seen_ids.add(card.source_id)
                    all_listings.append(card)

        logger.info(
            "  City '%s': %d unique apartments from %d agencies",
            city, len(all_listings), len(agencies),
        )
        return all_listings

    # ------------------------------------------------------------------
    # Parse GTM data-attribute cards
    # ------------------------------------------------------------------

    def _parse_gtm_cards(self, soup: BeautifulSoup, city: str) -> list[RawListing]:
        results: list[RawListing] = []

        buttons = soup.select("button[data-gtm-item-id-param]")

        for btn in buttons:
            item_type = btn.get("data-gtm-item-type-param", "").lower()
            txn_type = btn.get("data-gtm-transaction-type-param", "")

            # Only keep apartments for sale
            if item_type != "appartement" or txn_type != "acheter":
                continue

            source_id = btn.get("data-gtm-item-id-param", "")
            price_str = btn.get("data-gtm-item-price-param", "0")
            size_str = btn.get("data-gtm-item-size-param", "0")
            rooms_str = btn.get("data-gtm-item-rooms-nb-param", "")
            item_city = btn.get("data-gtm-item-city-param", city)
            zipcode = btn.get("data-gtm-item-zipcode-param", "")

            try:
                price = int(float(price_str))
            except (ValueError, TypeError):
                price = 0

            try:
                surface = int(float(size_str))
            except (ValueError, TypeError):
                surface = 0

            try:
                rooms = int(rooms_str) if rooms_str else None
            except (ValueError, TypeError):
                rooms = None

            # Find the parent card container
            card_el = btn.find_parent(
                "div",
                class_=lambda c: c and "border" in c and "rounded" in c,
            )
            if not card_el:
                card_el = btn.find_parent("div")

            # Extract detail URL
            detail_url = ""
            if card_el:
                link = card_el.select_one(
                    "a[href*='/acheter/']"
                )
                if link:
                    href = link.get("href", "")
                    detail_url = href if href.startswith("http") else urljoin(BASE_URL, href)

            # Extract images
            images = self._extract_card_images(card_el)

            raw = RawListing(
                source=self.source_name,
                source_id=source_id,
                source_url=detail_url,
                city=f"{item_city} ({zipcode})" if zipcode else item_city,
                price=price,
                surface=surface,
                rooms=rooms,
                images_urls=images,
                raw_data={"zipcode": zipcode, "type": item_type},
            )
            results.append(raw)

        return results

    # ------------------------------------------------------------------
    # Detail page (for enriching with lat/lng + full image gallery)
    # ------------------------------------------------------------------

    async def get_detail(self, url: str) -> RawListing | None:
        if not url:
            return None

        soup = await self._soup(url)

        btn = soup.select_one("button[data-gtm-item-id-param]")
        source_id = ""
        price = 0
        surface = 0
        rooms = None
        city = ""
        zipcode = ""

        if btn:
            source_id = btn.get("data-gtm-item-id-param", "")
            try:
                price = int(float(btn.get("data-gtm-item-price-param", "0")))
            except (ValueError, TypeError):
                price = 0
            try:
                surface = int(float(btn.get("data-gtm-item-size-param", "0")))
            except (ValueError, TypeError):
                surface = 0
            try:
                rooms_str = btn.get("data-gtm-item-rooms-nb-param", "")
                rooms = int(rooms_str) if rooms_str else None
            except (ValueError, TypeError):
                rooms = None
            city = btn.get("data-gtm-item-city-param", "")
            zipcode = btn.get("data-gtm-item-zipcode-param", "")

        if not source_id:
            source_id = url.rstrip("/").split("/")[-1]

        images = self._extract_page_images(soup)
        lat, lng = self._extract_coords(soup)

        return RawListing(
            source=self.source_name,
            source_id=source_id,
            source_url=url,
            city=f"{city} ({zipcode})" if zipcode else city,
            lat=lat,
            lng=lng,
            surface=surface,
            rooms=rooms,
            price=price,
            images_urls=images,
            raw_data={"zipcode": zipcode},
        )

    # ------------------------------------------------------------------
    # Image extraction helpers
    # ------------------------------------------------------------------

    def _extract_card_images(self, card_el: Tag | None) -> list[str]:
        """Extract images from a search card element."""
        if not card_el:
            return []
        urls: list[str] = []
        seen: set[str] = set()
        for img in card_el.select("img[src*='/glide/']"):
            src = img.get("src", "")
            if "/glide/services/" in src:
                continue
            if src and src not in seen:
                seen.add(src)
                urls.append(self._glide_to_cdn(src))
        return urls

    def _extract_page_images(self, soup: BeautifulSoup) -> list[str]:
        """Extract all property images from a detail page."""
        urls: list[str] = []
        seen: set[str] = set()

        for img in soup.select("img[src*='/glide/']"):
            src = img.get("src", "")
            if "/glide/services/" in src:
                continue
            if src and src not in seen:
                seen.add(src)
                urls.append(self._glide_to_cdn(src))

        # Fallback: JSON-LD
        if not urls:
            for script_tag in soup.find_all("script", {"type": "application/ld+json"}):
                try:
                    data = json.loads(script_tag.string or "")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        for key in ("image", "photo", "photos", "images"):
                            val = item.get(key)
                            if isinstance(val, str) and val not in seen:
                                seen.add(val)
                                urls.append(val)
                            elif isinstance(val, list):
                                for v in val:
                                    if isinstance(v, str) and v not in seen:
                                        seen.add(v)
                                        urls.append(v)
                except (json.JSONDecodeError, TypeError):
                    continue

        return urls

    # ------------------------------------------------------------------
    # Coordinates extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _glide_to_cdn(src: str) -> str:
        """Convert a /glide/... path to the public CDN URL (no auth/hotlink issue)."""
        # /glide/office6/laforet_.../52365738a.jpg?w=800&...
        # → https://laforetbusiness.laforet-intranet.com/office6/laforet_.../52365738a.jpg
        path = src.split("?")[0]  # strip query params
        if path.startswith("/glide/"):
            path = path[len("/glide/"):]
        elif "/glide/" in path:
            path = path.split("/glide/", 1)[1]
        return f"{CDN_BASE}/{path}"

    def _extract_coords(self, soup: BeautifulSoup) -> tuple[float | None, float | None]:
        for el in soup.select("[data-lat][data-lng], [data-latitude][data-longitude]"):
            try:
                lat = float(el.get("data-lat") or el.get("data-latitude") or "")
                lng = float(el.get("data-lng") or el.get("data-longitude") or "")
                return lat, lng
            except (ValueError, TypeError):
                continue

        coord_pattern = re.compile(
            r'"lat(?:itude)?"\s*:\s*([\d.]+)\s*,\s*"(?:lng|lon(?:gitude)?)"\s*:\s*([\d.]+)'
        )
        for script_tag in soup.find_all("script"):
            text = script_tag.string or ""
            m = coord_pattern.search(text)
            if m:
                try:
                    return float(m.group(1)), float(m.group(2))
                except (ValueError, IndexError):
                    continue

        return None, None
