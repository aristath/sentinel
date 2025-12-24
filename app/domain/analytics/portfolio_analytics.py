"""
Portfolio Analytics - PyFolio integration for performance analysis.

Reconstructs portfolio history from trades and generates comprehensive
performance metrics using PyFolio.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import empyrical

from app.infrastructure.database import get_db_manager
from app.repositories import TradeRepository, CashFlowRepository, StockRepository, HistoryRepository
from app.domain.models import Trade, CashFlow

logger = logging.getLogger(__name__)


async def reconstruct_historical_positions(
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    Reconstruct historical position quantities by date from trades.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        DataFrame with columns: date, symbol, quantity
    """
    trade_repo = TradeRepository()
    position_history = await trade_repo.get_position_history(start_date, end_date)
    
    if not position_history:
        return pd.DataFrame(columns=["date", "symbol", "quantity"])
    
    df = pd.DataFrame(position_history)
    df["date"] = pd.to_datetime(df["date"])
    return df


async def reconstruct_cash_balance(
    start_date: str,
    end_date: str,
    initial_cash: float = 0.0
) -> pd.Series:
    """
    Reconstruct cash balance over time from cash flows and trades.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        initial_cash: Starting cash balance
    
    Returns:
        Series with date index and cash balance values
    """
    cash_flow_repo = CashFlowRepository()
    trade_repo = TradeRepository()
    
    # Get cash flows (deposits, withdrawals, dividends, fees)
    cash_flows = await cash_flow_repo.get_by_date_range(start_date, end_date)
    
    # Get trades to account for trade values
    trades = await trade_repo.get_all_in_range(start_date, end_date)
    
    # Combine all transactions by date
    transactions_by_date = {}  # {date: net_change}
    
    # Add cash flows
    for cf in cash_flows:
        date = cf.date
        amount = cf.amount_eur or 0.0
        tx_type = (cf.transaction_type or "").upper()
        
        if date not in transactions_by_date:
            transactions_by_date[date] = 0.0
        
        if "DEPOSIT" in tx_type:
            transactions_by_date[date] += amount
        elif "WITHDRAWAL" in tx_type:
            transactions_by_date[date] -= abs(amount)
        elif "DIVIDEND" in tx_type:
            transactions_by_date[date] += amount
        # Fees are already negative in amount_eur
    
    # Add trades (BUY reduces cash, SELL increases cash)
    for trade in trades:
        if not trade.executed_at:
            continue
        
        trade_date = trade.executed_at.strftime("%Y-%m-%d") if isinstance(trade.executed_at, datetime) else str(trade.executed_at)[:10]
        
        if trade_date < start_date or trade_date > end_date:
            continue
        
        if trade_date not in transactions_by_date:
            transactions_by_date[trade_date] = 0.0
        
        # Trade value in EUR
        if trade.value_eur is not None:
            trade_value = trade.value_eur
        else:
            # Calculate from quantity * price * exchange rate
            exchange_rate = trade.currency_rate if trade.currency_rate else 1.0
            trade_value = trade.quantity * trade.price * exchange_rate
        
        if trade.side.upper() == "BUY":
            # BUY reduces cash
            transactions_by_date[trade_date] -= trade_value
        elif trade.side.upper() == "SELL":
            # SELL increases cash
            transactions_by_date[trade_date] += trade_value
    
    # Build cash balance series
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    cash_series = pd.Series(0.0, index=dates)
    
    current_cash = initial_cash
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        
        # Apply transaction for this date
        if date_str in transactions_by_date:
            current_cash += transactions_by_date[date_str]
        
        cash_series[date] = current_cash
    
    return cash_series


