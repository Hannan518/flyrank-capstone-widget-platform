import httpx

from app.services.geo.base import GeoData


class IpapiCoProvider:
    name = "ipapi.co"

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def lookup(self, ip: str) -> GeoData | None:
        response = await self._client.get(f"https://ipapi.co/{ip}/json/")
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            return None
        return GeoData(
            country_code=data.get("country_code"),
            country=data.get("country_name"),
            region=data.get("region"),
            city=data.get("city"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
        )
