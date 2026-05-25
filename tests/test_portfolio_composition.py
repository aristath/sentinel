"""Tests for portfolio composition + metrics math.

Each function is tested in isolation with hand-picked inputs that have
known correct answers. The orchestration `build_composition` is exercised
end-to-end via an integration-style test against in-memory mocks.
"""

from __future__ import annotations

import math
from unittest.mock import AsyncMock

import pytest

from sentinel.portfolio_composition import (
    DEFAULT_RISK_FREE_RATE,
    TRADING_DAYS_PER_YEAR,
    all_equity_index_symbols,
    annualized_volatility,
    asset_class_for,
    basket_daily_returns,
    basket_symbols,
    beta,
    build_composition,
    build_daily_pnl,
    compose,
    continent_for,
    daily_hprs,
    daily_value_series,
    hhi_concentration,
    inception_cagr,
    max_drawdown,
    radar_axes,
    resolve_benchmark_group,
    rolling_twr,
    rollup_country_industry,
    sharpe_ratio,
)


class TestBenchmarkGroupResolution:
    def test_own_index_countries(self):
        assert resolve_benchmark_group("DE") == "DE"
        assert resolve_benchmark_group("FR") == "FR"
        assert resolve_benchmark_group("US") == "US"

    def test_uk_stands_alone_not_eu(self):
        assert resolve_benchmark_group("GB") == "UK"

    def test_continental_eu_without_own_index_falls_to_europe_region(self):
        assert resolve_benchmark_group("GR") == "EUROPE"  # Greece — no Athens index
        assert resolve_benchmark_group("NL") == "EUROPE"  # Netherlands — no AEX
        assert resolve_benchmark_group("AT") == "EUROPE"
        assert resolve_benchmark_group("CH") == "EUROPE"  # Switzerland (continent, not EU member)

    def test_china_maps_to_hang_seng_basket(self):
        assert resolve_benchmark_group("CN") == "CN"
        assert resolve_benchmark_group("HK") == "CN"

    def test_asian_country_without_own_index_falls_to_asia_region(self):
        assert resolve_benchmark_group("TW") == "ASIA"  # Taiwan — no TAIEX
        assert resolve_benchmark_group("KR") == "ASIA"  # Korea
        assert resolve_benchmark_group("JP") == "ASIA"  # Japan
        assert resolve_benchmark_group("IN") == "ASIA"  # India

    def test_continent_without_a_regional_index_falls_to_all(self):
        # South America, Africa, Oceania have no usable regional index.
        assert resolve_benchmark_group("BR") == "ALL"  # Brazil
        assert resolve_benchmark_group("ZA") == "ALL"  # South Africa
        assert resolve_benchmark_group("AU") == "ALL"  # Australia

    def test_unknown_or_blank_falls_to_all(self):
        assert resolve_benchmark_group("ZZ") == "ALL"
        assert resolve_benchmark_group("") == "ALL"
        assert resolve_benchmark_group(None) == "ALL"

    def test_case_insensitive(self):
        assert resolve_benchmark_group("de") == "DE"
        assert resolve_benchmark_group("tw") == "ASIA"

    def test_us_basket_has_multiple_indices(self):
        syms = basket_symbols("US")
        assert "SP500.IDX" in syms
        assert "NASDAQ.IDX" in syms
        assert len(syms) >= 3

    def test_europe_region_excludes_uk(self):
        syms = basket_symbols("EUROPE")
        assert "FTSE.IDX" not in syms  # UK is not in the continental basket
        assert "DAX.IDX" in syms

    def test_asia_region_includes_hang_seng(self):
        syms = basket_symbols("ASIA")
        assert "HSI.IDX" in syms

    def test_all_basket_is_union_of_every_group(self):
        all_syms = basket_symbols("ALL")
        assert set(all_syms) == set(all_equity_index_symbols())
        assert "SP500.IDX" in all_syms
        assert "HSI.IDX" in all_syms