async def reconstruct_portfolio_values(
    start_date: str,
    end_date: str,
    initial_cash: float = 0.0
) -> pd.Series:
    """
    Reconstruct daily portfolio values from positions + prices + cash.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        initial_cash: Starting cash balance
    
    Returns:
        Series with date index and portfolio values
    """
    # Get position history
    positions_df = await reconstruct_historical_positions(start_date, end_date)
    
    # Get cash balance history
    cash_series = await reconstruct_cash_balance(start_date, end_date, initial_cash)
    
    # Get all unique dates
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    portfolio_values = pd.Series(0.0, index=dates)
    
    db_manager = get_db_manager()
    stock_repo = StockRepository()
    
    # Get all symbols that had positions
    symbols = positions_df["symbol"].unique() if not positions_df.empty else []
    
    # For each date, calculate portfolio value
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        total_value = cash_series.get(date, initial_cash)
        
        # Get positions on this date
        date_positions = positions_df[positions_df["date"] <= date]
        if not date_positions.empty:
            # Group by symbol and get latest quantity for each
            latest_positions = date_positions.groupby("symbol").last()
            
            for symbol, row in latest_positions.iterrows():
                quantity = row["quantity"]
                if quantity <= 0:
                    continue
                
                # Get price for this symbol on this date
                try:
                    history_repo = HistoryRepository(symbol)
                    price_data = await history_repo.get_daily_range(date_str, date_str)
                    
                    if price_data:
                        price = price_data[0].close_price
                        total_value += quantity * price
                except Exception as e:
                    logger.debug(f"Could not get price for {symbol} on {date_str}: {e}")
        
        portfolio_values[date] = total_value
    
    return portfolio_values


def calculate_portfolio_returns(portfolio_values: pd.Series) -> pd.Series:
    """
    Calculate daily returns from portfolio values.
    
    Args:
        portfolio_values: Series with date index and portfolio values
    
    Returns:
        Series with date index and daily returns (PyFolio format)
    """
    if len(portfolio_values) < 2:
        return pd.Series(dtype=float)
    
    returns = portfolio_values.pct_change().dropna()
    returns.index = pd.to_datetime(returns.index)
    return returns


async def get_portfolio_metrics(
    returns: pd.Series,
    benchmark: Optional[pd.Series] = None,
    risk_free_rate: float = 0.0
) -> Dict[str, float]:
    """
    Calculate comprehensive portfolio metrics using PyFolio.
    
    Args:
        returns: Daily returns series
        benchmark: Optional benchmark returns for comparison
        risk_free_rate: Risk-free rate (default 0.0)
    
    Returns:
        Dict with metrics: annual_return, volatility, sharpe_ratio, sortino_ratio,
        calmar_ratio, max_drawdown, etc.
    """
    if returns.empty or len(returns) < 2:
        return {
            "annual_return": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown": 0.0,
        }
    
    try:
        # Calculate metrics using empyrical (used by PyFolio)
        annual_return = float(empyrical.annual_return(returns))
        volatility = float(empyrical.annual_volatility(returns))
        sharpe_ratio = float(empyrical.sharpe_ratio(returns, risk_free=risk_free_rate))
        sortino_ratio = float(empyrical.sortino_ratio(returns, risk_free=risk_free_rate))
        max_drawdown = float(empyrical.max_drawdown(returns))
        
        # Calmar ratio = annual return / abs(max drawdown)
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0.0
        
        return {
            "annual_return": annual_return if np.isfinite(annual_return) else 0.0,
            "volatility": volatility if np.isfinite(volatility) else 0.0,
            "sharpe_ratio": sharpe_ratio if np.isfinite(sharpe_ratio) else 0.0,
            "sortino_ratio": sortino_ratio if np.isfinite(sortino_ratio) else 0.0,
            "calmar_ratio": calmar_ratio if np.isfinite(calmar_ratio) else 0.0,
            "max_drawdown": max_drawdown if np.isfinite(max_drawdown) else 0.0,
        }
    except Exception as e:
        logger.error(f"Error calculating portfolio metrics: {e}")
        return {
            "annual_return": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown": 0.0,
        }


