"""Scraper for pap.fr apartment sale listings.

Strategy: PAP requires city-specific "g-codes" in the URL for correct
filtering. We discover these codes dynamically via PAP's autocomplete
endpoint (/json/ac-geo?q=...). Search result pages are server-rendered
HTML with `.search-list-item-alt` cards. We then fetch each detail page
to get the full photo gallery and, when available, GPS coordinates.
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scrapers.base import AbstractScraper, RawListing
from app.scrapers.http_scraper import HttpScraperMixin

logger = logging.getLogger(__name__)

BASE_URL = "https://www.pap.fr"

# ── City g-codes (pre-populated, refreshed dynamically) ──────────────
# The g-code is required in the search URL for PAP to filter by city.
# Format: city_key → (g_code, department_number)
CITY_CODES: dict[str, tuple[int, str]] = {
    "paris":       (439,   "75"),
    "marseille":   (12024, "13"),
    "lyon":        (43590, "69"),
    "toulouse":    (43612, "31"),
    "nice":        (8979,  "06"),
    "nantes":      (43619, "44"),
    "montpellier": (43621, "34"),
    "strasbourg":  (43623, "67"),
    "bordeaux":    (43588, "33"),
    "lille":       (43627, "59"),
}


def _extract_number(text: str | None) -> int | None:
    """Extract the first integer from a text like '310.000 €' or '61 m²'."""
    if not text:
        return None
    # Remove dots used as thousand separators, thin spaces, and non-breaking spaces
    cleaned = text.replace(".", "").replace("\xa0", " ").replace("\u202f", " ")
    m = re.search(r"[\d\s]+", cleaned)
    if m:
        digits = m.group().replace(" ", "").strip()
        return int(digits) if digits else None
    return None


class PapScraper(HttpScraperMixin, AbstractScraper):
    """Scraper for pap.fr — apartment purchases (particulier à particulier)."""

    source_name = "pap"

    # ------------------------------------------------------------------
    # G-code resolution
    # ------------------------------------------------------------------

    async def _resolve_gcode(self, city: str) -> tuple[int, str] | None:
        """Resolve a city name to a (g_code, dept) tuple via autocomplete."""
        city_lower = city.lower().strip()

        # Check pre-populated codes first
        if city_lower in CITY_CODES:
            return CITY_CODES[city_lower]

        # Dynamic lookup via PAP autocomplete
        try:
            resp = await self._get(f"{BASE_URL}/json/ac-geo?q={city}")
            data = resp.json()
            if data and isinstance(data, list):
                entry = data[0]
                gcode = entry.get("id")
                name = entry.get("name", "")
                # Extract dept from name like "Paris (75)"
                dept_match = re.search(r"\((\d+)\)", name)
                dept = dept_match.group(1) if dept_match else ""
                if gcode:
                    logger.info("  Resolved PAP g-code for %s: g%s (%s)", city, gcode, dept)
                    return (int(gcode), dept)
        except Exception as exc:
            logger.warning("  Failed to resolve g-code for %s: %s", city, exc)

        return None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(self, city: str, max_pages: int = 5) -> list[RawListing]:
        code = await self._resolve_gcode(city)
        if not code:
            logger.warning("  No PAP g-code for city '%s', skipping", city)
            return []

        gcode, dept = code
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for page in range(1, max_pages + 1):
            url = f"{BASE_URL}/annonce/vente-appartements-{city.lower()}-{dept}-g{gcode}"
            if page > 1:
                url += f"-{page}"

            logger.info("  Fetching PAP page %d: %s", page, url)

            try:
                soup = await self._soup(url)
            except Exception as exc:
                logger.warning("  Failed to fetch page %d: %s", page, exc)
                break

            cards = self._parse_search_cards(soup, city)

            if not cards:
                logger.info("  No more results at page %d", page)
                break

            for card in cards:
                if card.source_id not in seen_ids:
                    seen_ids.add(card.source_id)
                    listings.append(card)

            logger.info("  Page %d: %d new listings", page, len(cards))

        # Fetch detail pages for full images + coordinates
        enriched: list[RawListing] = []
        for listing in listings:
            detail = await self.get_detail(listing.source_url)
            if detail:
                # Merge search-level data with detail data
                if not detail.city or detail.city == "":
                    detail.city = listing.city
                enriched.append(detail)
            else:
                enriched.append(listing)

        logger.info("  City '%s': %d unique listings", city, len(enriched))
        return enriched

    # ------------------------------------------------------------------
    # Search-page card parsing
    # ------------------------------------------------------------------

    def _parse_search_cards(self, soup: BeautifulSoup, city: str) -> list[RawListing]:
        results: list[RawListing] = []

        for card in soup.select(".search-list-item-alt"):
            # Skip ad/promo cards (no price element)
            price_el = card.select_one(".item-price")
            if not price_el:
                continue

            # Detail link
            link_tag = card.select_one("a[href*='/annonces/']")
            if not link_tag:
                continue
            href = link_tag.get("href", "")
            detail_url = urljoin(BASE_URL, href)

            # Source ID from URL
            source_id = href.rstrip("/").split("/")[-1]
            # Clean source_id: extract the r-code if present
            r_match = re.search(r"(r\d+)", source_id)
            if r_match:
                source_id = r_match.group(1)

            # Price
            price_text = price_el.get_text(strip=True)
            # Handle "à partir de X €" pattern
            price = _extract_number(price_text) or 0

            # Surface and rooms from tags
            surface: int = 0
            rooms: int | None = None
            for tag in card.select(".item-tags li"):
                text = tag.get_text(strip=True).lower()
                if ("m²" in text or "m2" in text) and "€" not in text:
                    surface = _extract_number(text) or 0
                elif "pièce" in text or "piece" in text:
                    rooms = _extract_number(text)

            # City from title
            title_el = card.select_one(".item-title")
            listing_city = city
            if title_el:
                title_text = title_el.get_text(strip=True)
                # Try to extract city like "Paris 15E (75015)" from title
                city_match = re.search(
                    r"(?:Seulement sur PAP|Moins cher sur PAP)?([\w\s\-']+(?:\d+E)?)\s*\((\d+)\)",
                    title_text,
                )
                if city_match:
                    listing_city = f"{city_match.group(1).strip()} ({city_match.group(2)})"

            # Thumbnail
            img_tag = card.select_one("img[src*='cdn.pap.fr']")
            thumb = ""
            if img_tag:
                thumb = img_tag.get("src", "")

            results.append(
                RawListing(
                    source=self.source_name,
                    source_id=source_id,
                    source_url=detail_url,
                    city=listing_city,
                    price=price,
                    surface=surface,
                    rooms=rooms,
                    images_urls=[thumb] if thumb else [],
                )
            )

        return results

    # ------------------------------------------------------------------
    # Detail page
    # ------------------------------------------------------------------

    async def get_detail(self, url: str) -> RawListing | None:
        try:
            soup = await self._soup(url)
        except Exception as exc:
            logger.warning("  Failed to fetch detail %s: %s", url, exc)
            return None

        # -- Price --
        price_el = soup.select_one(".item-price, [itemprop='price']")
        price = _extract_number(price_el.get_text() if price_el else None) or 0

        # -- Surface / Rooms --
        surface: int = 0
        rooms: int | None = None
        for tag in soup.select(".item-tags li, .item-summary li"):
            text = tag.get_text(strip=True).lower()
            if ("m²" in text or "m2" in text) and "€" not in text:
                surface = _extract_number(text) or 0
            elif "pièce" in text or "piece" in text:
                rooms = _extract_number(text)

        # -- City from title --
        city = ""
        title_el = soup.select_one("h1, .item-title-content")
        if title_el:
            title_text = title_el.get_text(strip=True)
            city_match = re.search(
                r"([\w\s\-']+(?:\d+E)?)\s*\((\d+)\)",
                title_text,
            )
            if city_match:
                city = f"{city_match.group(1).strip()} ({city_match.group(2)})"

        # -- Images --
        images = self._extract_images(soup)

        # -- Coordinates --
        lat, lng = self._extract_coords(soup)

        source_id = url.rstrip("/").split("/")[-1]
        r_match = re.search(r"(r\d+)", source_id)
        if r_match:
            source_id = r_match.group(1)

        return RawListing(
            source=self.source_name,
            source_id=source_id,
            source_url=url,
            city=city,
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
        urls: list[str] = []
        seen: set[str] = set()

        # Gallery / carousel images (owl-carousel is used by PAP)
        for img in soup.select(
            ".owl-carousel img, .gallery img, .carousel img, "
            "[class*='slider'] img, [class*='gallery'] img"
        ):
            src = (
                img.get("data-original")
                or img.get("data-src")
                or img.get("data-lazy")
                or img.get("src")
                or ""
            )
            if src and src not in seen and not src.endswith(".svg"):
                seen.add(src)
                full_url = src if src.startswith("http") else urljoin(BASE_URL, src)
                # Use full-size images instead of thumbnails
                full_url = re.sub(r"-p\d+\.(jpg|webp|png)", r"-p1.\1", full_url)
                urls.append(full_url)

        # Fallback: any cdn.pap.fr images
        if not urls:
            for img in soup.find_all("img"):
                src = img.get("src") or ""
                if "cdn.pap.fr" in src and src not in seen:
                    seen.add(src)
                    full_url = re.sub(r"-p\d+\.(jpg|webp|png)", r"-p1.\1", src)
                    urls.append(full_url)

        return urls

    # ------------------------------------------------------------------
    # Coordinates extraction
    # ------------------------------------------------------------------

    def _extract_coords(self, soup: BeautifulSoup) -> tuple[float | None, float | None]:
        """Try to extract lat/lng from data attributes or inline scripts."""
        # Data attributes
        for el in soup.select("[data-lat][data-lng], [data-latitude][data-longitude]"):
            try:
                lat = float(el.get("data-lat") or el.get("data-latitude") or "")
                lng = float(el.get("data-lng") or el.get("data-longitude") or "")
                if 41.0 < lat < 52.0 and -6.0 < lng < 10.0:
                    return lat, lng
            except (ValueError, TypeError):
                continue

        # Inline script patterns (PAP uses various JS map init patterns)
        patterns = [
            re.compile(
                r"(?:lat|latitude)[\"']?\s*[:=]\s*([0-9]+\.[0-9]+).*?"
                r"(?:lng|lon|longitude)[\"']?\s*[:=]\s*(-?[0-9]+\.[0-9]+)",
                re.DOTALL,
            ),
            re.compile(
                r"LatLng\(([0-9]+\.[0-9]+)\s*,\s*(-?[0-9]+\.[0-9]+)\)",
            ),
            re.compile(
                r"center:\s*\[(-?[0-9]+\.[0-9]+)\s*,\s*(-?[0-9]+\.[0-9]+)\]",
            ),
        ]

        for script in soup.find_all("script"):
            text = script.string or ""
            for pattern in patterns:
                m = pattern.search(text)
                if m:
                    try:
                        lat, lng = float(m.group(1)), float(m.group(2))
                        if 41.0 < lat < 52.0 and -6.0 < lng < 10.0:
                            return lat, lng
                    except ValueError:
                        continue

        return None, None
