"""
Backtester - Simulate portfolio performance over historical periods.

Uses the ACTUAL Planner, Portfolio, and trading logic via dependency injection.
Runs in an isolated simulation environment without affecting the real database.

SAFETY: The real database is NEVER modified. All operations go to an in-memory copy.

Usage:
    config = BacktestConfig(
        start_date='2020-01-01',
        end_date='2024-12-31',
        initial_capital=10000,
        monthly_deposit=500,
        rebalance_frequency='weekly',
    )
    backtester = Backtester(config)
    async for progress in backtester.run():
        print(progress.current_date, progress.portfolio_value)
"""

import random
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional, cast

import numpy as np

from sentinel.broker import Broker
from sentinel.database import Database
from sentinel.database.simulation import SimulationDatabase
from sentinel.price_validator import PriceValidator


def _calculate_max_drawdown(values: np.ndarray) -> float:
    if len(values) == 0:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            dd = (peak - v) / peak
            max_dd = max(max_dd, dd)
    return float(max_dd)


def _calculate_sharpe(returns: np.ndarray) -> float:
    if len(returns) < 2:
        return 0.0
    vol = float(np.std(returns))
    if vol <= 1e-12:
        return 0.0
    return float((np.mean(returns) / vol) * np.sqrt(252))


class RebalanceFrequency:
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    initial_capital: float = 10000.0
    monthly_deposit: float = 0.0
    rebalance_frequency: str = "weekly"
    # Securities selection
    use_existing_universe: bool = True
    pick_random: bool = True
    random_count: int = 10
    symbols: list[str] = field(default_factory=list)

    def get_start_date(self) -> date:
        return datetime.strptime(self.start_date, "%Y-%m-%d").date()

    def get_end_date(self) -> date:
        return datetime.strptime(self.end_date, "%Y-%m-%d").date()


@dataclass
class BacktestProgress:
    """Progress update during backtest simulation."""

    current_date: str
    progress_pct: float
    portfolio_value: float
    status: str  # 'preparing', 'discovering', 'downloading', 'running', 'completed', 'error', 'cancelled'
    message: str = ""
    phase: str = ""  # 'prepare_db', 'discover_symbols', 'download_prices', 'simulate'
    current_item: str = ""  # Current symbol being processed
    items_done: int = 0
    items_total: int = 0


@dataclass
class PortfolioSnapshot:
    """Daily snapshot of portfolio state."""

    date: str
    total_value: float
    cash: float
    positions_value: float
    positions: dict


@dataclass
class SimulatedTrade:
    """A trade executed during simulation."""

    date: str
    symbol: str
    action: str
    quantity: int
    price: float
    value: float


@dataclass
class SecurityPerformance:
    """Performance breakdown for a single security."""

    symbol: str
    name: str
    total_invested: float
    total_sold: float
    final_value: float
    total_return: float
    return_pct: float
    num_buys: int
    num_sells: int


@dataclass
class BacktestResult:
    """Final results of a backtest run."""

    config: BacktestConfig
    snapshots: list[PortfolioSnapshot]
    trades: list[SimulatedTrade]
    initial_value: float
    final_value: float
    total_deposits: float
    total_return: float
    total_return_pct: float
    cagr: float
    max_drawdown: float
    sharpe_ratio: float
    security_performance: list[SecurityPerformance]
    memory_entry_count: int = 0
    opportunity_buy_count: int = 0


