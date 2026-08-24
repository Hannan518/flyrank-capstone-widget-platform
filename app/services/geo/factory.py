from datetime import timedelta

import httpx

from app.core.config import Settings
from app.services.geo.base import GeoProvider
from app.services.geo.chain import GeoEnrichmentChain
from app.services.geo.ip_api_com import IpApiComProvider
from app.services.geo.ipapi_co import IpapiCoProvider
from app.services.geo.mock import MockGeoProvider


def build_geo_chain(settings: Settings) -> GeoEnrichmentChain:
    providers: list[GeoProvider]
    if settings.geo_provider_mode == "mock":
        providers = [MockGeoProvider()]
    else:
        client = httpx.AsyncClient(timeout=settings.geo_total_budget_ms / 1000)
        providers = [IpApiComProvider(client), IpapiCoProvider(client)]
    return GeoEnrichmentChain(
        providers,
        total_budget=timedelta(milliseconds=settings.geo_total_budget_ms),
    )