async def get_performance_attribution(
    returns: pd.Series,
    start_date: str,
    end_date: str
) -> Dict[str, Dict[str, float]]:
    """
    Calculate performance attribution by geography and industry.
    
    Args:
        returns: Daily portfolio returns
        start_date: Start date for analysis
        end_date: End date for analysis
    
    Returns:
        Dict with 'geography' and 'industry' keys, each containing
        attribution by category (e.g., {'EU': 0.08, 'ASIA': 0.15})
    """
    if returns.empty:
        return {"geography": {}, "industry": {}}
    
    # Get position history
    positions_df = await reconstruct_historical_positions(start_date, end_date)
    
    if positions_df.empty:
        return {"geography": {}, "industry": {}}
    
    # Get stock info for geography/industry
    stock_repo = StockRepository()
    stocks = await stock_repo.get_all()
    stock_info = {s.symbol: {"geography": s.geography, "industry": s.industry} for s in stocks}
    
    # Calculate returns by geography and industry
    # Only process dates where we have returns data (more efficient)
    geo_returns = {}
    industry_returns = {}
    
    # Get unique dates from returns (only trading days)
    return_dates = returns.index.tolist()
    
    for date in return_dates:
        date_str = date.strftime("%Y-%m-%d")
        
        # Get positions on this date
        date_positions = positions_df[positions_df["date"] <= date]
        if date_positions.empty:
            continue
        
        latest_positions = date_positions.groupby("symbol").last()
        
        # Calculate position values and weights
        total_value = 0.0
        position_values = {}
        
        for symbol, row in latest_positions.iterrows():
            quantity = row["quantity"]
            if quantity <= 0:
                continue
            
            info = stock_info.get(symbol, {})
            geography = info.get("geography", "UNKNOWN")
            industry = info.get("industry")
            
            # Get price
            try:
                history_repo = HistoryRepository(symbol)
                price_data = await history_repo.get_daily_range(date_str, date_str)
                
                if price_data:
                    price = price_data[0].close_price
                    value = quantity * price
                    total_value += value
                    position_values[symbol] = {
                        "value": value,
                        "geography": geography,
                        "industry": industry
                    }
            except Exception:
                continue
        
        if total_value == 0:
            continue
        
        # Get return for this date
        daily_return = returns[date]
        
        # Attribute return by geography/industry
        for symbol, data in position_values.items():
            weight = data["value"] / total_value
            geo = data["geography"]
            ind = data["industry"]
            
            contribution = daily_return * weight
            
            if geo not in geo_returns:
                geo_returns[geo] = []
            geo_returns[geo].append(contribution)
            
            if ind:
                if ind not in industry_returns:
                    industry_returns[ind] = []
                industry_returns[ind].append(contribution)
    
    # Calculate average returns (annualized)
    attribution = {
        "geography": {},
        "industry": {}
    }
    
    for geo, contributions in geo_returns.items():
        if contributions:
            total_return = sum(contributions)
            # Annualize (assuming 252 trading days)
            annualized = total_return * (252 / len(contributions)) if contributions else 0.0
            attribution["geography"][geo] = float(annualized) if np.isfinite(annualized) else 0.0
    
    for ind, contributions in industry_returns.items():
        if contributions:
            total_return = sum(contributions)
            annualized = total_return * (252 / len(contributions)) if contributions else 0.0
            attribution["industry"][ind] = float(annualized) if np.isfinite(annualized) else 0.0
    
    return attribution


async def get_position_risk_metrics(
    symbol: str,
    start_date: str,
    end_date: str
) -> Dict[str, float]:
    """
    Calculate risk metrics for a specific position.
    
    Args:
        symbol: Stock symbol
        start_date: Start date for analysis
        end_date: End date for analysis
    
    Returns:
        Dict with sortino_ratio, sharpe_ratio, volatility, max_drawdown
    """
    try:
        history_repo = HistoryRepository(symbol)
        prices = await history_repo.get_daily_range(start_date, end_date)
        
        if len(prices) < 2:
            return {
                "sortino_ratio": 0.0,
                "sharpe_ratio": 0.0,
                "volatility": 0.0,
                "max_drawdown": 0.0,
            }
        
        # Calculate returns
        closes = [p.close_price for p in prices]
        returns = pd.Series(closes).pct_change().dropna()
        
        if returns.empty:
            return {
                "sortino_ratio": 0.0,
                "sharpe_ratio": 0.0,
                "volatility": 0.0,
                "max_drawdown": 0.0,
            }
        
        # Calculate metrics
        volatility = float(empyrical.annual_volatility(returns))
        sharpe_ratio = float(empyrical.sharpe_ratio(returns))
        sortino_ratio = float(empyrical.sortino_ratio(returns))
        max_drawdown = float(empyrical.max_drawdown(returns))
        
        return {
            "sortino_ratio": sortino_ratio if np.isfinite(sortino_ratio) else 0.0,
            "sharpe_ratio": sharpe_ratio if np.isfinite(sharpe_ratio) else 0.0,
            "volatility": volatility if np.isfinite(volatility) else 0.0,
            "max_drawdown": max_drawdown if np.isfinite(max_drawdown) else 0.0,
        }
    except Exception as e:
        logger.debug(f"Error calculating risk metrics for {symbol}: {e}")
        return {
            "sortino_ratio": 0.0,
            "sharpe_ratio": 0.0,
            "volatility": 0.0,
            "max_drawdown": 0.0,
        }


