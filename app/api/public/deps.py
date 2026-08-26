from typing import Annotated

from fastapi import Depends, Request

from app.api.deps import ClientIpDep, get_client_ip
from app.services.geo.chain import GeoEnrichmentChain

__all__ = ["ClientIpDep", "GeoChainDep", "get_client_ip", "get_geo_chain"]


def get_geo_chain(request: Request) -> GeoEnrichmentChain:
    return request.app.state.geo_chain


GeoChainDep = Annotated[GeoEnrichmentChain, Depends(get_geo_chain)]
