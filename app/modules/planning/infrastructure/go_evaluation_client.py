"""HTTP client for Go evaluation service.

This module provides a Python client for the Go planner evaluation service,
enabling high-performance sequence evaluation with 10-100x speedup over Python.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.domain.models import Security
from app.modules.planning.domain.models import ActionCandidate
from app.modules.scoring.domain.models import PortfolioContext

logger = logging.getLogger(__name__)


class GoEvaluationError(Exception):
    """Exception raised when Go evaluation service fails."""

    pass


class GoEvaluationClient:
    """
    HTTP client for Go evaluation service.

    Provides async methods to evaluate action sequences using the high-performance
    Go service instead of Python evaluation functions.

    Usage:
        async with GoEvaluationClient() as client:
            results = await client.evaluate_batch(sequences, context)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:9000",
        timeout: float = 120.0,
    ):
        """
        Initialize Go evaluation client.

        Args:
            base_url: Base URL of Go service (default: http://localhost:9000)
            timeout: Request timeout in seconds (default: 120.0)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "GoEvaluationClient":
        """Enter async context manager."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
            ),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.close()

    async def close(self):
        """Close HTTP client and release connections."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> Dict[str, str]:
        """
        Check if Go service is healthy.

        Returns:
            Dict with status and version

        Raises:
            GoEvaluationError: If service is unhealthy or unreachable
        """
        if not self._client:
            raise GoEvaluationError(
                "Client not initialized. Use async context manager."
            )

        try:
            response = await self._client.get(f"{self.base_url}/api/v1/health")
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise GoEvaluationError("Go service health check timed out")
        except httpx.ConnectError:
            raise GoEvaluationError(
                f"Cannot connect to Go service at {self.base_url}. "
                "Make sure the service is running."
            )
        except httpx.HTTPStatusError as e:
            raise GoEvaluationError(f"Go service returned error: {e}")
        except Exception as e:
            raise GoEvaluationError(f"Go service health check failed: {e}")

    async def evaluate_batch(
        self,
        sequences: List[List[ActionCandidate]],
        portfolio_context: PortfolioContext,
        available_cash_eur: float,
        securities: List[Security],
        transaction_cost_fixed: float = 2.0,
        transaction_cost_percent: float = 0.002,
        price_adjustments: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluate multiple sequences in parallel using Go service.

        Args:
            sequences: List of action sequences to evaluate
            portfolio_context: Current portfolio state
            available_cash_eur: Available cash in EUR
            securities: List of securities for metadata lookup
            transaction_cost_fixed: Fixed transaction cost (EUR)
            transaction_cost_percent: Percentage transaction cost (fraction)
            price_adjustments: Optional price multipliers for stochastic evaluation

        Returns:
            List of evaluation results (same order as input sequences)

        Raises:
            GoEvaluationError: If evaluation fails
        """
        if not self._client:
            raise GoEvaluationError(
                "Client not initialized. Use async context manager."
            )

        if not sequences:
            return []

        # Build request payload
        request_data = {
            "sequences": [self._serialize_sequence(seq) for seq in sequences],
            "evaluation_context": self._serialize_context(
                portfolio_context,
                securities,
                available_cash_eur,
                transaction_cost_fixed,
                transaction_cost_percent,
                price_adjustments,
            ),
        }

        try:
            response = await self._client.post(
                f"{self.base_url}/api/v1/evaluate/batch",
                json=request_data,
            )
            response.raise_for_status()
            result = response.json()

            # Extract results
            results = result.get("results", [])
            errors = result.get("errors", [])

            if errors:
                logger.warning(f"Go evaluation returned errors: {errors}")

            return results

        except httpx.TimeoutException:
            raise GoEvaluationError(
                f"Go service evaluation timed out after {self.timeout}s. "
                f"Try reducing batch size or increasing timeout."
            )
        except httpx.ConnectError:
            raise GoEvaluationError(
                f"Cannot connect to Go service at {self.base_url}. "
                "Make sure the service is running."
            )
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("error", "")
            except Exception:
                pass
            raise GoEvaluationError(
                f"Go service returned HTTP {e.response.status_code}: {error_detail}"
            )
        except Exception as e:
            raise GoEvaluationError(f"Go service evaluation failed: {e}")

    def _serialize_sequence(
        self, sequence: List[ActionCandidate]
    ) -> List[Dict[str, Any]]:
        """
        Serialize action sequence to JSON-compatible format for Go service.

        Args:
            sequence: List of ActionCandidate objects

        Returns:
            List of dicts representing actions
        """
        return [
            {
                "side": action.side,  # "BUY" or "SELL"
                "symbol": action.symbol,
                "name": action.name,
                "quantity": action.quantity,
                "price": action.price,
                "value_eur": action.value_eur,
                "currency": action.currency,
                "priority": action.priority,
                "reason": action.reason,
                "tags": action.tags,
            }
            for action in sequence
        ]

    def _serialize_context(
        self,
        portfolio_context: PortfolioContext,
        securities: List[Security],
        available_cash_eur: float,
        transaction_cost_fixed: float,
        transaction_cost_percent: float,
        price_adjustments: Optional[Dict[str, float]],
    ) -> Dict[str, Any]:
        """
        Serialize evaluation context to JSON-compatible format for Go service.

        Args:
            portfolio_context: Portfolio context with positions and weights
            securities: List of securities
            available_cash_eur: Available cash
            transaction_cost_fixed: Fixed transaction cost
            transaction_cost_percent: Percentage transaction cost
            price_adjustments: Optional price multipliers

        Returns:
            Dict representing evaluation context
        """
        return {
            "portfolio_context": {
                "country_weights": portfolio_context.country_weights or {},
                "industry_weights": portfolio_context.industry_weights or {},
                "positions": portfolio_context.positions or {},
                "total_value": portfolio_context.total_value,
                "security_countries": portfolio_context.security_countries or {},
                "security_industries": portfolio_context.security_industries or {},
                "security_scores": portfolio_context.security_scores or {},
                "security_dividends": portfolio_context.security_dividends or {},
                "country_to_group": portfolio_context.country_to_group or {},
                "industry_to_group": portfolio_context.industry_to_group or {},
                "position_avg_prices": portfolio_context.position_avg_prices or {},
                "current_prices": portfolio_context.current_prices or {},
            },
            "positions": [],  # Not needed by Go service (uses portfolio_context.positions)
            "securities": [
                {
                    "symbol": s.symbol,
                    "name": s.name,
                    "country": s.country,
                    "industry": s.industry,
                    "currency": s.currency.value if s.currency else "EUR",
                }
                for s in securities
            ],
            "available_cash_eur": available_cash_eur,
            "total_portfolio_value_eur": portfolio_context.total_value,
            "current_prices": portfolio_context.current_prices or {},
            "stocks_by_symbol": {},  # Computed by Go service
            "transaction_cost_fixed": transaction_cost_fixed,
            "transaction_cost_percent": transaction_cost_percent,
            "price_adjustments": price_adjustments or {},
        }