async def get_position_drawdown(
    symbol: str,
    start_date: str,
    end_date: str
) -> Dict[str, Optional[float]]:
    """
    Analyze drawdown periods for a specific position.
    
    Args:
        symbol: Stock symbol
        start_date: Start date for analysis
        end_date: End date for analysis
    
    Returns:
        Dict with max_drawdown, current_drawdown, days_in_drawdown, recovery_date
    """
    try:
        history_repo = HistoryRepository(symbol)
        prices = await history_repo.get_daily_range(start_date, end_date)
        
        if len(prices) < 2:
            return {
                "max_drawdown": None,
                "current_drawdown": None,
                "days_in_drawdown": None,
                "recovery_date": None,
            }
        
        # Calculate returns and drawdowns
        closes = pd.Series([p.close_price for p in prices], index=[pd.to_datetime(p.date) for p in prices])
        returns = closes.pct_change().dropna()
        
        # Calculate cumulative returns
        cumulative = (1 + returns).cumprod()
        
        # Calculate running maximum
        running_max = cumulative.expanding().max()
        
        # Calculate drawdown
        drawdown = (cumulative - running_max) / running_max
        
        max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0
        current_drawdown = float(drawdown.iloc[-1]) if not drawdown.empty else 0.0
        
        # Calculate days in current drawdown
        days_in_drawdown = None
        recovery_date = None
        
        if current_drawdown < 0:
            # Find when drawdown started
            drawdown_start_idx = None
            for i in range(len(drawdown) - 1, -1, -1):
                if drawdown.iloc[i] >= 0:
                    drawdown_start_idx = i + 1
                    break
            
            if drawdown_start_idx is not None:
                days_in_drawdown = len(drawdown) - drawdown_start_idx
            else:
                days_in_drawdown = len(drawdown)
        
        return {
            "max_drawdown": max_drawdown if np.isfinite(max_drawdown) else None,
            "current_drawdown": current_drawdown if np.isfinite(current_drawdown) else None,
            "days_in_drawdown": days_in_drawdown,
            "recovery_date": recovery_date,
        }
    except Exception as e:
        logger.debug(f"Error calculating drawdown for {symbol}: {e}")
        return {
            "max_drawdown": None,
            "current_drawdown": None,
            "days_in_drawdown": None,
            "recovery_date": None,
        }


async def get_factor_attribution(
    returns: pd.Series,
    start_date: str,
    end_date: str
) -> Dict[str, float]:
    """
    Analyze which factors (dividends, geography, industry) contributed most to returns.
    
    Args:
        returns: Daily portfolio returns
        start_date: Start date for analysis
        end_date: End date for analysis
    
    Returns:
        Dict with factor contributions (e.g., dividend_contribution, geography_contribution)
    """
    # This is a simplified version - full factor attribution would require
    # more sophisticated analysis. For now, we'll use performance attribution
    # to infer factor contributions.
    
    attribution = await get_performance_attribution(returns, start_date, end_date)
    
    # Calculate total portfolio return
    if returns.empty:
        total_return = 0.0
    else:
        total_return = float(empyrical.annual_return(returns))
    
    # Calculate contributions
    factor_attribution = {
        "dividend_contribution": 0.0,  # Would need dividend data to calculate
        "geography_contribution": sum(attribution["geography"].values()) if attribution["geography"] else 0.0,
        "industry_contribution": sum(attribution["industry"].values()) if attribution["industry"] else 0.0,
        "total_return": total_return,
    }
    
    return factor_attribution