class TestBasketDailyReturns:
    def test_averages_member_returns_per_date(self):
        prices = {
            "A": [{"date": "2025-01-01", "close": 100}, {"date": "2025-01-02", "close": 110}],  # +10%
            "B": [{"date": "2025-01-01", "close": 100}, {"date": "2025-01-02", "close": 120}],  # +20%
        }
        br = basket_daily_returns(["A", "B"], prices)
        assert math.isclose(br["2025-01-02"], 0.15)  # mean of +10% and +20%

    def test_tolerates_missing_member_on_a_date(self):
        prices = {
            "A": [{"date": "2025-01-01", "close": 100}, {"date": "2025-01-02", "close": 110}],
            "B": [{"date": "2025-01-02", "close": 100}, {"date": "2025-01-03", "close": 120}],  # different calendar
        }
        br = basket_daily_returns(["A", "B"], prices)
        # 2025-01-02 only A has a return (+10%); B's first day has no prior close
        assert math.isclose(br["2025-01-02"], 0.10)

    def test_empty_basket(self):
        assert basket_daily_returns([], {}) == {}


class TestContinentFor:
    def test_known_eu_country(self):
        assert continent_for("GR") == "Europe"
        assert continent_for("DE") == "Europe"

    def test_known_asia(self):
        assert continent_for("CN") == "Asia"
        assert continent_for("HK") == "Asia"
        assert continent_for("KZ") == "Asia"

    def test_north_america(self):
        assert continent_for("US") == "North America"

    def test_unknown_falls_to_bucket(self):
        # ZZ is reserved by ISO as "not in use" and is our canonical "no real code"
        assert continent_for("ZZ") == "Unknown"

    def test_legacy_csv_value_lands_in_unknown(self):
        """Preserved multi-CSV strings like "US, Asia" are not ISO-2 and must
        not blow up the continent grouping."""
        assert continent_for("US, Asia") == "Unknown"

    def test_blank_or_none_is_unknown(self):
        assert continent_for("") == "Unknown"
        assert continent_for(None) == "Unknown"

    def test_case_insensitive(self):
        assert continent_for("us") == "North America"

    def test_covers_every_continent(self):
        """Each of the seven continent buckets should be reachable from the
        country table — protects against accidental deletions on refactors."""
        from sentinel.portfolio_composition import CONTINENT_BY_COUNTRY

        seen = set(CONTINENT_BY_COUNTRY.values())
        expected = {
            "Africa",
            "Antarctica",
            "Asia",
            "Europe",
            "North America",
            "Oceania",
            "South America",
        }
        assert seen == expected

    def test_spot_check_coverage_across_iso3166(self):
        """A few less-common countries we don't trade today but might tomorrow —
        the table must classify them so the app doesn't break on first contact."""
        assert continent_for("IS") == "Europe"  # Iceland
        assert continent_for("VN") == "Asia"  # Vietnam
        assert continent_for("CO") == "South America"  # Colombia
        assert continent_for("MA") == "Africa"  # Morocco
        assert continent_for("FJ") == "Oceania"  # Fiji
        assert continent_for("MX") == "North America"  # Mexico

    def test_table_has_at_least_240_entries(self):
        """Sanity: ISO-3166-1 has ~250 codes; if we're missing a chunk something
        was nuked. Lower bound chosen with headroom."""
        from sentinel.portfolio_composition import CONTINENT_BY_COUNTRY

        assert len(CONTINENT_BY_COUNTRY) >= 240


class TestAssetClassFor:
    def test_known_kinds(self):
        assert asset_class_for(1) == "Stock"
        assert asset_class_for(7) == "ETF / Fund"
        assert asset_class_for(10) == "Depositary Receipt"

    def test_unknown_kind_falls_to_other(self):
        assert asset_class_for(999) == "Other"

    def test_none_is_other(self):
        assert asset_class_for(None) == "Other"


