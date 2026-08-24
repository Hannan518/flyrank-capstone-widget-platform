import asyncio
import logging
from datetime import timedelta
from typing import Sequence

from app.services.geo.base import GeoData, GeoProvider

logger = logging.getLogger(__name__)


class GeoEnrichmentChain:
    def __init__(
        self,
        providers: Sequence[GeoProvider],
        total_budget: timedelta,
    ):
        self._providers = list(providers)
        self._budget = total_budget

    @property
    def provider_names(self) -> list[str]:
        return [provider.name for provider in self._providers]

    async def enrich(self, ip: str) -> GeoData | None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._budget.total_seconds()
        for provider in self._providers:
            remaining = deadline - loop.time()
            if remaining <= 0:
                logger.warning(
                    "geo budget exhausted before provider %s", provider.name
                )
                break
            try:
                data = await asyncio.wait_for(
                    provider.lookup(ip), timeout=remaining
                )
            except Exception as exc:
                logger.warning("geo provider %s failed: %s", provider.name, exc)
                continue
            if data is not None:
                logger.info("geo enriched via %s", provider.name)
                return data
            logger.warning("geo provider %s returned no data", provider.name)
        logger.warning("geo enrichment unavailable; storing without geo")
        return None

    async def aclose(self) -> None:
        for provider in self._providers:
            close = getattr(provider, "aclose", None)
            if close is not None:
                await close()
