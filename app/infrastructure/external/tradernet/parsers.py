"""Tradernet API response parsers."""

import logging
from datetime import datetime, timedelta

from app.infrastructure.external.tradernet.models import OHLC, OrderResult

logger = logging.getLogger(__name__)


def parse_price_data_string(data, symbol: str):
    """Parse price data if it's a JSON string."""
    if isinstance(data, str):
        import json

        try:
            return json.loads(data)
        except json.JSONDecodeError:
            logger.warning(
                f"Received non-JSON string response for {symbol}: {data[:100]}"
            )
            return []
    return data


def parse_hloc_format(data: dict, symbol: str, start: datetime) -> list[OHLC]:
    """Parse hloc format: {'hloc': {'SYMBOL': [[high, low, open, close], ...]}}."""
    hloc_data = data.get("hloc", {})
    if not hloc_data or not isinstance(hloc_data, dict):
        return []

    symbol_data = hloc_data.get(symbol, [])
    if not symbol_data or not isinstance(symbol_data, list):
        return []

    result = []
    current_date = start
    for candle_array in symbol_data:
        if isinstance(candle_array, list) and len(candle_array) >= 4:
            if len(candle_array) == 4:
                high = float(candle_array[0])
                low = float(candle_array[1])
                open_price = float(candle_array[2])
                close = float(candle_array[3])
            else:
                high = float(candle_array[0]) if len(candle_array) > 0 else 0
                low = float(candle_array[1]) if len(candle_array) > 1 else 0
                open_price = float(candle_array[2]) if len(candle_array) > 2 else 0
                close = float(candle_array[3]) if len(candle_array) > 3 else 0

            result.append(
                OHLC(
                    timestamp=current_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=0,
                )
            )
            current_date += timedelta(days=1)

    return result


def parse_candles_format(data: dict) -> list[OHLC]:
    """Parse candles format from dict."""
    candles = data.get("candles", [])
    result = []
    for candle in candles:
        if isinstance(candle, dict):
            result.append(
                OHLC(
                    timestamp=datetime.fromtimestamp(candle.get("t", 0)),
                    open=float(candle.get("o", 0)),
                    high=float(candle.get("h", 0)),
                    low=float(candle.get("l", 0)),
                    close=float(candle.get("c", 0)),
                    volume=int(candle.get("v", 0)),
                )
            )
    return result


def parse_candles_list(data: list) -> list[OHLC]:
    """Parse direct list of candles."""
    result = []
    for candle in data:
        if isinstance(candle, dict):
            result.append(
                OHLC(
                    timestamp=datetime.fromtimestamp(candle.get("t", 0)),
                    open=float(candle.get("o", 0)),
                    high=float(candle.get("h", 0)),
                    low=float(candle.get("l", 0)),
                    close=float(candle.get("c", 0)),
                    volume=int(candle.get("v", 0)),
                )
            )
    return result


def get_trading_mode() -> str:
    """Get trading mode from cache."""
    from app.infrastructure.cache import cache

    trading_mode = "research"
    try:
        cached_settings = cache.get("settings:all")
        if cached_settings and "trading_mode" in cached_settings:
            trading_mode = cached_settings["trading_mode"]
    except Exception:
        pass
    return trading_mode


def create_research_mode_order(
    symbol: str, side: str, quantity: float, client
) -> OrderResult:
    """Create a mock order result for research mode."""
    try:
        quote = client.get_quote(symbol)
        mock_price = quote.price if quote else 0.0
    except Exception:
        mock_price = 0.0

    return OrderResult(
        order_id=f"RESEARCH_{symbol}_{datetime.now().timestamp()}",
        symbol=symbol,
        side=side.upper(),
        quantity=quantity,
        price=mock_price,
        status="submitted",
    )


def create_order_result(result, symbol: str, side: str, quantity: float) -> OrderResult:
    """Create OrderResult from API response."""
    if isinstance(result, dict):
        return OrderResult(
            order_id=str(result.get("order_id", result.get("orderId", ""))),
            symbol=symbol,
            side=side.upper(),
            quantity=quantity,
            price=float(result.get("price", 0)),
            status=result.get("status", "submitted"),
        )
    return OrderResult(
        order_id=str(result) if result else "",
        symbol=symbol,
        side=side.upper(),
        quantity=quantity,
        price=0,
        status="submitted",
    )