class TestCompose:
    @pytest.fixture
    def securities_map(self):
        return {
            "AAPL.US": {"geography": "US", "industry": "Tech", "currency": "USD", "instr_kind_c": 1},
            "ASML.EU": {"geography": "NL", "industry": "Semis", "currency": "EUR", "instr_kind_c": 1},
            "VWCE.EU": {"geography": "", "industry": "", "currency": "EUR", "instr_kind_c": 7},
            "TSM.US": {"geography": "TW", "industry": "Semis", "currency": "USD", "instr_kind_c": 10},
        }

    def test_country_pct_sums_to_1(self, securities_map):
        result = compose({"AAPL.US": 100, "ASML.EU": 100, "TSM.US": 100}, securities_map)
        total = sum(b.pct for b in result["by_country"])
        assert math.isclose(total, 1.0)

    def test_country_buckets_have_correct_share(self, securities_map):
        result = compose({"AAPL.US": 300, "ASML.EU": 100}, securities_map)
        by_country = {b.name: b.pct for b in result["by_country"]}
        assert math.isclose(by_country["US"], 0.75)
        assert math.isclose(by_country["NL"], 0.25)

    def test_continent_groups_countries(self, securities_map):
        result = compose({"AAPL.US": 100, "TSM.US": 100, "ASML.EU": 100}, securities_map)
        by_cont = {b.name: b.pct for b in result["by_continent"]}
        # AAPL + TSM = North America + Asia, ASML = Europe
        assert math.isclose(by_cont["North America"], 1 / 3)
        assert math.isclose(by_cont["Asia"], 1 / 3)
        assert math.isclose(by_cont["Europe"], 1 / 3)

    def test_blank_geography_lands_in_unknown(self, securities_map):
        result = compose({"VWCE.EU": 100, "AAPL.US": 100}, securities_map)
        by_country = {b.name: b.pct for b in result["by_country"]}
        assert "Unknown" in by_country
        assert math.isclose(by_country["Unknown"], 0.5)

    def test_unknown_sorted_to_end(self, securities_map):
        """Even if Unknown is the largest bucket, it should not lead the list."""
        result = compose({"VWCE.EU": 900, "AAPL.US": 100}, securities_map)
        assert result["by_country"][0].name == "US"
        assert result["by_country"][-1].name == "Unknown"

    def test_zero_total_returns_empty_lists(self, securities_map):
        result = compose({}, securities_map)
        for key in ("by_country", "by_continent", "by_industry", "by_currency", "by_asset_class"):
            assert result[key] == []

    def test_etf_appears_as_etf_asset_class(self, securities_map):
        result = compose({"VWCE.EU": 100, "AAPL.US": 100}, securities_map)
        by_kind = {b.name: b.pct for b in result["by_asset_class"]}
        assert by_kind["ETF / Fund"] == 0.5
        assert by_kind["Stock"] == 0.5

    def test_missing_security_lands_in_unknown_buckets(self):
        result = compose({"NOTFOUND.US": 100}, {})
        assert result["by_country"][0].name == "Unknown"
        assert result["by_industry"][0].name == "Unknown"
        assert result["by_currency"][0].name == "Unknown"
        assert result["by_asset_class"][0].name == "Other"


class TestRollupCountryIndustry:
    """The unit-agnostic rollup helper used by ideal + post-plan compositions."""

    @pytest.fixture
    def securities_map(self):
        return {
            "AAPL.US": {"geography": "US", "industry": "Tech"},
            "ASML.EU": {"geography": "NL", "industry": "Semis"},
            "TSM.US": {"geography": "TW", "industry": "Semis"},
        }

    def test_rollup_normalizes_to_pcts(self, securities_map):
        # Treat the weights as ideal %s — sum doesn't have to be 1.0 going in,
        # the bucketer normalizes for us.
        result = rollup_country_industry(
            {"AAPL.US": 0.4, "ASML.EU": 0.3, "TSM.US": 0.3},
            securities_map,
        )
        by_country = {b.name: b.pct for b in result["by_country"]}
        assert math.isclose(by_country["US"], 0.4)
        assert math.isclose(by_country["NL"], 0.3)
        assert math.isclose(by_country["TW"], 0.3)

    def test_industry_aggregates_across_countries(self, securities_map):
        # ASML and TSM are both Semis from different countries
        result = rollup_country_industry(
            {"AAPL.US": 100, "ASML.EU": 100, "TSM.US": 100},
            securities_map,
        )
        by_industry = {b.name: b.pct for b in result["by_industry"]}
        assert math.isclose(by_industry["Semis"], 2 / 3)
        assert math.isclose(by_industry["Tech"], 1 / 3)

    def test_zero_weights_excluded(self, securities_map):
        result = rollup_country_industry(
            {"AAPL.US": 100, "ASML.EU": 0, "TSM.US": 0},
            securities_map,
        )
        assert [b.name for b in result["by_country"]] == ["US"]

    def test_missing_security_lands_in_unknown(self):
        result = rollup_country_industry({"NOPE": 100}, {})
        assert result["by_country"][0].name == "Unknown"
        assert result["by_industry"][0].name == "Unknown"


