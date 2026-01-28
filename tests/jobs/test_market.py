"""Tests for jobs/market.py - Market timing checks."""

import pytest

from sentinel.jobs.types import BaseJob, MarketTiming
from sentinel.jobs.market import can_execute_now


class MockJob(BaseJob):
    """Test job implementation."""

    async def execute(self) -> None:
        pass


class MockMarketChecker:
    """Mock market checker for testing."""

    def __init__(self, any_open=False, security_markets=None, all_closed=True):
        self._any_open = any_open
        self._security_markets = security_markets or {}
        self._all_closed = all_closed

    def is_any_market_open(self) -> bool:
        return self._any_open

    def is_security_market_open(self, symbol: str) -> bool:
        return self._security_markets.get(symbol, False)

    def are_all_markets_closed(self) -> bool:
        return self._all_closed


def test_can_execute_now_any_time():
    """ANY_TIME should always allow execution."""
    job = MockJob(
        _id="test:job",
        _job_type="test",
        _market_timing=MarketTiming.ANY_TIME,
    )
    checker = MockMarketChecker(any_open=True)

    assert can_execute_now(job, checker) is True


def test_can_execute_now_any_time_markets_closed():
    """ANY_TIME should allow execution even when markets closed."""
    job = MockJob(
        _id="test:job",
        _job_type="test",
        _market_timing=MarketTiming.ANY_TIME,
    )
    checker = MockMarketChecker(any_open=False)

    assert can_execute_now(job, checker) is True


def test_can_execute_now_after_market_close_when_open():
    """AFTER_MARKET_CLOSE should not execute when market is open."""
    job = MockJob(
        _id="test:job",
        _job_type="test",
        _market_timing=MarketTiming.AFTER_MARKET_CLOSE,
    )
    checker = MockMarketChecker(any_open=True)

    assert can_execute_now(job, checker) is False


def test_can_execute_now_after_market_close_when_closed():
    """AFTER_MARKET_CLOSE should execute when market is closed."""
    job = MockJob(
        _id="test:job",
        _job_type="test",
        _market_timing=MarketTiming.AFTER_MARKET_CLOSE,
    )
    checker = MockMarketChecker(any_open=False)

    assert can_execute_now(job, checker) is True


def test_can_execute_now_after_market_close_with_subject():
    """AFTER_MARKET_CLOSE with subject should check security's market."""
    job = MockJob(
        _id="ml:retrain:AAPL.US",
        _job_type="ml:retrain",
        _market_timing=MarketTiming.AFTER_MARKET_CLOSE,
        _subject="AAPL.US",
    )

    # AAPL market is open
    checker = MockMarketChecker(
        any_open=True,
        security_markets={"AAPL.US": True},
    )
    assert can_execute_now(job, checker) is False

    # AAPL market is closed
    checker = MockMarketChecker(
        any_open=True,
        security_markets={"AAPL.US": False},
    )
    assert can_execute_now(job, checker) is True


def test_can_execute_now_during_market_open_when_open():
    """DURING_MARKET_OPEN should execute when market is open."""
    job = MockJob(
        _id="test:job",
        _job_type="test",
        _market_timing=MarketTiming.DURING_MARKET_OPEN,
    )
    checker = MockMarketChecker(any_open=True)

    assert can_execute_now(job, checker) is True


def test_can_execute_now_during_market_open_when_closed():
    """DURING_MARKET_OPEN should not execute when market is closed."""
    job = MockJob(
        _id="test:job",
        _job_type="test",
        _market_timing=MarketTiming.DURING_MARKET_OPEN,
    )
    checker = MockMarketChecker(any_open=False)

    assert can_execute_now(job, checker) is False


def test_can_execute_now_during_market_open_with_subject():
    """DURING_MARKET_OPEN with subject should check security's market."""
    job = MockJob(
        _id="trading:execute:VOW.GR",
        _job_type="trading:execute",
        _market_timing=MarketTiming.DURING_MARKET_OPEN,
        _subject="VOW.GR",
    )

    # VOW market is open
    checker = MockMarketChecker(
        any_open=True,
        security_markets={"VOW.GR": True},
    )
    assert can_execute_now(job, checker) is True

    # VOW market is closed
    checker = MockMarketChecker(
        any_open=True,
        security_markets={"VOW.GR": False},
    )
    assert can_execute_now(job, checker) is False


def test_can_execute_now_all_markets_closed_true():
    """ALL_MARKETS_CLOSED should execute when all closed."""
    job = MockJob(
        _id="analytics:correlation",
        _job_type="analytics:correlation",
        _market_timing=MarketTiming.ALL_MARKETS_CLOSED,
    )
    checker = MockMarketChecker(all_closed=True, any_open=False)

    assert can_execute_now(job, checker) is True


def test_can_execute_now_all_markets_closed_false():
    """ALL_MARKETS_CLOSED should not execute when any open."""
    job = MockJob(
        _id="analytics:correlation",
        _job_type="analytics:correlation",
        _market_timing=MarketTiming.ALL_MARKETS_CLOSED,
    )
    checker = MockMarketChecker(all_closed=False, any_open=True)

    assert can_execute_now(job, checker) is False
