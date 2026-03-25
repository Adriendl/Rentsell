"""HTTP scraper mixin with polite crawling, retries, and robots.txt support."""

from __future__ import annotations

import asyncio
import random
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def _is_retryable(exc: BaseException) -> bool:
    """Return True for HTTP 429 / 503 responses."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 503)
    return False


class HttpScraperMixin:
    """Mixin providing polite async HTTP fetching with retry logic."""

    _client: httpx.AsyncClient | None = None
    _robots_cache: dict[str, RobotFileParser] = {}

    # ------------------------------------------------------------------
    # Client helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.AsyncClient:
        """Lazily initialise an ``httpx.AsyncClient`` with a random UA."""
        if self._client is None or self._client.is_closed:
            ua = random.choice(USER_AGENTS)
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": ua,
                    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
                },
                follow_redirects=True,
                timeout=30.0,
            )
        return self._client

    def _rotate_ua(self) -> None:
        """Swap the User-Agent header on the current client."""
        client = self._get_client()
        client.headers["User-Agent"] = random.choice(USER_AGENTS)

    # ------------------------------------------------------------------
    # Core GET with polite delay + retries
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=5, min=5, max=30),
        reraise=True,
    )
    async def _get(self, url: str) -> httpx.Response:
        """GET *url* with a random politeness delay and automatic retries."""
        settings = get_settings()
        delay = random.uniform(settings.min_delay, settings.max_delay)
        await asyncio.sleep(delay)

        client = self._get_client()
        response = client.get(url)
        if asyncio.iscoroutine(response):
            response = await response
        response.raise_for_status()
        return response

    # ------------------------------------------------------------------
    # robots.txt
    # ------------------------------------------------------------------

    async def _check_robots(self, base_url: str, path: str) -> bool:
        """Return ``True`` if *path* is allowed by *base_url*/robots.txt."""
        if base_url in self._robots_cache:
            rp = self._robots_cache[base_url]
        else:
            rp = RobotFileParser()
            robots_url = f"{base_url.rstrip('/')}/robots.txt"
            try:
                resp = await self._get(robots_url)
                rp.parse(resp.text.splitlines())
            except Exception:
                # If we can't fetch robots.txt, assume allowed
                rp.parse([])
            self._robots_cache[base_url] = rp
        return rp.can_fetch("*", f"{base_url.rstrip('/')}{path}")

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    async def _soup(self, url: str) -> BeautifulSoup:
        """Fetch *url* and return a ``BeautifulSoup`` tree."""
        resp = await self._get(url)
        return BeautifulSoup(resp.text, "html.parser")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
