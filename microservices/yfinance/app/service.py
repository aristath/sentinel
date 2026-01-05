"""Core Yahoo Finance service wrapping yfinance library."""

import logging
from typing import Dict, List, Optional

import yfinance as yf

from app.models import (
    AnalystData,
    FundamentalData,
    HistoricalPrice,
    SecurityInfo,
)

logger = logging.getLogger(__name__)


class YahooFinanceService:
    """Service wrapping yfinance library."""

    def _convert_symbol(self, symbol: str, yahoo_override: Optional[str] = None) -> str:
        """Convert Tradernet symbol to Yahoo symbol.

        Args:
            symbol: Tradernet format symbol (e.g., "AAPL.US")
            yahoo_override: Optional explicit Yahoo symbol override

        Returns:
            Yahoo Finance symbol (e.g., "AAPL")
        """
        if yahoo_override:
            return yahoo_override

        # Convert Tradernet format to Yahoo format
        if symbol.endswith(".US"):
            return symbol[:-3]  # Remove .US
        if symbol.endswith(".JP"):
            base = symbol[:-3]
            return f"{base}.T"  # Japanese stocks use .T

        return symbol  # European stocks use as-is

    def get_current_price(
        self, symbol: str, yahoo_symbol: Optional[str] = None
    ) -> Optional[float]:
        """Get current price for a symbol.

        Args:
            symbol: Tradernet format symbol
            yahoo_symbol: Optional explicit Yahoo symbol override

        Returns:
            Current price or None if unavailable
        """
        try:
            yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            return float(price) if price else None
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
            return None

    def get_batch_quotes(
        self,
        symbols: List[str],
        yahoo_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        """Get current prices for multiple symbols efficiently.

        Args:
            symbols: List of Tradernet format symbols
            yahoo_overrides: Optional dict mapping symbol to Yahoo symbol override

        Returns:
            Dict mapping Tradernet symbol to current price
        """
        if yahoo_overrides is None:
            yahoo_overrides = {}

        # Convert symbols
        yf_symbols = []
        symbol_map = {}  # yf_symbol -> tradernet_symbol

        for symbol in symbols:
            yf_symbol = self._convert_symbol(
                symbol, yahoo_overrides.get(symbol)
            )
            yf_symbols.append(yf_symbol)
            symbol_map[yf_symbol] = symbol

        try:
            # Use yfinance download for batch efficiency
            # Use period="5d" to handle markets with different trading schedules
            data = yf.download(
                tickers=" ".join(yf_symbols),
                period="5d",
                progress=False,
                threads=True,
                auto_adjust=True,
            )

            result = {}
            if data.empty:
                return result

            # Handle single vs multiple symbols
            if len(yf_symbols) == 1:
                yf_symbol = yf_symbols[0]
                tradernet_symbol = symbol_map[yf_symbol]
                # Get last non-NaN value
                close_series = data["Close"].dropna()
                if len(close_series) > 0:
                    result[tradernet_symbol] = float(close_series.iloc[-1].item())
            else:
                for yf_symbol in yf_symbols:
                    tradernet_symbol = symbol_map[yf_symbol]
                    if yf_symbol in data["Close"].columns:
                        # Get last non-NaN value for this symbol
                        close_series = data["Close"][yf_symbol].dropna()
                        if len(close_series) > 0:
                            result[tradernet_symbol] = float(close_series.iloc[-1].item())

            return result
        except Exception as e:
            logger.error(f"Failed to get batch quotes: {e}")
            return {}

    def get_historical_prices(
        self,
        symbol: str,
        yahoo_symbol: Optional[str] = None,
        period: str = "1y",
        interval: str = "1d",
    ) -> List[HistoricalPrice]:
        """Get historical OHLCV data.

        Args:
            symbol: Tradernet format symbol
            yahoo_symbol: Optional explicit Yahoo symbol override
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1d, 1wk, 1mo)

        Returns:
            List of HistoricalPrice objects
        """
        try:
            yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period=period, interval=interval)

            result = []
            for date, row in hist.iterrows():
                result.append(
                    HistoricalPrice(
                        date=date.to_pydatetime(),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=int(row["Volume"]),
                        adj_close=float(row.get("Adj Close", row["Close"])),
                    )
                )

            return result
        except Exception as e:
            logger.error(f"Failed to get historical prices for {symbol}: {e}")
            return []

    def get_fundamental_data(
        self, symbol: str, yahoo_symbol: Optional[str] = None
    ) -> Optional[FundamentalData]:
        """Get fundamental analysis data.

        Args:
            symbol: Tradernet format symbol
            yahoo_symbol: Optional explicit Yahoo symbol override

        Returns:
            FundamentalData or None if unavailable
        """
        try:
            yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            return FundamentalData(
                symbol=symbol,
                pe_ratio=info.get("trailingPE"),
                forward_pe=info.get("forwardPE"),
                peg_ratio=info.get("pegRatio"),
                price_to_book=info.get("priceToBook"),
                revenue_growth=info.get("revenueGrowth"),
                earnings_growth=info.get("earningsGrowth"),
                profit_margin=info.get("profitMargins"),
                operating_margin=info.get("operatingMargins"),
                roe=info.get("returnOnEquity"),
                debt_to_equity=info.get("debtToEquity"),
                current_ratio=info.get("currentRatio"),
                market_cap=info.get("marketCap"),
                dividend_yield=info.get("dividendYield"),
                five_year_avg_dividend_yield=info.get("fiveYearAvgDividendYield"),
            )
        except Exception as e:
            logger.error(f"Failed to get fundamental data for {symbol}: {e}")
            return None

    def get_analyst_data(
        self, symbol: str, yahoo_symbol: Optional[str] = None
    ) -> Optional[AnalystData]:
        """Get analyst recommendations and price targets.

        Args:
            symbol: Tradernet format symbol
            yahoo_symbol: Optional explicit Yahoo symbol override

        Returns:
            AnalystData or None if unavailable
        """
        try:
            yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            recommendation = info.get("recommendationKey", "hold")
            target_price = info.get("targetMeanPrice", 0) or 0
            current_price = (
                info.get("currentPrice") or info.get("regularMarketPrice", 0) or 0
            )

            upside_pct = 0.0
            if current_price > 0 and target_price > 0:
                upside_pct = ((target_price - current_price) / current_price) * 100

            num_analysts = info.get("numberOfAnalystOpinions", 0) or 0

            rec_scores = {
                "strongBuy": 1.0,
                "buy": 0.8,
                "hold": 0.5,
                "sell": 0.2,
                "strongSell": 0.0,
            }
            recommendation_score = rec_scores.get(recommendation, 0.5)

            return AnalystData(
                symbol=symbol,
                recommendation=recommendation,
                target_price=target_price,
                current_price=current_price,
                upside_pct=upside_pct,
                num_analysts=num_analysts,
                recommendation_score=recommendation_score,
            )
        except Exception as e:
            logger.error(f"Failed to get analyst data for {symbol}: {e}")
            return None

    def get_security_industry(
        self, symbol: str, yahoo_symbol: Optional[str] = None
    ) -> Optional[SecurityInfo]:
        """Get security industry/sector.

        Args:
            symbol: Tradernet format symbol
            yahoo_symbol: Optional explicit Yahoo symbol override

        Returns:
            SecurityInfo with industry/sector or None if unavailable
        """
        try:
            yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            return SecurityInfo(
                symbol=symbol,
                industry=info.get("industry"),
                sector=info.get("sector"),
            )
        except Exception as e:
            logger.error(f"Failed to get industry for {symbol}: {e}")
            return None

    def get_security_country_exchange(
        self, symbol: str, yahoo_symbol: Optional[str] = None
    ) -> Optional[SecurityInfo]:
        """Get security country and exchange.

        Args:
            symbol: Tradernet format symbol
            yahoo_symbol: Optional explicit Yahoo symbol override

        Returns:
            SecurityInfo with country/exchange or None if unavailable
        """
        try:
            yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            return SecurityInfo(
                symbol=symbol,
                country=info.get("country"),
                full_exchange_name=info.get("fullExchangeName"),
            )
        except Exception as e:
            logger.error(f"Failed to get country/exchange for {symbol}: {e}")
            return None

    def get_security_info(
        self, symbol: str, yahoo_symbol: Optional[str] = None
    ) -> Optional[SecurityInfo]:
        """Get comprehensive security information.

        Args:
            symbol: Tradernet format symbol
            yahoo_symbol: Optional explicit Yahoo symbol override

        Returns:
            SecurityInfo with all available data or None if unavailable
        """
        try:
            yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            # Determine product type from quoteType
            quote_type = info.get("quoteType", "").lower()
            product_type = None
            if quote_type == "equity":
                product_type = "stock"
            elif quote_type == "etf":
                product_type = "etf"
            elif quote_type == "mutualfund":
                product_type = "mutual_fund"

            return SecurityInfo(
                symbol=symbol,
                industry=info.get("industry"),
                sector=info.get("sector"),
                country=info.get("country"),
                full_exchange_name=info.get("fullExchangeName"),
                product_type=product_type,
                name=info.get("longName") or info.get("shortName"),
            )
        except Exception as e:
            logger.error(f"Failed to get security info for {symbol}: {e}")
            return None


# Global service instance
_service: Optional[YahooFinanceService] = None


def get_yahoo_finance_service() -> YahooFinanceService:
    """Get or create Yahoo Finance service instance."""
    global _service
    if _service is None:
        _service = YahooFinanceService()
    return _service