class TestDailyValueSeries:
    def test_basic_snapshots(self):
        snaps = [
            {"date": 1715040000, "data": {"positions": {"AAPL.US": {"value_eur": 100}}, "cash_eur": 50}},
            {"date": 1715126400, "data": {"positions": {"AAPL.US": {"value_eur": 110}}, "cash_eur": 50}},
        ]
        series = daily_value_series(snaps)
        assert len(series) == 2
        assert series[0][1] == 150.0
        assert series[1][1] == 160.0

    def test_missing_date_is_skipped(self):
        snaps = [{"date": None, "data": {"positions": {}, "cash_eur": 100}}]
        assert daily_value_series(snaps) == []


class TestDailyHprs:
    """Daily holding-period returns derived from the pnl-history daily list.
    Same math the /api/portfolio/pnl-history rolling TWR uses — kept in
    sync via a single shared implementation."""

    def test_simple_two_day_no_deposit(self):
        daily = [
            {"date": "2024-01-01", "total_value_eur": 100.0, "net_deposits_eur": 0.0},
            {"date": "2024-01-02", "total_value_eur": 110.0, "net_deposits_eur": 0.0},
        ]
        returns = daily_hprs(daily)
        assert len(returns) == 1
        assert math.isclose(returns[0], 0.1)

    def test_deposit_stripped_from_return(self):
        # Portfolio jumps 100 -> 200 but 80 of that was a deposit. Real HPR = 20%.
        daily = [
            {"date": "2024-01-01", "total_value_eur": 100.0, "net_deposits_eur": 0.0},
            {"date": "2024-01-02", "total_value_eur": 200.0, "net_deposits_eur": 80.0},
        ]
        returns = daily_hprs(daily)
        assert math.isclose(returns[0], 0.2)

    def test_skips_when_prior_value_zero(self):
        daily = [
            {"date": "2024-01-01", "total_value_eur": 0.0, "net_deposits_eur": 0.0},
            {"date": "2024-01-02", "total_value_eur": 100.0, "net_deposits_eur": 100.0},
        ]
        assert daily_hprs(daily) == []


class TestRollingTwr:
    """The shared rolling-TWR helper /pnl-history and build_composition use."""

    def _series(self, values, deposits=None):
        deposits = deposits or [0.0] * len(values)
        from datetime import date, timedelta

        return [
            {
                "date": (date(2024, 1, 1) + timedelta(days=i)).isoformat(),
                "total_value_eur": v,
                "net_deposits_eur": d,
            }
            for i, (v, d) in enumerate(zip(values, deposits, strict=True))
        ]

    def test_compounded_two_day_no_deposits(self):
        # +10% then -5% -> total (1.10 * 0.95) - 1 = 0.045
        daily = self._series([100, 110, 104.5])
        twr = rolling_twr(daily, window_days=2)
        assert math.isclose(twr, 0.045, abs_tol=1e-9)

    def test_strips_window_deposit(self):
        # Day 1: +10%. Day 2: value 200 but 75 was a deposit (real HPR = 13.6%).
        daily = self._series([100, 110, 200], deposits=[0.0, 0.0, 75.0])
        # 1.10 * 1.1363636... - 1 ≈ 0.25
        twr = rolling_twr(daily, window_days=2)
        assert math.isclose(twr, 0.25, abs_tol=1e-3)

    def test_too_short_window_returns_none(self):
        assert rolling_twr([], window_days=5) is None
        assert rolling_twr(self._series([100]), window_days=5) is None

    def test_zero_value_in_window_returns_none(self):
        daily = self._series([0, 100, 110])
        assert rolling_twr(daily, window_days=2) is None


