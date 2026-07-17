"""Current portfolio valuation from account state plus market data."""

from __future__ import annotations

import inspect
import json
import logging
import time
from typing import Any

from sentinel.broker import Broker
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.utils.positions import PositionCalculator

QUOTE_FALLBACK_TTL_SECONDS = 60 * 60
logger = logging.getLogger(__name__)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class PortfolioValuationService:
    """Build one live valuation used by the portfolio and performance APIs."""

    def __init__(
        self,
        db: Database | None = None,
        broker: Broker | None = None,
        currency: Currency | None = None,
    ):
        self._db = db or Database()
        self._broker = broker or Broker()
        self._currency = currency or Currency()

    async def current(self) -> dict[str, Any]:
        positions, cash = await self._account_state()
        symbols = [position["symbol"] for position in positions if position.get("symbol")]
        quotes = await self._quotes(symbols)
        securities = await self._db.get_all_securities(active_only=False)
        securities_map = {security["symbol"]: security for security in securities}

        pos_calc = PositionCalculator(currency_converter=self._currency)
        enriched = []
        positions_total_eur = 0.0
        invested_total_eur = 0.0
        intraday_pnl_eur = 0.0
        intraday_count = 0

        for position in positions:
            symbol = position["symbol"]
            quantity = _as_float(position.get("quantity"))
            avg_cost = _as_float(position.get("avg_cost"))
            currency = position.get("currency") or securities_map.get(symbol, {}).get("currency") or "EUR"
            quote = quotes.get(symbol) or {}
            price = _as_float(quote.get("price") or position.get("current_price"))

            value_local = await pos_calc.calculate_value_local(quantity, price)
            value_eur = await pos_calc.calculate_value_eur(quantity, price, currency)
            invested_eur = await pos_calc.calculate_value_eur(quantity, avg_cost, currency)
            profit_pct, _ = pos_calc.calculate_profit(quantity, price, avg_cost)

            positions_total_eur += value_eur
            invested_total_eur += invested_eur

            previous_close = _as_float(position.get("previous_close_price"), default=0.0)
            if previous_close > 0:
                intraday_native = (price - previous_close) * quantity
                intraday_pnl_eur += await self._currency.to_eur(intraday_native, currency)
                intraday_count += 1

            security = securities_map.get(symbol, {})
            enriched.append(
                {
                    **position,
                    "current_price": price,
                    "currency": currency,
                    "value_local": value_local,
                    "value_eur": value_eur,
                    "invested_eur": invested_eur,
                    "profit_pct": profit_pct,
                    "name": security.get("name", position.get("name") or symbol),
                    "price_source": "quote" if quote.get("price") else "account",
                }
            )

        total_cash_eur = 0.0
        for currency, amount in cash.items():
            total_cash_eur += await self._currency.to_eur(amount, currency)

        portfolio_return_pct = (
            round((positions_total_eur - invested_total_eur) / invested_total_eur * 100, 2)
            if invested_total_eur > 0
            else 0.0
        )

        return {
            "positions": enriched,
            "cash": cash,
            "total_cash_eur": total_cash_eur,
            "total_positions_eur": positions_total_eur,
            "total_value_eur": positions_total_eur + total_cash_eur,
            "portfolio_return_pct": portfolio_return_pct,
            "intraday_pnl_eur": intraday_pnl_eur if intraday_count else None,
        }

    async def _account_state(self) -> tuple[list[dict], dict[str, float]]:
        try:
            if await self._connect_broker():
                account = await self._broker.get_portfolio()
                positions = account.get("positions") or []
                cash = account.get("cash") or {}
                if positions or cash:
                    return positions, cash
        except Exception as e:
            logger.warning("Live broker account valuation unavailable; falling back to database positions: %s", e)

        return await self._db.get_all_positions(), await self._db.get_cash_balances()

    async def _quotes(self, symbols: list[str]) -> dict[str, dict]:
        if not symbols:
            return {}

        quotes: dict[str, dict] = {}
        try:
            if await self._connect_broker():
                quotes = await self._broker.get_quotes(symbols)
        except Exception as e:
            logger.warning("Live quote valuation unavailable; falling back to cached/account prices: %s", e)
            quotes = {}

        missing = set(symbols) - set(quotes)
        if missing:
            now = int(time.time())
            securities = await self._db.get_all_securities(active_only=False)
            for security in securities:
                symbol = security["symbol"]
                if symbol not in missing:
                    continue
                updated_at = security.get("quote_updated_at") or 0
                if now - int(updated_at) > QUOTE_FALLBACK_TTL_SECONDS:
                    continue
                try:
                    quote = json.loads(security.get("quote_data") or "{}")
                except json.JSONDecodeError:
                    continue
                if quote.get("ltp"):
                    quote["price"] = quote.get("ltp")
                    quote["symbol"] = quote.get("c") or symbol
                    quotes[symbol] = quote

        return quotes

    async def _connect_broker(self) -> bool:
        if bool(getattr(self._broker, "connected", False)):
            return True
        connect: Any = getattr(self._broker, "connect", None)
        if not callable(connect):
            return False
        result = connect()
        if inspect.isawaitable(result):
            result = await result
        return bool(result)
