from typing import Annotated

from fastapi import Depends, Request

from app.services.geo.chain import GeoEnrichmentChain


def get_geo_chain(request: Request) -> GeoEnrichmentChain:
    return request.app.state.geo_chain


GeoChainDep = Annotated[GeoEnrichmentChain, Depends(get_geo_chain)]


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "0.0.0.0"


ClientIpDep = Annotated[str, Depends(get_client_ip)]