async def evaluate_sequences_with_go(
    sequences: List[List[ActionCandidate]],
    portfolio_context: PortfolioContext,
    available_cash_eur: float,
    securities: List[Security],
    transaction_cost_fixed: float = 2.0,
    transaction_cost_percent: float = 0.002,
    price_adjustments: Optional[Dict[str, float]] = None,
    go_service_url: str = "http://localhost:9000",
) -> List[Dict[str, Any]]:
    """
    Convenience function to evaluate sequences with Go service.

    This is a simple wrapper around GoEvaluationClient for one-off evaluations.
    For multiple evaluations, use GoEvaluationClient directly with async context manager.

    Args:
        sequences: List of action sequences to evaluate
        portfolio_context: Current portfolio state
        available_cash_eur: Available cash in EUR
        securities: List of securities for metadata lookup
        transaction_cost_fixed: Fixed transaction cost (EUR)
        transaction_cost_percent: Percentage transaction cost (fraction)
        price_adjustments: Optional price multipliers for stochastic evaluation
        go_service_url: URL of Go service (default: http://localhost:9000)

    Returns:
        List of evaluation results

    Raises:
        GoEvaluationError: If evaluation fails
    """
    async with GoEvaluationClient(base_url=go_service_url) as client:
        return await client.evaluate_batch(
            sequences=sequences,
            portfolio_context=portfolio_context,
            available_cash_eur=available_cash_eur,
            securities=securities,
            transaction_cost_fixed=transaction_cost_fixed,
            transaction_cost_percent=transaction_cost_percent,
            price_adjustments=price_adjustments,
        )
