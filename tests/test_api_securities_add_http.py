"""HTTP-level tests for POST /api/securities add/re-enable behavior."""

import os
import tempfile
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sentinel.api.dependencies import CommonDependencies
from sentinel.api.routers.securities import get_common_deps
from sentinel.api.routers.securities import router as securities_router
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.settings import Settings


@pytest_asyncio.fixture
async def deps():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()

    settings = Settings()
    settings._db = db
    await settings.init_defaults()

    broker = AsyncMock()
    broker.get_security_info = AsyncMock(
        return_value={
            "short_name": "Test Corp",
            "currency": "EUR",
            "mrkt": {"mkt_id": 123},
            "lot": "1.00000000",
        }
    )
    broker.get_historical_prices_bulk = AsyncMock(return_value={"TEST.EU": []})
    broker.add_stock_list_ticker = AsyncMock(return_value=True)

    yield CommonDependencies(
        db=db,
        settings=settings,
        broker=broker,
        currency=Currency(),
    )

    await db.close()
    db.remove_from_cache()
    for ext in ["", "-wal", "-shm"]:
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def _build_client(deps: CommonDependencies) -> TestClient:
    app = FastAPI()
    app.include_router(securities_router, prefix="/api")

    async def override_deps():
        return deps

    app.dependency_overrides[get_common_deps] = override_deps
    return TestClient(app)


@pytest.mark.asyncio
async def test_add_security_reenables_inactive_security(deps: CommonDependencies):
    # Seed an inactive security (soft-deleted style flags).
    await deps.db.upsert_security(
        "TEST.EU",
        name="Old Name",
        currency="EUR",
        market_id="",
        min_lot=1,
        active=0,
        allow_buy=0,
        allow_sell=0,
    )

    client = _build_client(deps)
    resp = client.post("/api/securities", json={"symbol": "TEST.EU"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["symbol"] == "TEST.EU"
    assert payload["re_enabled"] is True

    row = await deps.db.get_security("TEST.EU")
    assert row is not None
    assert int(row["active"]) == 1
    assert int(row["allow_buy"]) == 1
    assert int(row["allow_sell"]) == 1
    assert row["name"] == "Test Corp"


@pytest.mark.asyncio
async def test_add_security_ignores_client_supplied_geography_industry(deps: CommonDependencies):
    """Geography and industry are broker-sourced now; client values are dropped silently."""
    deps.broker.get_security_metadata = AsyncMock(
        return_value={
            "geography": "US",
            "industry": "Computers, Phones & Household Electronics",
            "instr_kind_c": 1,
            "mkt_short_code": "FIX",
            "name": "Test Corp",
        }
    )

    client = _build_client(deps)
    resp = client.post(
        "/api/securities",
        json={
            "symbol": "TEST.EU",
            "geography": "Atlantis",  # bogus value that must NOT persist
            "industry": "Sandcastles",
        },
    )
    assert resp.status_code == 200

    row = await deps.db.get_security("TEST.EU")
    assert row["geography"] != "Atlantis"
    assert row["industry"] != "Sandcastles"


@pytest.mark.asyncio
async def test_put_security_drops_geography_industry_from_request(deps: CommonDependencies):
    """PUT no longer accepts geography/industry — silently dropped from the whitelist."""
    await deps.db.upsert_security(
        "TEST.EU",
        name="Test Corp",
        geography="US",
        industry="Software & IT Services",
        active=1,
    )

    client = _build_client(deps)
    resp = client.put(
        "/api/securities/TEST.EU",
        json={
            "geography": "ZZ",
            "industry": "Garbage",
            "allow_buy": 0,  # this one IS still accepted
        },
    )
    assert resp.status_code == 200

    row = await deps.db.get_security("TEST.EU")
    assert row["geography"] == "US"  # unchanged
    assert row["industry"] == "Software & IT Services"  # unchanged
    assert int(row["allow_buy"]) == 0  # accepted field still works


@pytest.mark.asyncio
async def test_add_security_errors_when_already_active(deps: CommonDependencies):
    await deps.db.upsert_security(
        "TEST.EU",
        name="Already Active",
        currency="EUR",
        market_id="",
        min_lot=1,
        active=1,
        allow_buy=1,
        allow_sell=1,
    )
    client = _build_client(deps)
    resp = client.post("/api/securities", json={"symbol": "TEST.EU"})
    assert resp.status_code == 400
    assert "already exists" in (resp.json().get("detail") or "").lower()