class TestInceptionCagr:
    """CAGR from inception — final_value / total_deposits over years."""

    def test_basic_one_year_30pct(self):
        from datetime import date, timedelta

        daily = [
            {"date": date(2024, 1, 1).isoformat(), "total_value_eur": 0.0, "net_deposits_eur": 0.0},
            {
                "date": (date(2024, 1, 1) + timedelta(days=365)).isoformat(),
                "total_value_eur": 1300.0,
                "net_deposits_eur": 1000.0,
            },
        ]
        cagr, years = inception_cagr(daily)
        # 1300 / 1000 = 1.3 over 1 year -> 30%
        assert math.isclose(cagr, 0.3, abs_tol=1e-2)
        assert math.isclose(years, 1.0, abs_tol=1e-2)

    def test_zero_deposits_returns_zero(self):
        daily = [
            {"date": "2024-01-01", "total_value_eur": 0.0, "net_deposits_eur": 0.0},
            {"date": "2025-01-01", "total_value_eur": 100.0, "net_deposits_eur": 0.0},
        ]
        cagr, _ = inception_cagr(daily)
        assert cagr == 0.0

    def test_too_short_history(self):
        cagr, years = inception_cagr([])
        assert cagr == 0.0 and years == 0.0


class TestBuildDailyPnl:
    """The shared pnl-history daily builder used by both endpoints."""

    def test_attributes_deposits_by_date(self):
        # Snapshot in unix-ts form; deposits_by_date maps ISO -> cumulative EUR.
        from datetime import datetime, timezone

        snaps = [
            {
                "date": int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()),
                "data": {"positions": {"X": {"value_eur": 90}}, "cash_eur": 10.0},
            },
            {
                "date": int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp()),
                "data": {"positions": {"X": {"value_eur": 130}}, "cash_eur": 70.0},
            },
        ]
        deposits = {"2024-01-01": 100.0, "2024-01-02": 200.0}
        daily = build_daily_pnl(snaps, deposits)
        assert len(daily) == 2
        assert daily[0]["total_value_eur"] == 100.0
        assert daily[1]["total_value_eur"] == 200.0
        assert daily[1]["net_deposits_eur"] == 200.0
        assert daily[1]["pnl_eur"] == 0.0  # 200 - 200 deposits


class TestAnnualizedVolatility:
    def test_constant_returns_zero_vol(self):
        assert annualized_volatility([0.01, 0.01, 0.01, 0.01]) == 0.0

    def test_known_stdev(self):
        # Returns with sample stdev 0.01 -> annualized 0.01 * sqrt(252)
        returns = [0.01, -0.01, 0.01, -0.01]
        # sample stdev = sqrt(sum(sq dev)/n-1) = sqrt((4*0.0001)/3) ≈ 0.01155
        expected = 0.01154700538 * math.sqrt(TRADING_DAYS_PER_YEAR)
        assert math.isclose(annualized_volatility(returns), expected, rel_tol=1e-3)


class TestMaxDrawdown:
    def test_monotonic_up_is_zero_dd(self):
        assert max_drawdown([100, 110, 120, 130]) == 0.0

    def test_known_drawdown(self):
        # Peak at 200, trough at 100 -> 50% DD
        assert math.isclose(max_drawdown([100, 200, 100, 150]), 0.5)

    def test_empty_input(self):
        assert max_drawdown([]) == 0.0


class TestSharpeRatio:
    def test_zero_volatility_returns_zero(self):
        assert sharpe_ratio([0.01, 0.01, 0.01], risk_free_rate=0.02) == 0.0

    def test_positive_mean_above_rf_is_positive_sharpe(self):
        # Mean 0.005, stdev 0.01 -> annualized Sharpe ~7.9 minus rf
        returns = [0.015, -0.005, 0.015, -0.005, 0.015]
        s = sharpe_ratio(returns, risk_free_rate=0.0)
        assert s > 0

    def test_too_few_returns_zero(self):
        assert sharpe_ratio([], risk_free_rate=0.02) == 0.0
        assert sharpe_ratio([0.01], risk_free_rate=0.02) == 0.0


