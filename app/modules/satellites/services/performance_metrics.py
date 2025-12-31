"""Performance metrics calculator for satellite buckets.

Calculates risk-adjusted performance metrics for evaluating satellite strategies:
- Sharpe ratio: Return per unit of total risk
- Sortino ratio: Return per unit of downside risk
- Max drawdown: Worst peak-to-trough decline
- Win rate: Percentage of profitable trades
- Profit factor: Gross profit / gross loss
- Calmar ratio: Return / max drawdown
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a satellite bucket."""

    bucket_id: str
    period_days: int

    # Returns
    total_return: float  # Total return over period (%)
    annualized_return: float  # Annualized return (%)

    # Risk metrics
    volatility: float  # Standard deviation of returns (%)
    downside_volatility: float  # Std dev of negative returns only (%)
    max_drawdown: float  # Maximum drawdown (%)

    # Risk-adjusted returns
    sharpe_ratio: float  # Return per unit of total risk
    sortino_ratio: float  # Return per unit of downside risk
    calmar_ratio: float  # Return per unit of max drawdown

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float  # % of profitable trades
    profit_factor: float  # Gross profit / gross loss

    # Additional metrics
    avg_win: float  # Average winning trade (%)
    avg_loss: float  # Average losing trade (%)
    largest_win: float  # Largest winning trade (%)
    largest_loss: float  # Largest losing trade (%)

    # Score for meta-allocator
    composite_score: float  # Weighted combination of metrics

    # Metadata
    start_date: str
    end_date: str
    calculated_at: str


def calculate_sharpe_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float:
    """Calculate Sharpe ratio.

    Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns

    Args:
        returns: List of period returns (as decimals, e.g., 0.05 for 5%)
        risk_free_rate: Annual risk-free rate (default 0)

    Returns:
        Sharpe ratio (higher is better)
    """
    if not returns or len(returns) < 2:
        return 0.0

    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)

    if std_return == 0:
        return 0.0

    # Adjust risk-free rate to period
    period_rf = risk_free_rate / 252  # Assuming daily returns

    sharpe = (mean_return - period_rf) / std_return

    return float(sharpe)


def calculate_sortino_ratio(
    returns: list[float], risk_free_rate: float = 0.0, target_return: float = 0.0
) -> float:
    """Calculate Sortino ratio.

    Sortino = (Mean Return - Target) / Downside Deviation

    Only penalizes downside volatility, not upside.

    Args:
        returns: List of period returns
        risk_free_rate: Annual risk-free rate
        target_return: Minimum acceptable return (default 0)

    Returns:
        Sortino ratio (higher is better)
    """
    if not returns or len(returns) < 2:
        return 0.0

    mean_return = np.mean(returns)

    # Calculate downside deviation (only negative returns)
    downside_returns = [r - target_return for r in returns if r < target_return]

    if not downside_returns:
        return float("inf")  # No downside = infinite Sortino

    downside_std = np.std(downside_returns, ddof=1)

    if downside_std == 0:
        return 0.0

    sortino = (mean_return - target_return) / downside_std

    return float(sortino)


