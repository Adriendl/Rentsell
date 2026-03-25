"""Scraper for pap.fr apartment sale listings."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.scrapers.base import AbstractScraper, RawListing
from app.scrapers.http_scraper import HttpScraperMixin

BASE_URL = "https://www.pap.fr"


def _slugify_city(city: str) -> str:
    slug = unicodedata.normalize("NFD", city)
    slug = slug.encode("ascii", "ignore").decode("ascii")
    slug = slug.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    return slug


def _extract_number(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"[\d\s]+", text.replace("\xa0", " "))
    if m:
        return int(m.group().replace(" ", "").strip() or "0")
    return None


class PapScraper(HttpScraperMixin, AbstractScraper):
    """Scraper for pap.fr — apartment purchases (particulier a particulier)."""

    source_name = "pap"

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(self, city: str, max_pages: int = 5) -> list[RawListing]:
        listings: list[RawListing] = []
        city_slug = _slugify_city(city)

        for page in range(1, max_pages + 1):
            url = f"{BASE_URL}/annonces/vente-appartement-{city_slug}"
            if page > 1:
                url += f"-{page}"

            soup = await self._soup(url)
            cards = self._parse_search_cards(soup, city)

            if not cards:
                break

            listings.extend(cards)

        return listings

    # ------------------------------------------------------------------
    # Search-page card parsing
    # ------------------------------------------------------------------

    def _parse_search_cards(self, soup: BeautifulSoup, city: str) -> list[RawListing]:
        results: list[RawListing] = []

        # PAP renders listing items typically as <div class="search-list-item"> or similar
        card_containers = soup.select(
            ".search-list-item, .search-results-item, "
            "[class*='annonce'], [class*='listing-item']"
        )

        for card in card_containers:
            # Detail link
            link_tag = card.select_one("a[href*='/annonces/']")
            if not link_tag:
                continue
            href = link_tag.get("href", "")
            detail_url = urljoin(BASE_URL, href)

            # Price
            price_el = card.select_one(
                ".item-price, [class*='price'], [class*='prix'], .price"
            )
            price = _extract_number(price_el.get_text() if price_el else None) or 0

            # Surface
            surface: int = 0
            rooms: int | None = None
            for tag in card.select(
                ".item-tags li, .item-criteria span, [class*='tag'], "
                "[class*='criteria'] span, [class*='feature']"
            ):
                text = tag.get_text(" ", strip=True).lower()
                if "m²" in text or "m2" in text:
                    surface = _extract_number(text) or 0
                if "pièce" in text or "piece" in text or "p." in text:
                    rooms = _extract_number(text)

            # Thumbnail image
            img_tag = card.select_one("img[src], img[data-src], img[data-original]")
            thumb = ""
            if img_tag:
                thumb = (
                    img_tag.get("data-original")
                    or img_tag.get("data-src")
                    or img_tag.get("src")
                    or ""
                )

            source_id = href.rstrip("/").split("/")[-1] or href

            results.append(
                RawListing(
                    source=self.source_name,
                    source_id=source_id,
                    source_url=detail_url,
                    city=city,
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
        soup = await self._soup(url)

        # -- Price --
        price_el = soup.select_one(
            ".item-price, [class*='price'], [class*='prix'], "
            ".price, [itemprop='price']"
        )
        price = _extract_number(price_el.get_text() if price_el else None) or 0

        # -- Surface / Rooms --
        surface: int | float = 0
        rooms: int | None = None
        for feat in soup.select(
            ".item-tags li, .item-description li, "
            "[class*='criteria'] li, [class*='feature'] li, "
            ".item-summary li"
        ):
            text = feat.get_text(" ", strip=True).lower()
            if "m²" in text or "m2" in text:
                surface = _extract_number(text) or 0
            if "pièce" in text or "piece" in text:
                rooms = _extract_number(text)

        # -- Address / City --
        address_el = soup.select_one(
            ".item-geo, [class*='address'], [class*='geo'], "
            "[class*='localisation'], [itemprop='address']"
        )
        address = address_el.get_text(strip=True) if address_el else None
        city = ""
        if address:
            city = address.split(",")[-1].strip() if "," in address else address

        # -- Images --
        images = self._extract_images(soup)

        # -- Lat / Lng --
        lat, lng = self._extract_coords(soup)

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
        urls: list[str] = []
        seen: set[str] = set()

        # Gallery / carousel images
        for img in soup.select(
            ".owl-carousel img, .gallery img, .carousel img, "
            "[class*='slider'] img, [class*='gallery'] img, "
            "[class*='photo'] img"
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
                urls.append(src if src.startswith("http") else urljoin(BASE_URL, src))

        # Fallback: any large-ish img on the page
        if not urls:
            for img in soup.find_all("img"):
                src = img.get("src") or ""
                if src and src not in seen and "photo" in src.lower():
                    seen.add(src)
                    urls.append(src if src.startswith("http") else urljoin(BASE_URL, src))

        return urls

    # ------------------------------------------------------------------
    # Coordinates extraction
    # ------------------------------------------------------------------

    def _extract_coords(self, soup: BeautifulSoup) -> tuple[float | None, float | None]:
        for el in soup.select("[data-lat][data-lng], [data-latitude][data-longitude]"):
            try:
                lat = float(el.get("data-lat") or el.get("data-latitude") or "")
                lng = float(el.get("data-lng") or el.get("data-longitude") or "")
                return lat, lng
            except (ValueError, TypeError):
                continue

        # Inline script patterns
        pattern = re.compile(
            r"(?:lat|latitude)[\"']?\s*[:=]\s*([0-9]+\.[0-9]+).*?"
            r"(?:lng|lon|longitude)[\"']?\s*[:=]\s*([0-9]+\.[0-9]+)",
            re.DOTALL,
        )
        for script in soup.find_all("script"):
            text = script.string or ""
            m = pattern.search(text)
            if m:
                try:
                    return float(m.group(1)), float(m.group(2))
                except ValueError:
                    continue

        return None, None