class BacktestDatabaseBuilder:
    """Creates and populates a temporary database for backtesting."""

    def __init__(self, config: BacktestConfig, real_db: Database):
        self.config = config
        self.real_db = real_db
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir) / "backtest.db"
        self.temp_db: Database | None = None
        self.broker = Broker()
        self._symbols: list[str] = []

    @property
    def symbols(self) -> list[str]:
        """Get the symbols that were loaded into the temp database."""
        return self._symbols

    async def build(self) -> AsyncGenerator[BacktestProgress, None]:
        """
        Build the temporary database, yielding progress updates.
        After completion, self.temp_db contains the ready database.
        """
        # Phase 1: Prepare database
        yield BacktestProgress(
            current_date="",
            progress_pct=0,
            portfolio_value=0,
            status="preparing",
            phase="prepare_db",
            message="Preparing database...",
        )

        # Create a fresh database at the temp path
        self.temp_db = Database(str(self.temp_path))
        await self.temp_db.connect()
        await self._copy_settings()

        # Phase 2: Discover symbols
        yield BacktestProgress(
            current_date="",
            progress_pct=0,
            portfolio_value=0,
            status="discovering",
            phase="discover_symbols",
            message="Discovering securities...",
        )
        self._symbols = await self._get_symbols()

        if not self._symbols:
            yield BacktestProgress(
                current_date="",
                progress_pct=0,
                portfolio_value=0,
                status="error",
                phase="discover_symbols",
                message="No securities found for backtest",
            )
            return

        # Phase 3: Download/copy prices for each symbol
        total = len(self._symbols)
        for i, symbol in enumerate(self._symbols):
            yield BacktestProgress(
                current_date="",
                progress_pct=(i / total) * 100,
                portfolio_value=0,
                status="downloading",
                phase="download_prices",
                message="Downloading historical data...",
                current_item=symbol,
                items_done=i,
                items_total=total,
            )
            await self._populate_symbol(symbol)

    async def _copy_settings(self) -> None:
        """Copy settings and allocation targets from real database."""
        assert self.temp_db is not None
        # Copy settings
        cursor = await self.real_db.conn.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        for row in rows:
            await self.temp_db.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (row["key"], row["value"])
            )

        # Copy allocation targets
        cursor = await self.real_db.conn.execute("SELECT type, name, weight FROM allocation_targets")
        rows = await cursor.fetchall()
        for row in rows:
            await self.temp_db.conn.execute(
                "INSERT OR REPLACE INTO allocation_targets (type, name, weight) VALUES (?, ?, ?)",
                (row["type"], row["name"], row["weight"]),
            )

        await self.temp_db.conn.commit()

    async def _get_symbols(self) -> list[str]:
        """Get list of symbols to use in backtest based on config."""
        if self.config.use_existing_universe:
            securities = await self.real_db.get_all_securities(active_only=True)
            return [s["symbol"] for s in securities]
        elif self.config.pick_random:
            # Fetch top EU securities from Tradernet API and pick random
            available = await self.broker.get_available_securities()
            if not available:
                return []
            count = min(self.config.random_count, len(available))
            return random.sample(available, count)
        else:
            return self.config.symbols or []

    async def _populate_symbol(self, symbol: str) -> None:
        """Populate symbol data in temp database (copy from real DB or fetch from API)."""
        # Check if real DB has this symbol's data
        existing_security = await self.real_db.get_security(symbol)
        existing_prices = await self.real_db.get_prices(symbol)

        if existing_security and existing_prices:
            # Copy security info and prices from real DB
            await self._copy_symbol_data(symbol, existing_security, existing_prices)
        else:
            # Fetch security info and prices from Tradernet API
            await self._fetch_symbol_data(symbol)

    async def _copy_symbol_data(self, symbol: str, security: dict, prices: list[dict]) -> None:
        """Copy security and price data from real database to temp database."""
        assert self.temp_db is not None
        # Insert security using only columns that exist in the temp DB schema.
        cursor = await self.temp_db.conn.execute("PRAGMA table_info(securities)")
        temp_cols = {row["name"] for row in await cursor.fetchall()}
        filtered = {k: v for k, v in security.items() if k in temp_cols}
        if "symbol" not in filtered:
            filtered["symbol"] = symbol

        cols = list(filtered.keys())
        placeholders = ",".join(["?" for _ in cols])
        cols_str = ",".join(cols)
        await self.temp_db.conn.execute(
            f"INSERT OR REPLACE INTO securities ({cols_str}) VALUES ({placeholders})",  # noqa: S608
            tuple(filtered.values()),
        )

        # Insert prices
        for price in prices:
            await self.temp_db.conn.execute(
                """INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    symbol,
                    price["date"],
                    price.get("open"),
                    price.get("high"),
                    price.get("low"),
                    price["close"],
                    price.get("volume"),
                ),
            )

        await self.temp_db.conn.commit()

    async def _fetch_symbol_data(self, symbol: str) -> None:
        """Fetch security and price data from Tradernet API."""
        assert self.temp_db is not None
        await self.broker.connect()

        # Fetch security info
        info = await self.broker.get_security_info(symbol)
        if info:
            name = info.get("short_name", info.get("name", symbol))
            currency = info.get("currency", info.get("curr", "EUR"))
            market_id = str(info.get("mrkt", {}).get("mkt_id", ""))
            min_lot = int(float(info.get("lot", 1)))

            await self.temp_db.upsert_security(
                symbol,
                name=name,
                currency=currency,
                market_id=market_id,
                min_lot=min_lot,
                active=True,
            )
        else:
            # Create minimal security entry
            await self.temp_db.upsert_security(symbol, name=symbol, currency="EUR", active=True)

        # Fetch historical prices (20 years; TraderNet getHloc has no documented max range)
        prices_data = await self.broker.get_historical_prices_bulk([symbol], years=20)
        prices = prices_data.get(symbol, [])
        if prices:
            for price in prices:
                await self.temp_db.conn.execute(
                    """INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        symbol,
                        price["date"],
                        price.get("open"),
                        price.get("high"),
                        price.get("low"),
                        price["close"],
                        price.get("volume"),
                    ),
                )
            await self.temp_db.conn.commit()

    async def cleanup(self) -> None:
        """Close and remove temporary database file and directory."""
        import shutil

        try:
            if self.temp_db:
                await self.temp_db.close()
                self.temp_db.remove_from_cache()
                self.temp_db = None
            if self.temp_path.exists():
                self.temp_path.unlink()
            if Path(self.temp_dir).exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:  # noqa: S110
            pass


