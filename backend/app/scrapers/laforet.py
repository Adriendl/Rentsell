"""Scraper for laforet.com apartment sale listings."""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup, Tag

from app.scrapers.base import AbstractScraper, RawListing
from app.scrapers.http_scraper import HttpScraperMixin

BASE_URL = "https://www.laforet.com"


def _slugify_city(city: str) -> str:
    """Normalise a city name for URL insertion (e.g. 'Saint-Étienne' -> 'saint-etienne')."""
    import unicodedata

    slug = unicodedata.normalize("NFD", city)
    slug = slug.encode("ascii", "ignore").decode("ascii")
    slug = slug.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    return slug


def _extract_number(text: str | None) -> int | None:
    """Extract the first integer from a text string."""
    if not text:
        return None
    m = re.search(r"[\d\s]+", text.replace("\xa0", " "))
    if m:
        return int(m.group().replace(" ", "").strip())
    return None


class LaforetScraper(HttpScraperMixin, AbstractScraper):
    """Scraper for laforet.com — apartment purchases."""

    source_name = "laforet"

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(self, city: str, max_pages: int = 5) -> list[RawListing]:
        listings: list[RawListing] = []
        city_slug = _slugify_city(city)

        for page in range(1, max_pages + 1):
            url = (
                f"{BASE_URL}/acheter?"
                f"types%5B%5D=appartement"
                f"&localisation={quote(city_slug, safe='')}"
                f"&page={page}"
            )
            soup = await self._soup(url)
            cards = self._parse_search_cards(soup, city)

            if not cards:
                break

            listings.extend(cards)

        return listings

    # ------------------------------------------------------------------
    # Search-page parsing
    # ------------------------------------------------------------------

    def _parse_search_cards(self, soup: BeautifulSoup, city: str) -> list[RawListing]:
        results: list[RawListing] = []

        # Laforet renders property cards inside <a> or <article> elements
        # with a link to /detail/vente/... or /acheter/...
        card_links = soup.select("a[href*='/acheter/'], a[href*='/detail/vente/']")
        if not card_links:
            # Fallback: try generic property card containers
            card_links = soup.select(".card-property a[href], .property-card a[href]")

        seen_urls: set[str] = set()
        for link_tag in card_links:
            href = link_tag.get("href", "")
            if not href or href in seen_urls:
                continue
            detail_url = urljoin(BASE_URL, href)
            seen_urls.add(href)

            # Try to grab summary info from the card
            card: Tag = link_tag
            # Walk up to the wrapping card element if available
            parent_card = link_tag.find_parent(["article", "div"])
            if parent_card:
                card = parent_card

            price_text = self._text_of(card, ".card-property__price, .price, [class*=price]")
            surface_text = self._text_of(card, ".card-property__surface, [class*=surface]")
            rooms_text = self._text_of(card, ".card-property__rooms, [class*=rooms], [class*=pieces]")

            # Extract thumbnail image
            img_tag = card.select_one("img[src], img[data-src]")
            thumb_url = ""
            if img_tag:
                thumb_url = img_tag.get("data-src") or img_tag.get("src") or ""

            # Derive a source_id from the URL path
            source_id = href.rstrip("/").split("/")[-1] or href

            raw = RawListing(
                source=self.source_name,
                source_id=source_id,
                source_url=detail_url,
                city=city,
                price=_extract_number(price_text) or 0,
                surface=_extract_number(surface_text) or 0,
                rooms=_extract_number(rooms_text),
                images_urls=[thumb_url] if thumb_url else [],
            )
            results.append(raw)

        return results

    # ------------------------------------------------------------------
    # Detail page
    # ------------------------------------------------------------------

    async def get_detail(self, url: str) -> RawListing | None:
        soup = await self._soup(url)

        # -- Price --
        price_el = soup.select_one(
            ".detail-price, .property-price, [class*=price] .value, "
            "[class*='prix'], h2[class*='price']"
        )
        price = _extract_number(price_el.get_text() if price_el else None) or 0

        # -- Surface / Rooms --
        surface: int | float = 0
        rooms: int | None = None
        for feat in soup.select(
            ".detail-features li, .property-features li, "
            "[class*='feature'] li, [class*='detail'] li, .criteria span"
        ):
            text = feat.get_text(" ", strip=True).lower()
            if "m²" in text or "m2" in text:
                surface = _extract_number(text) or 0
            if "pièce" in text or "piece" in text:
                rooms = _extract_number(text)

        # -- Address --
        address_el = soup.select_one(
            ".detail-address, .property-address, [class*='address'], "
            "[class*='localisation'], [itemprop='address']"
        )
        address = address_el.get_text(strip=True) if address_el else None

        # -- City --
        city = ""
        if address:
            city = address.split(",")[-1].strip() if "," in address else address

        # -- Images --
        images = self._extract_images(soup)

        # -- Lat / Lng from embedded scripts or data attributes --
        lat, lng = self._extract_coords(soup)

        # -- Source ID --
        source_id = url.rstrip("/").split("/")[-1]

        return RawListing(
            source=self.source_name,
            source_id=source_id,
            source_url=url,
            city=city,
            address=address,
            lat=lat,
            lng=lng,
            surface=surface,
            rooms=rooms,
            price=price,
            images_urls=images,
        )

    # ------------------------------------------------------------------
    # Image extraction
    # ------------------------------------------------------------------

    def _extract_images(self, soup: BeautifulSoup) -> list[str]:
        """Extract full-size image URLs from the detail gallery.

        Laforet hosts images on the CDN:
        ``https://laforetbusiness.laforet-intranet.com/...``
        They appear in gallery/carousel <img> tags or inside JSON-LD data.
        """
        urls: list[str] = []
        seen: set[str] = set()

        # Strategy 1: gallery / carousel images
        for img in soup.select(
            ".carousel img, .gallery img, .swiper img, "
            "[class*='slider'] img, [class*='gallery'] img, "
            "[class*='carousel'] img, .detail-photos img"
        ):
            src = img.get("data-src") or img.get("data-lazy") or img.get("src") or ""
            if src and src not in seen and "laforet" in src:
                seen.add(src)
                urls.append(src)

        # Strategy 2: any <img> tag whose src points to the known CDN
        if not urls:
            for img in soup.find_all("img"):
                src = img.get("data-src") or img.get("src") or ""
                if "laforetbusiness.laforet-intranet.com" in src and src not in seen:
                    seen.add(src)
                    urls.append(src)

        # Strategy 3: JSON-LD or inline JSON blocks
        if not urls:
            for script_tag in soup.find_all("script", {"type": "application/ld+json"}):
                try:
                    data = json.loads(script_tag.string or "")
                    for img_item in data if isinstance(data, list) else [data]:
                        for key in ("image", "photo", "photos", "images"):
                            val = img_item.get(key, None) if isinstance(img_item, dict) else None
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

        # Strategy 4: look through all <script> for CDN URLs
        if not urls:
            cdn_pattern = re.compile(
                r"https?://laforetbusiness\.laforet-intranet\.com/[^\s\"'<>]+"
            )
            for script_tag in soup.find_all("script"):
                if script_tag.string:
                    for match in cdn_pattern.findall(script_tag.string):
                        if match not in seen:
                            seen.add(match)
                            urls.append(match)

        return urls

    # ------------------------------------------------------------------
    # Coordinates extraction
    # ------------------------------------------------------------------

    def _extract_coords(self, soup: BeautifulSoup) -> tuple[float | None, float | None]:
        """Try to extract lat/lng from the page."""
        # Check data attributes on map containers
        for el in soup.select("[data-lat][data-lng], [data-latitude][data-longitude]"):
            try:
                lat = float(el.get("data-lat") or el.get("data-latitude") or "")
                lng = float(el.get("data-lng") or el.get("data-longitude") or "")
                return lat, lng
            except (ValueError, TypeError):
                continue

        # Check inline scripts for coordinate patterns
        coord_patterns = [
            re.compile(r'"lat(?:itude)?":\s*([\d.]+)\s*,\s*"lng|lon(?:gitude)?":\s*([\d.]+)'),
            re.compile(r"lat(?:itude)?\s*[:=]\s*([\d.]+).*?lng|lon(?:gitude)?\s*[:=]\s*([\d.]+)"),
        ]
        for script_tag in soup.find_all("script"):
            text = script_tag.string or ""
            for pattern in coord_patterns:
                m = pattern.search(text)
                if m:
                    try:
                        return float(m.group(1)), float(m.group(2))
                    except (ValueError, IndexError):
                        continue

        return None, None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _text_of(tag: Tag, selector: str) -> str | None:
        """Return stripped text of the first element matching *selector* inside *tag*."""
        el = tag.select_one(selector)
        return el.get_text(strip=True) if el else None
