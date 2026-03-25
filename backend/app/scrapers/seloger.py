"""SeLoger scraper — requires Playwright + stealth for JS-rendered pages."""

from app.scrapers.base import AbstractScraper, RawListing
from app.scrapers.browser_scraper import BrowserScraperMixin


class SeLogerScraper(BrowserScraperMixin, AbstractScraper):
    source_name = "seloger"

    async def search(self, city: str, max_pages: int = 5) -> list[RawListing]:
        raise NotImplementedError(
            "SeLoger requires Playwright browser automation with stealth plugin"
        )

    async def get_detail(self, url: str) -> RawListing | None:
        raise NotImplementedError(
            "SeLoger requires Playwright browser automation with stealth plugin"
        )