class BacktestBroker:
    """
    Mock broker that returns historical prices from the simulation database.
    Implements the same interface as the real Broker class.

    IMPORTANT: Uses PriceValidator to validate/interpolate prices, matching
    what the production app does for price handling.
    """

    def __init__(self, sim_db: SimulationDatabase):
        self._db = sim_db
        self._simulation_date: str = ""
        # Cache validated prices per symbol: {symbol: {date: close_price}}
        self._validated_prices: dict[str, dict[str, float]] = {}
        self._price_validator = PriceValidator()

    def set_simulation_date(self, date_str: str):
        """Set the current simulation date for price lookups."""
        self._simulation_date = date_str

    @property
    def connected(self) -> bool:
        return True

    async def connect(self) -> bool:
        return True

    async def get_quote(self, symbol: str) -> Optional[dict]:
        price = await self._get_historical_price(symbol)
        if price is None:
            return None
        return {
            "symbol": symbol,
            "price": price,
            "bid": price,
            "ask": price,
            "change": 0,
            "change_percent": 0,
        }

    async def get_quotes(self, symbols: list[str]) -> dict[str, dict]:
        result = {}
        for symbol in symbols:
            quote = await self.get_quote(symbol)
            if quote:
                result[symbol] = quote
        return result

    async def _get_historical_price(self, symbol: str) -> Optional[float]:
        """
        Get historical price for the simulation date.

        Uses PriceValidator.validate_and_interpolate() to handle corrupted
        price data, exactly like the production app does.
        """
        # Lazily load and validate all prices for this symbol
        if symbol not in self._validated_prices:
            await self._load_and_validate_prices(symbol)

        prices = self._validated_prices.get(symbol, {})
        if not prices:
            return None

        # Return price for simulation date if exact match
        if self._simulation_date in prices:
            return prices[self._simulation_date]

        # Find most recent price on or before simulation date
        valid_dates = [d for d in prices.keys() if d <= self._simulation_date]
        if valid_dates:
            latest = max(valid_dates)
            return prices[latest]

        return None

    async def _load_and_validate_prices(self, symbol: str):
        """
        Load all prices for a symbol and run them through PriceValidator.

        This matches how the production app handles price data - it validates
        and interpolates corrupted prices before use.
        """
        cursor = await self._db.conn.execute(
            """SELECT date, open, high, low, close, volume
               FROM prices WHERE symbol = ?
               ORDER BY date ASC""",
            (symbol,),
        )
        rows = await cursor.fetchall()

        if not rows:
            self._validated_prices[symbol] = {}
            return

        # Convert to list of dicts (oldest first, as validator expects)
        raw_prices = [dict(row) for row in rows]

        # Validate and interpolate using the app's PriceValidator
        validated = self._price_validator.validate_and_interpolate(raw_prices)

        # Cache as date -> close price mapping
        self._validated_prices[symbol] = {p["date"]: p["close"] for p in validated if p.get("close")}

    async def get_portfolio(self) -> dict:
        """Return simulated portfolio state."""
        positions = await self._db.get_all_positions()
        cash = await self._db.get_cash_balances()

        # Update prices to historical values
        for pos in positions:
            price = await self._get_historical_price(pos["symbol"])
            if price:
                pos["current_price"] = price

        return {"positions": positions, "cash": cash}

    async def buy(self, symbol: str, quantity: int) -> Optional[str]:
        return f"BACKTEST-BUY-{symbol}-{quantity}"

    async def sell(self, symbol: str, quantity: int) -> Optional[str]:
        return f"BACKTEST-SELL-{symbol}-{quantity}"


