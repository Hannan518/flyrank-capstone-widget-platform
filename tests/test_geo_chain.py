from datetime import timedelta

from app.services.geo.base import GeoData
from app.services.geo.chain import GeoEnrichmentChain
from app.services.geo.mock import MockGeoProvider


def test_falls_back_to_second_provider_on_failure():
    dead = MockGeoProvider(error=RuntimeError("provider down"))
    alive = MockGeoProvider()
    chain = GeoEnrichmentChain([dead, alive], total_budget=timedelta(seconds=2))

    import asyncio

    data = asyncio.run(chain.enrich("1.2.3.4"))

    assert dead.calls == 1
    assert alive.calls == 1
    assert data is not None
    assert data.country_code == "DE"


def test_returns_none_when_all_providers_fail():
    dead_a = MockGeoProvider(error=RuntimeError("a down"))
    dead_b = MockGeoProvider(data=None)
    chain = GeoEnrichmentChain([dead_a, dead_b], total_budget=timedelta(seconds=2))

    import asyncio

    data = asyncio.run(chain.enrich("1.2.3.4"))

    assert data is None


def test_budget_exhaustion_skips_later_providers():
    slow = MockGeoProvider(delay_seconds=0.5)
    never_reached = MockGeoProvider()
    chain = GeoEnrichmentChain(
        [slow, never_reached], total_budget=timedelta(milliseconds=50)
    )

    import asyncio

    data = asyncio.run(chain.enrich("1.2.3.4"))

    assert slow.calls == 1
    assert never_reached.calls == 0
    assert data is None


def test_first_success_short_circuits():
    first = MockGeoProvider()
    second = MockGeoProvider()
    chain = GeoEnrichmentChain([first, second], total_budget=timedelta(seconds=2))

    import asyncio

    data = asyncio.run(chain.enrich("1.2.3.4"))

    assert first.calls == 1
    assert second.calls == 0
    assert isinstance(data, GeoData)