class TestBeta:
    def test_identical_series_beta_one(self):
        b = beta([0.01, 0.02, -0.01], [0.01, 0.02, -0.01])
        assert math.isclose(b, 1.0)

    def test_zero_correlation_zero_beta(self):
        b = beta([0.01, -0.01, 0.01, -0.01], [0.01, 0.01, -0.01, -0.01])
        assert math.isclose(b, 0.0)

    def test_perfect_anti_correlation_negative_beta(self):
        b = beta([0.01, -0.01, 0.01], [-0.01, 0.01, -0.01])
        assert b < 0

    def test_mismatched_lengths_aligns_to_shorter(self):
        # No crash, uses shortest tail
        b = beta([0.01, 0.02, 0.03], [0.01, 0.02])
        assert isinstance(b, float)


class TestHhiConcentration:
    def test_single_position_is_one(self):
        assert hhi_concentration({"AAPL.US": 100}) == 1.0

    def test_two_equal_positions_is_half(self):
        assert math.isclose(hhi_concentration({"A": 100, "B": 100}), 0.5)

    def test_ten_equal_positions_is_one_tenth(self):
        positions = {f"S{i}": 100 for i in range(10)}
        assert math.isclose(hhi_concentration(positions), 0.1)

    def test_empty_is_zero(self):
        assert hhi_concentration({}) == 0.0

    def test_negative_positions_excluded(self):
        # Sanity: a short / negative quantity shouldn't poison HHI.
        result = hhi_concentration({"A": 100, "B": -50})
        assert math.isclose(result, 1.0)


class TestRadarAxes:
    def test_neutral_metrics_land_in_range(self):
        """A 'neutral' portfolio (0 return, vol/dd/concentration at the scale
        midpoint) should land between 0.2 and 0.7 on every axis — clearly not
        excellent, clearly not catastrophic, with each axis on its own scale."""
        axes = radar_axes(
            {
                "return_1y": 0.0,
                "sharpe": 0.0,
                "alpha_1y_vs_home": 0.0,
                "volatility": 0.2,
                "max_drawdown": 0.25,
                "hhi": 0.275,
            }
        )
        for k, v in axes.items():
            assert 0.2 < v < 0.7, f"{k}={v} expected mid-range"

    def test_excellent_portfolio_scores_high(self):
        axes = radar_axes(
            {
                "return_1y": 0.5,
                "sharpe": 3.0,
                "alpha_1y_vs_home": 0.25,
                "volatility": 0.05,
                "max_drawdown": 0.05,
                "hhi": 0.05,
            }
        )
        for k, v in axes.items():
            assert v >= 0.8, f"{k}={v} expected near top"

    def test_clamps_to_unit_interval(self):
        axes = radar_axes(
            {
                "return_1y": 10.0,
                "sharpe": 100.0,
                "alpha_1y_vs_home": -5.0,
                "volatility": -1.0,
                "max_drawdown": -1.0,
                "hhi": -1.0,
            }
        )
        for v in axes.values():
            assert 0.0 <= v <= 1.0


