import asyncio

from app.services.geo.base import GeoData


class MockGeoProvider:
    name = "mock-geo"

    def __init__(
        self,
        data: GeoData | None = GeoData("DE", "Germany", "Berlin", "Berlin", 52.52, 13.405),
        delay_seconds: float = 0.01,
        error: Exception | None = None,
    ):
        self._data = data
        self._delay = delay_seconds
        self._error = error
        self.calls = 0

    async def lookup(self, ip: str) -> GeoData | None:
        self.calls += 1
        await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return self._data
