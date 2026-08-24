from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeoData:
    country_code: str | None
    country: str | None
    region: str | None
    city: str | None
    latitude: float | None
    longitude: float | None


class GeoProvider(Protocol):
    name: str

    async def lookup(self, ip: str) -> GeoData | None: ...