@pytest.mark.asyncio
async def test_build_composition_integration_smoke():
    """Integration smoke: build_composition orchestrates DB + currency + settings
    correctly with no positions and no benchmarks (fresh-deploy path)."""
    db = AsyncMock()
    db.get_all_positions = AsyncMock(return_value=[])
    db.get_all_securities = AsyncMock(return_value=[])
    db.get_portfolio_snapshots = AsyncMock(return_value=[])
    db.get_cash_flows = AsyncMock(return_value=[])
    db.get_benchmarks = AsyncMock(return_value=[])
    db.get_benchmark_prices = AsyncMock(return_value=[])

    currency = AsyncMock()
    settings = AsyncMock()
    settings.get = AsyncMock(return_value=DEFAULT_RISK_FREE_RATE)

    payload = await build_composition(db, currency, settings)

    assert payload["total_value_eur"] == 0
    for key in ("by_country", "by_continent", "by_industry", "by_currency", "by_asset_class"):
        assert payload["composition"][key] == []
    assert payload["metrics"]["volatility"] == 0.0
    # No holdings -> nothing to benchmark against home markets.
    assert payload["metrics"]["beta_vs_home"] == 0.0
    assert payload["metrics"]["alpha_1y_vs_home"] == 0.0
    assert payload["metrics"]["home_coverage_pct"] == 0.0
    assert payload["home_markets"] == []
    # Radar axes are present and bounded.
    assert set(payload["radar"].keys()) == {
        "return_1y",
        "sharpe",
        "alpha",
        "low_volatility",
        "low_drawdown",
        "low_concentration",
    }
    for v in payload["radar"].values():
        assert 0.0 <= v <= 1.0


@pytest.mark.asyncio
async def test_build_composition_home_market_aggregate():
    """Each holding is benchmarked vs its own home-market basket, then
    value-weighted. A US holding goes against the US basket, a CN holding
    against Hang Seng — never one global index."""
    from datetime import date, timedelta

    db = AsyncMock()
    # Two holdings: one US, one Chinese.
    db.get_all_positions = AsyncMock(
        return_value=[
            {"symbol": "AAPL.US", "quantity": 10, "current_price": 100, "currency": "USD"},
            {"symbol": "BABA.HK", "quantity": 10, "current_price": 100, "currency": "USD"},
        ]
    )
    db.get_all_securities = AsyncMock(
        return_value=[
            {"symbol": "AAPL.US", "geography": "US", "industry": "Tech", "currency": "USD", "instr_kind_c": 1},
            {"symbol": "BABA.HK", "geography": "CN", "industry": "Tech", "currency": "USD", "instr_kind_c": 1},
        ]
    )
    db.get_portfolio_snapshots = AsyncMock(return_value=[])
    db.get_cash_flows = AsyncMock(return_value=[])

    # 60 daily dates of price history for securities + benchmark indices.
    dates = [(date.today() - timedelta(days=60 - i)).isoformat() for i in range(60)]

    def rising(base, step):
        return [{"date": d, "close": base + i * step} for i, d in enumerate(dates)]

    sec_prices = {
        "AAPL.US": rising(100, 1.0),  # steady riser
        "BABA.HK": rising(100, 0.5),
    }
    # SP500 basket member rises slower than AAPL (AAPL has positive alpha);
    # HSI rises faster than BABA (BABA has negative alpha).
    bench_prices = {
        "SP500.IDX": rising(100, 0.5),
        "NASDAQ.IDX": rising(100, 0.5),
        "DJI30.IDX": rising(100, 0.5),
        "RUT.IDX": rising(100, 0.5),
        "HSI.IDX": rising(100, 1.0),
    }

    db.get_prices = AsyncMock(side_effect=lambda symbol, **kw: sec_prices.get(symbol, []))
    db.get_benchmark_prices = AsyncMock(side_effect=lambda symbol, **kw: bench_prices.get(symbol, []))

    currency = AsyncMock()
    currency.to_eur_for_date = AsyncMock(side_effect=lambda amt, *a, **k: amt)
    settings = AsyncMock()
    settings.get = AsyncMock(return_value=DEFAULT_RISK_FREE_RATE)

    # PositionCalculator converts via currency.to_eur
    currency.to_eur = AsyncMock(side_effect=lambda amt, *a, **k: amt)

    payload = await build_composition(db, currency, settings)

    groups = {g["group"] for g in payload["home_markets"]}
    assert groups == {"US", "CN"}
    # Both holdings covered.
    assert payload["metrics"]["home_coverage_pct"] == 1.0
    # AAPL beat its (slower) US basket -> positive US alpha; BABA lagged its
    # (faster) Hang Seng -> negative CN alpha.
    by_group = {g["group"]: g for g in payload["home_markets"]}
    assert by_group["US"]["alpha_1y"] > 0
    assert by_group["CN"]["alpha_1y"] < 0
