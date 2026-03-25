"""Playwright-based browser scraper mixin — skeleton for future use."""


class BrowserScraperMixin:
    """Base mixin for scrapers requiring full browser rendering.

    Requires: playwright install chromium
    """

    async def _launch_browser(self):
        raise NotImplementedError

    async def _new_page(self):
        raise NotImplementedError

    async def _close(self):
        raise NotImplementedError