def calculate_max_drawdown(equity_curve: list[float]) -> tuple[float, int, int]:
    """Calculate maximum drawdown from equity curve.

    Args:
        equity_curve: List of portfolio values over time

    Returns:
        Tuple of (max_drawdown_pct, peak_idx, trough_idx)
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0, 0, 0

    equity = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max

    max_dd_idx = int(np.argmin(drawdown))
    max_dd = abs(float(drawdown[max_dd_idx]))

    # Find peak before this trough
    peak_idx = int(np.argmax(equity[: max_dd_idx + 1]))

    return max_dd, peak_idx, max_dd_idx


def calculate_calmar_ratio(annualized_return: float, max_drawdown: float) -> float:
    """Calculate Calmar ratio.

    Calmar = Annualized Return / Max Drawdown

    Args:
        annualized_return: Annual return (%)
        max_drawdown: Maximum drawdown (%)

    Returns:
        Calmar ratio (higher is better)
    """
    if max_drawdown == 0:
        return 0.0

    return annualized_return / max_drawdown


def calculate_win_rate(trades: list[dict]) -> tuple[float, int, int]:
    """Calculate win rate from trade history.

    Args:
        trades: List of trade dicts with 'profit_loss' or 'pnl' field

    Returns:
        Tuple of (win_rate, winning_count, losing_count)
    """
    if not trades:
        return 0.0, 0, 0

    winning = sum(1 for t in trades if t.get("profit_loss", 0) > 0)
    losing = sum(1 for t in trades if t.get("profit_loss", 0) < 0)

    total = winning + losing
    win_rate = (winning / total * 100) if total > 0 else 0.0

    return win_rate, winning, losing


def calculate_profit_factor(trades: list[dict]) -> float:
    """Calculate profit factor.

    Profit Factor = Gross Profit / Gross Loss

    Args:
        trades: List of trade dicts with 'profit_loss' field

    Returns:
        Profit factor (>1 is profitable, higher is better)
    """
    if not trades:
        return 0.0

    gross_profit = sum(
        t.get("profit_loss", 0) for t in trades if t.get("profit_loss", 0) > 0
    )
    gross_loss = abs(
        sum(t.get("profit_loss", 0) for t in trades if t.get("profit_loss", 0) < 0)
    )

    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


async def calculate_bucket_performance(
    bucket_id: str,
    period_days: int = 90,
    risk_free_rate: float = 0.03,
) -> Optional[PerformanceMetrics]:
    """Calculate comprehensive performance metrics for a bucket.

    Args:
        bucket_id: Bucket ID
        period_days: Evaluation period in days (default 90 for quarterly)
        risk_free_rate: Annual risk-free rate (default 3%)

    Returns:
        PerformanceMetrics object or None if insufficient data
    """
    from app.modules.satellites.services.balance_service import BalanceService
    from app.repositories import TradeRepository

    balance_service = BalanceService()
    trade_repo = TradeRepository()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)

    # Get transaction history to build equity curve
    # Using trade history for performance calculations

    # Get all trades for this bucket in the period
    all_trades = await trade_repo.get_all()
    bucket_trades = [
        t
        for t in all_trades
        if getattr(t, "bucket_id", "core") == bucket_id
        and t.executed_at
        and start_date <= datetime.fromisoformat(t.executed_at) <= end_date
    ]

    if len(bucket_trades) < 5:
        logger.info(
            f"Insufficient trade history for {bucket_id} "
            f"({len(bucket_trades)} trades in {period_days} days)"
        )
        return None

    # Calculate trade-level metrics
    trade_pnls = []
    for trade in bucket_trades:
        if hasattr(trade, "realized_pnl") and trade.realized_pnl is not None:
            trade_pnls.append(
                {
                    "profit_loss": trade.realized_pnl,
                    "executed_at": trade.executed_at,
                }
            )

    if not trade_pnls:
        logger.info(f"No realized P&L data for {bucket_id}")
        return None

    # Win rate and profit factor
    win_rate, winning_trades, losing_trades = calculate_win_rate(trade_pnls)
    profit_factor = calculate_profit_factor(trade_pnls)

    # Calculate returns
    profits = [t["profit_loss"] for t in trade_pnls if t["profit_loss"] > 0]
    losses = [t["profit_loss"] for t in trade_pnls if t["profit_loss"] < 0]

    avg_win = np.mean(profits) if profits else 0.0
    avg_loss = np.mean(losses) if losses else 0.0
    largest_win = max(profits) if profits else 0.0
    largest_loss = min(losses) if losses else 0.0

    # Total return (simplified - sum of P&L)
    total_pnl = sum(t["profit_loss"] for t in trade_pnls)

    # Get current bucket value for return calculation
    balances = await balance_service.get_all_balances(bucket_id)
    current_value = sum(b.balance for b in balances if b.currency == "EUR")

    # Estimate starting value
    starting_value = current_value - total_pnl
    if starting_value <= 0:
        starting_value = current_value  # Fallback

    total_return_pct = (total_pnl / starting_value * 100) if starting_value > 0 else 0

    # Annualize return
    annualized_return = ((1 + total_return_pct / 100) ** (365 / period_days) - 1) * 100

    # Calculate volatility (simplified - use trade returns)
    trade_returns = [t["profit_loss"] / starting_value for t in trade_pnls]
    volatility = (
        float(np.std(trade_returns, ddof=1) * 100) if len(trade_returns) > 1 else 0.0
    )

    downside_returns = [r for r in trade_returns if r < 0]
    downside_volatility = (
        float(np.std(downside_returns, ddof=1) * 100)
        if len(downside_returns) > 1
        else 0.0
    )

    # Sharpe and Sortino ratios
    sharpe = calculate_sharpe_ratio(trade_returns, risk_free_rate)
    sortino = calculate_sortino_ratio(trade_returns, risk_free_rate)

    # Max drawdown (simplified - use cumulative P&L)
    cumulative_pnl = np.cumsum([t["profit_loss"] for t in trade_pnls])
    equity_curve = starting_value + cumulative_pnl
    max_dd, _, _ = calculate_max_drawdown(equity_curve.tolist())
    max_dd_pct = max_dd * 100

    # Calmar ratio
    calmar = calculate_calmar_ratio(annualized_return, max_dd_pct)

    # Composite score (weighted average for meta-allocator)
    # Higher is better
    composite_score = (
        0.3 * sharpe
        + 0.3 * sortino
        + 0.2 * (profit_factor - 1)  # Normalize to 0+
        + 0.1 * (win_rate / 100)  # Normalize to 0-1
        + 0.1 * calmar
    )

    return PerformanceMetrics(
        bucket_id=bucket_id,
        period_days=period_days,
        total_return=total_return_pct,
        annualized_return=annualized_return,
        volatility=volatility,
        downside_volatility=downside_volatility,
        max_drawdown=max_dd_pct,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        total_trades=len(bucket_trades),
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_win=float(avg_win),
        avg_loss=float(avg_loss),
        largest_win=float(largest_win),
        largest_loss=float(largest_loss),
        composite_score=composite_score,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        calculated_at=datetime.now().isoformat(),
    )
