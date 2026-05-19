"""Freedom24 Favorites to Sentinel universe reconciliation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

FREEDOM24_UNIVERSE_SOURCE = "freedom24_default"
BROKER_POSITION_UNIVERSE_SOURCE = "broker_position"


@dataclass
class SecurityImportResult:
    symbol: str
    name: str
    prices_count: int
    re_enabled: bool


@dataclass
class UniverseReconciliationResult:
    imported: list[str] = field(default_factory=list)
    reactivated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    buy_disabled: list[str] = field(default_factory=list)
    buy_reenabled: list[str] = field(default_factory=list)
    provenance_updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(
            self.imported
            or self.reactivated
            or self.removed
            or self.buy_disabled
            or self.buy_reenabled
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "imported": self.imported,
            "reactivated": self.reactivated,
            "removed": self.removed,
            "buy_disabled": self.buy_disabled,
            "buy_reenabled": self.buy_reenabled,
            "provenance_updated": self.provenance_updated,
            "skipped": self.skipped,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_int_flag(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _min_lot_from_info(info: dict, existing: dict | None) -> int:
    raw = info.get("lot")
    if raw is None and existing:
        raw = existing.get("min_lot")
    try:
        return int(float(raw if raw is not None else 1))
    except (TypeError, ValueError):
        return 1


def _market_id_from_info(info: dict, existing: dict | None) -> str:
    market = info.get("mrkt")
    if isinstance(market, dict) and market.get("mkt_id") is not None:
        return str(market.get("mkt_id"))
    if existing and existing.get("market_id") is not None:
        return str(existing.get("market_id"))
    return ""


def _default_list_from_payload(payload: object) -> dict | None:
    if not isinstance(payload, dict):
        return None

    default_id = payload.get("defaultId")
    user_lists = payload.get("userStockLists")
    if not isinstance(user_lists, list):
        return None

    for item in user_lists:
        if isinstance(item, dict) and item.get("id") == default_id:
            return item
    return None


def _tickers_from_default_list(stock_list: dict) -> set[str]:
    tickers = stock_list.get("tickers")
    if not isinstance(tickers, list):
        return set()
    return {ticker.strip() for ticker in tickers if isinstance(ticker, str) and ticker.strip()}


async def _position_quantity(db, symbol: str) -> float:
    position = await db.get_position(symbol)
    if not position:
        return 0.0
    try:
        return float(position.get("quantity", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


async def import_security_from_broker(
    db,
    broker,
    symbol: str,
    *,
    info: dict | None = None,
    fallback_info: dict | None = None,
    geography: str | None = None,
    industry: str | None = None,
    universe_source: str = FREEDOM24_UNIVERSE_SOURCE,
    universe_last_seen_at: str | None = None,
    fetch_prices: bool = True,
) -> SecurityImportResult:
    """Add or reactivate one broker security without disturbing analysis history."""
    symbol = symbol.strip()
    existing = await db.get_security(symbol)

    if info is None:
        try:
            info = await broker.get_security_info(symbol)
        except Exception as e:
            logger.warning("Broker metadata lookup failed for %s: %s", symbol, e)
            info = None

    broker_info: dict[str, Any] = info if isinstance(info, dict) else {}
    fallback: dict[str, Any] = fallback_info if isinstance(fallback_info, dict) else {}
    if not broker_info:
        logger.warning("Importing %s with incomplete broker metadata; metadata sync will retry later", symbol)

    name = (
        broker_info.get("short_name")
        or broker_info.get("name")
        or fallback.get("name")
        or (existing or {}).get("name")
        or symbol
    )
    currency = (
        broker_info.get("currency")
        or broker_info.get("curr")
        or fallback.get("currency")
        or (existing or {}).get("currency")
        or "EUR"
    )
    market_id = _market_id_from_info(broker_info, existing)
    min_lot = _min_lot_from_info(broker_info, existing)

    security_data: dict[str, Any] = {
        "name": name,
        "currency": currency,
        "market_id": market_id,
        "min_lot": min_lot,
        "active": 1,
        "allow_buy": 1,
        "allow_sell": 1,
        "universe_source": universe_source,
    }
    if universe_last_seen_at is not None:
        security_data["universe_last_seen_at"] = universe_last_seen_at
    if geography is None:
        security_data["geography"] = (existing or {}).get("geography") or ""
    else:
        security_data["geography"] = geography
    if industry is None:
        security_data["industry"] = (existing or {}).get("industry") or ""
    else:
        security_data["industry"] = industry

    await db.upsert_security(symbol, **security_data)
    if broker_info:
        await db.update_security_metadata(symbol, broker_info, market_id)

    prices_count = 0
    if fetch_prices:
        try:
            prices_data = await broker.get_historical_prices_bulk([symbol], years=20)
        except Exception as e:
            logger.warning("Historical price lookup failed for %s: %s", symbol, e)
            prices_data = {}
        prices = prices_data.get(symbol, []) if isinstance(prices_data, dict) else []
        if prices:
            await db.save_prices(symbol, prices)
            prices_count = len(prices)

    return SecurityImportResult(
        symbol=symbol,
        name=str(name),
        prices_count=prices_count,
        re_enabled=bool(existing and _as_int_flag(existing.get("active")) == 0),
    )


async def apply_removed_from_favorites_rule(db, symbol: str) -> dict[str, Any]:
    """Apply the safe local rule for a ticker absent from Freedom24 Favorites."""
    quantity = await _position_quantity(db, symbol)
    if quantity > 0:
        await db.upsert_security(
            symbol,
            active=1,
            allow_buy=0,
            allow_sell=1,
            universe_source=BROKER_POSITION_UNIVERSE_SOURCE,
        )
        return {
            "symbol": symbol,
            "active": True,
            "allow_buy": False,
            "allow_sell": True,
            "retained_position": True,
            "quantity": quantity,
        }

    await db.upsert_security(symbol, active=0, allow_buy=0, allow_sell=0)
    return {
        "symbol": symbol,
        "active": False,
        "allow_buy": False,
        "allow_sell": False,
        "retained_position": False,
        "quantity": 0.0,
    }


async def reconcile_universe_from_freedom24_default_list(db, broker) -> UniverseReconciliationResult:
    """Reconcile Sentinel's active universe against the Freedom24 default list."""
    result = UniverseReconciliationResult()
    payload = await broker.get_user_stock_lists()
    stock_list = _default_list_from_payload(payload)
    if stock_list is None:
        logger.warning("Skipping universe reconciliation: default Freedom24 list is unavailable")
        result.skipped.append("default_list")
        return result

    favorite_symbols = _tickers_from_default_list(stock_list)
    if not favorite_symbols:
        logger.warning("Skipping universe reconciliation: default Freedom24 list has no tickers")
        result.skipped.append("empty_default_list")
        return result

    now = utc_now_iso()
    active_securities = await db.get_all_securities(active_only=True)
    active_symbols = set()
    for security in active_securities:
        symbol = security.get("symbol")
        if isinstance(symbol, str):
            active_symbols.add(symbol)
    pending_update_count = len(favorite_symbols - active_symbols) + len(active_symbols - favorite_symbols)
    if active_symbols and pending_update_count * 2 > len(active_symbols):
        logger.warning(
            "Skipping universe reconciliation: %s pending changes for %s active securities exceeds 50%%",
            pending_update_count,
            len(active_symbols),
        )
        result.skipped.append("change_ratio_guard")
        return result

    for symbol in sorted(favorite_symbols):
        existing = await db.get_security(symbol)
        if not existing or _as_int_flag(existing.get("active")) == 0:
            imported = await import_security_from_broker(
                db,
                broker,
                symbol,
                universe_source=FREEDOM24_UNIVERSE_SOURCE,
                universe_last_seen_at=now,
            )
            if imported.re_enabled:
                result.reactivated.append(symbol)
            else:
                result.imported.append(symbol)
            continue

        source = existing.get("universe_source")
        if source == BROKER_POSITION_UNIVERSE_SOURCE:
            imported = await import_security_from_broker(
                db,
                broker,
                symbol,
                universe_source=FREEDOM24_UNIVERSE_SOURCE,
                universe_last_seen_at=now,
            )
            if _as_int_flag(existing.get("allow_buy"), default=1) == 0:
                result.buy_reenabled.append(symbol)
            else:
                result.provenance_updated.append(symbol)
            continue

        updates: dict[str, Any] = {}
        if source != FREEDOM24_UNIVERSE_SOURCE:
            updates["universe_source"] = FREEDOM24_UNIVERSE_SOURCE
        if existing.get("universe_last_seen_at") != now:
            updates["universe_last_seen_at"] = now
        if source == BROKER_POSITION_UNIVERSE_SOURCE and _as_int_flag(existing.get("allow_buy"), default=1) == 0:
            updates["allow_buy"] = 1
            updates["allow_sell"] = 1

        if updates:
            await db.upsert_security(symbol, **updates)
            if "allow_buy" in updates:
                result.buy_reenabled.append(symbol)
            else:
                result.provenance_updated.append(symbol)

    missing_from_favorites = []
    for security in active_securities:
        symbol = security.get("symbol")
        if not isinstance(symbol, str) or symbol in favorite_symbols:
            continue
        missing_from_favorites.append(security)

    for security in missing_from_favorites:
        symbol = security["symbol"]
        quantity = await _position_quantity(db, symbol)
        if quantity > 0:
            updates = {
                "active": 1,
                "allow_buy": 0,
                "allow_sell": 1,
                "universe_source": BROKER_POSITION_UNIVERSE_SOURCE,
            }
            material = _as_int_flag(security.get("allow_buy"), default=1) != 0
            await db.upsert_security(symbol, **updates)
            if material:
                result.buy_disabled.append(symbol)
            else:
                result.provenance_updated.append(symbol)
        else:
            await apply_removed_from_favorites_rule(db, symbol)
            result.removed.append(symbol)

    return result