class Backtester:
    """
    Main backtesting engine.

    Uses the ACTUAL Planner via dependency injection.
    The real database is NEVER modified.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self._cancelled = False
        self._sim_db: Optional[SimulationDatabase] = None
        self._sim_broker: Optional[BacktestBroker] = None
        self._simulation_date: str = ""
        self._planner = None
        self._portfolio = None
        self._currency = None

    def cancel(self):
        self._cancelled = True

    async def run(self) -> AsyncGenerator[BacktestProgress | BacktestResult, None]:
        """Run backtest using the ACTUAL Planner."""
        self._cancelled = False
        builder = None
        real_db = None
        opened_real_db_here = False

        try:
            real_db = Database()
            if getattr(real_db, "_connection", None) is None:
                await real_db.connect()
                opened_real_db_here = True

            # Phase 1-3: Build temporary database with required securities
            builder = BacktestDatabaseBuilder(self.config, real_db)
            self._builder = builder

            async for progress in builder.build():
                if self._cancelled:
                    yield BacktestProgress(
                        current_date="",
                        progress_pct=0,
                        portfolio_value=0,
                        status="cancelled",
                        message="Backtest cancelled",
                    )
                    return

                yield progress

                # Check if build had an error
                if progress.status == "error":
                    return

            # Phase 4: Initialize simulation environment from temp database
            self._sim_db = SimulationDatabase()
            await self._sim_db.initialize_from(builder.temp_db)

            self._sim_broker = BacktestBroker(self._sim_db)

            # Assert that db and broker are now initialized (for type checker)
            assert self._sim_db is not None
            assert self._sim_broker is not None

            from sentinel.currency import Currency
            from sentinel.planner import Planner
            from sentinel.portfolio import Portfolio

            self._currency = Currency()
            self._portfolio = Portfolio(db=self._sim_db, broker=self._sim_broker)
            self._planner = Planner(
                db=cast(Database, self._sim_db),
                broker=cast(Broker, self._sim_broker),
                portfolio=self._portfolio,
            )

            # Initialize cash
            await self._sim_db.set_cash_balance("EUR", self.config.initial_capital)

            start_date = self.config.get_start_date()
            end_date = self.config.get_end_date()

            snapshots: list[PortfolioSnapshot] = []
            trades: list[SimulatedTrade] = []
            total_deposits = self.config.initial_capital
            security_tracking: dict[str, dict] = {}
            memory_entry_count = 0
            opportunity_buy_count = 0

            total_days = (end_date - start_date).days
            days_processed = 0
            last_rebalance_date: Optional[date] = None
            last_month_deposited: Optional[int] = None

            current_date = start_date
            while current_date <= end_date:
                if self._cancelled:
                    yield BacktestProgress(
                        current_date=str(current_date),
                        progress_pct=(days_processed / total_days) * 100 if total_days > 0 else 0,
                        portfolio_value=await self._get_portfolio_value(),
                        status="cancelled",
                        phase="simulate",
                        message="Backtest cancelled",
                    )
                    return

                if current_date.weekday() >= 5:
                    current_date += timedelta(days=1)
                    days_processed += 1
                    continue

                self._simulation_date = str(current_date)
                self._sim_db.set_simulation_date(self._simulation_date)
                self._sim_broker.set_simulation_date(self._simulation_date)

                # Monthly deposit
                if self.config.monthly_deposit > 0:
                    if current_date.day == 1 and current_date.month != last_month_deposited:
                        cash = await self._sim_db.get_cash_balances()
                        await self._sim_db.set_cash_balance("EUR", cash.get("EUR", 0) + self.config.monthly_deposit)
                        total_deposits += self.config.monthly_deposit
                        last_month_deposited = current_date.month

                # Rebalance
                should_rebalance = self._should_rebalance(
                    current_date, last_rebalance_date, self.config.rebalance_frequency
                )

                if should_rebalance:
                    new_trades, memory_buys, opp_buys = await self._execute_rebalance(security_tracking)
                    trades.extend(new_trades)
                    memory_entry_count += memory_buys
                    opportunity_buy_count += opp_buys
                    last_rebalance_date = current_date

                # Update prices
                await self._update_position_prices()

                # Snapshot
                snapshot = await self._create_snapshot()
                snapshots.append(snapshot)

                if days_processed % 5 == 0:
                    yield BacktestProgress(
                        current_date=self._simulation_date,
                        progress_pct=(days_processed / total_days) * 100 if total_days > 0 else 0,
                        portfolio_value=snapshot.total_value,
                        status="running",
                        phase="simulate",
                        message="Running simulation...",
                    )

                current_date += timedelta(days=1)
                days_processed += 1

            result = self._calculate_results(
                snapshots,
                trades,
                total_deposits,
                security_tracking,
                memory_entry_count,
                opportunity_buy_count,
            )
            yield result

        except Exception as e:
            import traceback

            traceback.print_exc()
            yield BacktestProgress(
                current_date="",
                progress_pct=0,
                portfolio_value=0,
                status="error",
                message=str(e),
            )
        finally:
            if self._sim_db:
                await self._sim_db.close()
                self._sim_db = None
            self._planner = None
            self._portfolio = None
            self._currency = None
            if builder:
                await builder.cleanup()
            if real_db is not None and opened_real_db_here:
                await real_db.close()

    def _should_rebalance(self, current_date: date, last: Optional[date], freq: str) -> bool:
        if last is None:
            return True
        if freq == "daily":
            return True
        elif freq == "weekly":
            return current_date.weekday() == 0 and (current_date - last).days >= 5
        elif freq == "monthly":
            return current_date.month != last.month
        return False

    async def _is_in_cooloff(self, symbol: str, action: str, security_tracking: dict, cooloff_days: int) -> bool:
        """
        Check if security is in cool-off period during backtest.
        Uses trades table in simulation database with new schema.
        """
        assert self._sim_db is not None, "Simulation database not initialized"
        tracked = security_tracking.get(symbol) or {}
        last_action = tracked.get("last_action")
        last_date_raw = tracked.get("last_date")
        if last_action and last_date_raw:
            last_date = datetime.strptime(str(last_date_raw), "%Y-%m-%d").date()
        else:
            # Fallback for symbols not yet seen in tracking.
            trades = await self._sim_db.get_trades(symbol=symbol, limit=1)
            if not trades:
                return False  # No trade history
            last_trade = trades[0]
            last_action = last_trade["side"]
            executed_at = last_trade["executed_at"]
            if isinstance(executed_at, int):
                last_date = datetime.fromtimestamp(executed_at).date()
            else:
                last_date = datetime.fromisoformat(str(executed_at)[:10]).date()
        current_date = datetime.strptime(self._simulation_date, "%Y-%m-%d").date()
        days_since = (current_date - last_date).days

        # Check if opposite action within cool-off period
        if action == "buy" and last_action == "SELL" and days_since < cooloff_days:
            return True
        if action == "sell" and last_action == "BUY" and days_since < cooloff_days:
            return True

        return False

    async def _get_portfolio_value(self) -> float:
        """Get portfolio value using the Portfolio class."""
        from sentinel.portfolio import Portfolio

        portfolio = Portfolio(db=self._sim_db, broker=self._sim_broker)
        return await portfolio.total_value()

    async def _update_position_prices(self):
        """Update position prices to current simulation date."""
        assert self._sim_db is not None and self._sim_broker is not None
        positions = await self._sim_db.get_all_positions()
        for pos in positions:
            quote = await self._sim_broker.get_quote(pos["symbol"])
            if quote and quote.get("price"):
                await self._sim_db.upsert_position(pos["symbol"], current_price=quote["price"])

    async def _execute_rebalance(self, security_tracking: dict) -> tuple[list[SimulatedTrade], int, int]:
        """
        Execute rebalance using the ACTUAL Planner via dependency injection.

        Just like the real app, this:
        1. Gets recommendations from the Planner
        2. Executes the recommended trades
        """
        assert self._sim_db is not None and self._sim_broker is not None
        assert self._planner is not None and self._currency is not None
        trades = []
        memory_entry_count = 0
        opportunity_buy_count = 0

        # Get recommendations using the ACTUAL Planner logic (as_of_date = simulation date)
        recommendations = await self._planner.get_recommendations(as_of_date=self._simulation_date)

        # Get cool-off setting
        settings_data = await self._sim_db.conn.execute("SELECT value FROM settings WHERE key = 'trade_cooloff_days'")
        cooloff_setting = await settings_data.fetchone()
        cooloff_days = int(cooloff_setting["value"]) if cooloff_setting else 30

        # Execute each recommendation
        async with self._sim_db.deferred_writes():
            for rec in recommendations:
                if rec.action == "buy" and rec.sleeve == "opportunity":
                    opportunity_buy_count += 1
                    if rec.memory_entry:
                        memory_entry_count += 1
                # Check cool-off period
                if await self._is_in_cooloff(rec.symbol, rec.action, security_tracking, cooloff_days):
                    continue  # Skip this trade

                trade = await self._execute_trade(rec, security_tracking, self._currency)
                if trade:
                    trades.append(trade)

        return trades, memory_entry_count, opportunity_buy_count

    async def _execute_trade(self, rec, tracking: dict, currency) -> Optional[SimulatedTrade]:
        """Execute a trade recommendation in the simulation."""
        assert self._sim_db is not None
        symbol = rec.symbol
        action = rec.action
        quantity = rec.quantity
        price = rec.price
        sec_currency = rec.currency

        if quantity <= 0:
            return None

        # Get security info
        sec = await self._sim_db.get_security(symbol)
        sec_name = sec.get("name", symbol) if sec else symbol

        # Initialize tracking
        if symbol not in tracking:
            tracking[symbol] = {
                "name": sec_name,
                "total_invested": 0,
                "total_sold": 0,
                "num_buys": 0,
                "num_sells": 0,
                "last_action": None,
                "last_date": None,
            }

        cost_local = quantity * price
        cost_eur = await currency.to_eur(cost_local, sec_currency)

        if action == "buy":
            # Check cash
            cash = await self._sim_db.get_cash_balances()
            cash_eur = cash.get("EUR", 0)

            if cash_eur < cost_eur:
                return None

            # Deduct cash
            await self._sim_db.set_cash_balance("EUR", cash_eur - cost_eur)

            # Update position
            pos = await self._sim_db.get_position(symbol)
            if pos and pos.get("quantity", 0) > 0:
                old_qty = pos["quantity"]
                old_cost = pos.get("avg_cost") or price
                new_qty = old_qty + quantity
                new_avg = ((old_qty * old_cost) + (quantity * price)) / new_qty
                await self._sim_db.upsert_position(
                    symbol, quantity=new_qty, avg_cost=new_avg, current_price=price, currency=sec_currency
                )
            else:
                await self._sim_db.upsert_position(
                    symbol, quantity=quantity, avg_cost=price, current_price=price, currency=sec_currency
                )

            tracking[symbol]["total_invested"] += cost_eur
            tracking[symbol]["num_buys"] += 1

        elif action == "sell":
            pos = await self._sim_db.get_position(symbol)
            if not pos or pos.get("quantity", 0) < quantity:
                return None

            new_qty = pos["quantity"] - quantity
            await self._sim_db.upsert_position(symbol, quantity=new_qty, current_price=price)

            # Add proceeds
            cash = await self._sim_db.get_cash_balances()
            await self._sim_db.set_cash_balance("EUR", cash.get("EUR", 0) + cost_eur)

            tracking[symbol]["total_sold"] += cost_eur
            tracking[symbol]["num_sells"] += 1

        # Record trade in simulation database for cool-off tracking
        # Generate a unique broker_trade_id for the simulation
        import uuid

        broker_trade_id = f"BACKTEST-{uuid.uuid4().hex[:8]}"
        executed_at_ts = int(
            datetime.strptime(self._simulation_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )
        await self._sim_db.upsert_trade(
            broker_trade_id=broker_trade_id,
            symbol=symbol,
            side=action.upper(),
            quantity=quantity,
            price=price,
            executed_at=executed_at_ts,
            raw_data={
                "id": broker_trade_id,
                "symbol": symbol,
                "side": action.upper(),
                "qty": quantity,
                "price": price,
                "date": self._simulation_date,
                "simulated": True,
            },
        )
        tracking[symbol]["last_action"] = action.upper()
        tracking[symbol]["last_date"] = self._simulation_date

        return SimulatedTrade(
            date=self._simulation_date,
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=price,
            value=cost_eur,
        )

    async def _create_snapshot(self) -> PortfolioSnapshot:
        """Create snapshot using Portfolio class."""
        from sentinel.currency import Currency

        assert self._sim_db is not None
        currency = Currency()

        # Cash
        cash_balances = await self._sim_db.get_cash_balances()
        total_cash = 0.0
        for curr, amount in cash_balances.items():
            total_cash += await currency.to_eur(amount, curr)

        # Positions
        positions_data = await self._sim_db.get_all_positions()
        positions = {}
        positions_value = 0.0

        for pos in positions_data:
            price = pos.get("current_price", 0) or 0
            qty = pos.get("quantity", 0)
            pos_currency = pos.get("currency", "EUR")
            value_eur = await currency.to_eur(price * qty, pos_currency)
            positions_value += value_eur
            positions[pos["symbol"]] = {
                "quantity": qty,
                "price": price,
                "value": value_eur,
            }

        return PortfolioSnapshot(
            date=self._simulation_date,
            total_value=total_cash + positions_value,
            cash=total_cash,
            positions_value=positions_value,
            positions=positions,
        )

    def _calculate_results(
        self,
        snapshots: list[PortfolioSnapshot],
        trades: list[SimulatedTrade],
        total_deposits: float,
        security_tracking: dict,
        memory_entry_count: int = 0,
        opportunity_buy_count: int = 0,
    ) -> BacktestResult:
        """Calculate result metrics from portfolio value history."""
        if not snapshots:
            return BacktestResult(
                config=self.config,
                snapshots=[],
                trades=[],
                initial_value=self.config.initial_capital,
                final_value=self.config.initial_capital,
                total_deposits=total_deposits,
                total_return=0,
                total_return_pct=0,
                cagr=0,
                max_drawdown=0,
                sharpe_ratio=0,
                security_performance=[],
                memory_entry_count=memory_entry_count,
                opportunity_buy_count=opportunity_buy_count,
            )

        initial_value = snapshots[0].total_value
        final_value = snapshots[-1].total_value
        values = np.array([s.total_value for s in snapshots])

        total_return = final_value - total_deposits
        total_return_pct = (total_return / total_deposits) * 100 if total_deposits > 0 else 0

        years = (self.config.get_end_date() - self.config.get_start_date()).days / 365.25
        if years > 0 and total_deposits > 0 and final_value > 0:
            cagr = ((final_value / total_deposits) ** (1 / years) - 1) * 100
        else:
            cagr = 0

        max_drawdown = _calculate_max_drawdown(values) * 100

        if len(values) >= 2:
            returns = np.diff(values) / values[:-1]
            sharpe_ratio = _calculate_sharpe(returns)
        else:
            sharpe_ratio = 0

        # Security performance
        security_performance = []
        for symbol, tracking in security_tracking.items():
            final_pos = snapshots[-1].positions.get(symbol, {})
            final_value_sec = final_pos.get("value", 0)
            total_invested = tracking["total_invested"]
            total_sold = tracking["total_sold"]
            total_return_sec = final_value_sec + total_sold - total_invested
            return_pct = (total_return_sec / total_invested * 100) if total_invested > 0 else 0

            security_performance.append(
                SecurityPerformance(
                    symbol=symbol,
                    name=tracking["name"],
                    total_invested=total_invested,
                    total_sold=total_sold,
                    final_value=final_value_sec,
                    total_return=total_return_sec,
                    return_pct=return_pct,
                    num_buys=tracking["num_buys"],
                    num_sells=tracking["num_sells"],
                )
            )

        security_performance.sort(key=lambda x: x.total_return, reverse=True)

        return BacktestResult(
            config=self.config,
            snapshots=snapshots,
            trades=trades,
            initial_value=initial_value,
            final_value=final_value,
            total_deposits=total_deposits,
            total_return=total_return,
            total_return_pct=total_return_pct,
            cagr=cagr,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            security_performance=security_performance,
            memory_entry_count=memory_entry_count,
            opportunity_buy_count=opportunity_buy_count,
        )


# Global state for cancellation
_active_backtest: Optional[Backtester] = None


def get_active_backtest() -> Optional[Backtester]:
    global _active_backtest
    return _active_backtest


def set_active_backtest(backtest: Optional[Backtester]):
    global _active_backtest
    _active_backtest = backtest
