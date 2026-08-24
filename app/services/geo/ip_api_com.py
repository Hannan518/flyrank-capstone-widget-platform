import httpx

from app.services.geo.base import GeoData

_FIELDS = "status,message,country,countryCode,regionName,city,lat,lon"


class IpApiComProvider:
    name = "ip-api.com"

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def lookup(self, ip: str) -> GeoData | None:
        response = await self._client.get(
            f"http://ip-api.com/json/{ip}?fields={_FIELDS}"
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "success":
            return None
        return GeoData(
            country_code=data.get("countryCode"),
            country=data.get("country"),
            region=data.get("regionName"),
            city=data.get("city"),
            latitude=data.get("lat"),
            longitude=data.get("lon"),
        )
