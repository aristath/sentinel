"""Tests for Broker metadata helpers.

Covers `Broker.get_security_metadata`, which fetches `attributes.CntryOfRisk`
and `sector_code` from Tradernet's `getAllSecurities` endpoint and returns
them in a normalized shape for the sync job to persist.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.broker import Broker

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tradernet_get_all_securities"


def load_fixture(name: str) -> dict:
    """Load a captured `getAllSecurities` response by slug."""
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def clear_broker_singleton():
    """Reset the Broker singleton between tests so mocks don't leak."""
    if hasattr(Broker, "_clear"):
        Broker._clear()  # type: ignore[attr-defined]
    yield
    if hasattr(Broker, "_clear"):
        Broker._clear()  # type: ignore[attr-defined]


@pytest.fixture
def broker():
    """Broker instance with a stubbed Tradernet SDK API."""
    instance = Broker()
    instance._api = MagicMock()
    return instance


class TestGetSecurityMetadata:
    """Verify Broker.get_security_metadata against captured Tradernet responses."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_connected(self):
        instance = Broker()
        instance._api = None
        assert await instance.get_security_metadata("AAPL.US") is None

    @pytest.mark.asyncio
    async def test_us_stock_maps_country_industry_kind_market_name(self, broker):
        broker._api.authorized_request.return_value = load_fixture("us_stock")

        result = await broker.get_security_metadata("AAPL.US")

        assert result == {
            "geography": "US",
            "industry": "Computers, Phones & Household Electronics",
            "instr_kind_c": 1,
            "mkt_short_code": "FIX",
            "name": "Apple Inc.",
        }

    @pytest.mark.asyncio
    async def test_uses_cntry_of_risk_not_listing_venue(self, broker):
        """CAT.3750.AS is a Chinese company on HKEX via Amsterdam — we want CN, not HK/NL."""
        broker._api.authorized_request.return_value = load_fixture("adr_china")

        result = await broker.get_security_metadata("CAT.3750.AS")

        assert result["geography"] == "CN"
        assert result["mkt_short_code"] == "HKEX"

    @pytest.mark.asyncio
    async def test_etf_returns_raw_values_with_kind_7(self, broker):
        """ETFs surface as instr_kind_c=7 so the sync job can blank geo/industry."""
        broker._api.authorized_request.return_value = load_fixture("etf_ie")

        result = await broker.get_security_metadata("VWCE.EU")

        assert result["instr_kind_c"] == 7
        assert result["geography"] == "IE"
        assert result["industry"] == "Equity ETFs"

    @pytest.mark.asyncio
    async def test_missing_cntry_of_risk_becomes_empty_string(self, broker):
        """KASE-listed names sometimes carry null CntryOfRisk and sector_code."""
        broker._api.authorized_request.return_value = load_fixture("kase_no_risk")

        result = await broker.get_security_metadata("KZAP.KZ")

        assert result["geography"] == ""
        assert result["industry"] == ""

    @pytest.mark.asyncio
    async def test_missing_ticker_returns_none(self, broker):
        broker._api.authorized_request.return_value = load_fixture("missing")

        assert await broker.get_security_metadata("DOESNOTEXIST.US") is None

    @pytest.mark.asyncio
    async def test_attributes_as_json_string_is_parsed(self, broker):
        """Direct HTTP (vs SDK) returns `attributes` as a JSON-encoded string."""
        fixture = load_fixture("us_stock")
        fixture["securities"][0]["attributes"] = json.dumps(fixture["securities"][0]["attributes"])
        broker._api.authorized_request.return_value = fixture

        result = await broker.get_security_metadata("AAPL.US")

        assert result["geography"] == "US"

    @pytest.mark.asyncio
    async def test_api_exception_returns_none(self, broker, caplog):
        broker._api.authorized_request.side_effect = RuntimeError("network down")

        result = await broker.get_security_metadata("AAPL.US")

        assert result is None
        assert any("AAPL.US" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_sends_ticker_filter_to_getAllSecurities(self, broker):
        """Verify we call the right command and pass the ticker filter correctly."""
        broker._api.authorized_request.return_value = load_fixture("us_stock")

        await broker.get_security_metadata("AAPL.US")

        broker._api.authorized_request.assert_called_once()
        cmd, payload = broker._api.authorized_request.call_args.args
        assert cmd == "getAllSecurities"
        filters = payload["filter"]["filters"]
        assert filters == [{"field": "ticker", "operator": "eq", "value": "AAPL.US"}]

    @pytest.mark.asyncio
    async def test_attributes_as_unexpected_type_does_not_crash(self, broker):
        """If Tradernet ever changes shape, e.g. returns `attributes` as a list, don't crash —
        return blank fields and let the sync job continue."""
        fixture = load_fixture("us_stock")
        fixture["securities"][0]["attributes"] = ["unexpected", "list"]
        broker._api.authorized_request.return_value = fixture

        result = await broker.get_security_metadata("AAPL.US")

        assert result["geography"] == ""

    @pytest.mark.asyncio
    async def test_response_without_securities_key_returns_none(self, broker):
        """Bad payloads (e.g. error responses missing the expected key) shouldn't crash."""
        broker._api.authorized_request.return_value = {"error": "rate-limited", "code": 429}

        assert await broker.get_security_metadata("AAPL.US") is None

    @pytest.mark.asyncio
    async def test_securities_key_present_but_null(self, broker):
        broker._api.authorized_request.return_value = {"securities": None, "total": 0}

        assert await broker.get_security_metadata("AAPL.US") is None

    @pytest.mark.asyncio
    async def test_non_string_country_code_is_coerced_to_string_or_blank(self, broker):
        """Defensive: if CntryOfRisk ever comes back as a number, store the string form
        (not crash, not write a number into a TEXT column)."""
        fixture = load_fixture("us_stock")
        fixture["securities"][0]["attributes"]["CntryOfRisk"] = 0  # Tradernet's "unknown" sentinel
        broker._api.authorized_request.return_value = fixture

        result = await broker.get_security_metadata("AAPL.US")

        # `0` is falsy → ends up blank, which is the right behavior (matches
        # the `issuer_country_code: "0"` semantic of "unclassified").
        assert result["geography"] == ""

    @pytest.mark.asyncio
    async def test_429_triggers_backoff_and_retry(self, broker):
        """Tradernet's getAllSecurities rate-limits at ~30 calls/min and once tripped
        stays angry for ~60s. On 429, back off and retry once before giving up."""
        from requests.exceptions import HTTPError

        # First call raises 429; second succeeds.
        broker._api.authorized_request.side_effect = [
            HTTPError("429 Client Error: Too Many Requests for url: ..."),
            load_fixture("us_stock"),
        ]

        with patch("sentinel.broker.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await broker.get_security_metadata("AAPL.US")

        assert result is not None
        assert result["geography"] == "US"
        assert broker._api.authorized_request.call_count == 2
        # Back-off should be at least 30s to let the rate-limit window clear.
        mock_sleep.assert_awaited_once()
        assert mock_sleep.await_args.args[0] >= 30

    @pytest.mark.asyncio
    async def test_429_twice_returns_none_without_third_attempt(self, broker):
        """If the back-off doesn't clear the limit, we give up — the next sync cycle
        retries naturally. We do NOT escalate to longer waits."""
        from requests.exceptions import HTTPError

        broker._api.authorized_request.side_effect = [
            HTTPError("429 Client Error"),
            HTTPError("429 Client Error"),
        ]

        with patch("sentinel.broker.asyncio.sleep", new_callable=AsyncMock):
            result = await broker.get_security_metadata("AAPL.US")

        assert result is None
        assert broker._api.authorized_request.call_count == 2

    @pytest.mark.asyncio
    async def test_non_rate_limit_error_returns_immediately_without_retry(self, broker):
        """Non-429 errors should not trigger the backoff path — fail fast."""
        broker._api.authorized_request.side_effect = RuntimeError("DNS failure")

        with patch("sentinel.broker.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await broker.get_security_metadata("AAPL.US")

        assert result is None
        assert broker._api.authorized_request.call_count == 1
        mock_sleep.assert_not_awaited()
