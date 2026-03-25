from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class RawListing:
    source: str
    source_id: str
    source_url: str
    city: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    surface: str | int | float = 0
    rooms: int | None = None
    price: str | int = 0
    images_urls: list[str] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)

class AbstractScraper(ABC):
    source_name: str

    @abstractmethod
    async def search(self, city: str, max_pages: int = 5) -> list[RawListing]: ...

    @abstractmethod
    async def get_detail(self, url: str) -> RawListing | None: ...
