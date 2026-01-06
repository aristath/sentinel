"""PyPFOpt router for unified microservice."""

import logging
from typing import Dict, List, Tuple, cast

from app.models.pypfopt_models import (
    CovarianceRequest,
    HRPRequest,
    MeanVarianceRequest,
    ServiceResponse,
)
from app.services.converters import (
    dataframe_to_matrix,
    dict_to_series,
    matrix_to_dataframe,
    timeseries_to_dataframe,
)
from app.services.pypfopt_service import PyPortfolioOptService
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize service
service = PyPortfolioOptService()


@router.post("/optimize/mean-variance", response_model=ServiceResponse)
async def optimize_mean_variance(request: MeanVarianceRequest) -> ServiceResponse:
    """Mean-Variance portfolio optimization using EfficientFrontier.

    Supports multiple optimization strategies:
    - efficient_return: Maximize return for given target
    - min_volatility: Minimize portfolio volatility
    - efficient_risk: Maximize return for target volatility
    - max_sharpe: Maximize Sharpe ratio

    Args:
        request: Mean-variance optimization parameters

    Returns:
        ServiceResponse with optimized weights and performance metrics
    """
    try:
        logger.info(f"Mean-variance optimization request: strategy={request.strategy}")

        # Convert request data to pandas structures
        mu = dict_to_series(request.expected_returns)
        cov = matrix_to_dataframe(request.covariance_matrix, request.symbols)
        weight_bounds = cast(
            List[Tuple[float, float]], [tuple(b) for b in request.weight_bounds]
        )
        sector_constraints = (
            [c.model_dump() for c in request.sector_constraints]
            if request.sector_constraints
            else []
        )

        # Run optimization
        result = service.mean_variance_optimize(
            mu,
            cov,
            weight_bounds,
            sector_constraints,
            request.strategy,
            request.target_return,
            request.target_volatility,
        )

        weights: Dict[str, float] = result["weights"]
        logger.info(f"Optimization successful: {len(weights)} securities")

        return ServiceResponse(
            success=True,
            data={
                "weights": result["weights"],
                "strategy_used": request.strategy,
                "achieved_return": result["achieved_return"],
                "achieved_volatility": result["achieved_volatility"],
            },
        )

    except Exception as e:
        logger.exception("Mean-variance optimization failed")
        return ServiceResponse(success=False, error=str(e))


@router.post("/optimize/hrp", response_model=ServiceResponse)
async def optimize_hrp(request: HRPRequest) -> ServiceResponse:
    """Hierarchical Risk Parity portfolio optimization.

    HRP is a modern alternative to mean-variance optimization that:
    - Uses machine learning (hierarchical clustering)
    - Doesn't require expected returns
    - More stable in practice

    Args:
        request: HRP optimization parameters with returns time series

    Returns:
        ServiceResponse with optimized weights
    """
    try:
        logger.info(f"HRP optimization request: {len(request.returns.data)} securities")

        # Convert request to pandas DataFrame
        returns_df = timeseries_to_dataframe(request.returns)

        # Run HRP optimization
        weights = service.hrp_optimize(returns_df)

        logger.info(f"HRP optimization successful: {len(weights)} securities")

        return ServiceResponse(success=True, data={"weights": weights})

    except Exception as e:
        logger.exception("HRP optimization failed")
        return ServiceResponse(success=False, error=str(e))


@router.post("/risk-model/covariance", response_model=ServiceResponse)
async def calculate_covariance(request: CovarianceRequest) -> ServiceResponse:
    """Calculate covariance matrix using Ledoit-Wolf shrinkage.

    Ledoit-Wolf shrinkage improves covariance estimation by:
    - Reducing estimation error
    - Being more stable with limited data
    - Better performance for portfolio optimization

    Args:
        request: Price time series data

    Returns:
        ServiceResponse with covariance matrix and symbols
    """
    try:
        logger.info(
            f"Covariance calculation request: {len(request.prices.data)} securities"
        )

        # Convert request to pandas DataFrame
        prices_df = timeseries_to_dataframe(request.prices)

        # Calculate covariance matrix
        cov_df = service.calculate_covariance(prices_df)

        # Convert back to nested list
        matrix, symbols = dataframe_to_matrix(cov_df)

        logger.info(
            f"Covariance calculation successful: {len(symbols)}x{len(symbols)} matrix"
        )

        return ServiceResponse(
            success=True, data={"covariance_matrix": matrix, "symbols": symbols}
        )

    except Exception as e:
        logger.exception("Covariance calculation failed")
        return ServiceResponse(success=False, error=str(e))


@router.post("/optimize/progressive", response_model=ServiceResponse)
async def optimize_progressive(request: MeanVarianceRequest) -> ServiceResponse:
    """Progressive optimization with fallback strategies.

    This is the main optimization endpoint used by arduino-trader.
    It implements a robust multi-strategy approach:

    1. Try each strategy with full constraints
    2. If all fail, relax sector constraints by 50%
    3. If all fail again, remove constraints entirely
    4. Return first success

    Strategies tried (in order):
    - efficient_return: Target specific return
    - min_volatility: Minimize risk
    - efficient_risk: Target specific volatility
    - max_sharpe: Maximize risk-adjusted return

    Args:
        request: Mean-variance optimization parameters

    Returns:
        ServiceResponse with optimized weights, strategy used, and constraint level
    """
    try:
        logger.info("Progressive optimization request")

        # Convert request data to pandas structures
        mu = dict_to_series(request.expected_returns)
        cov = matrix_to_dataframe(request.covariance_matrix, request.symbols)
        weight_bounds = cast(
            List[Tuple[float, float]], [tuple(b) for b in request.weight_bounds]
        )
        sector_constraints = (
            [c.model_dump() for c in request.sector_constraints]
            if request.sector_constraints
            else []
        )

        # Use target_return from request or default to 11%
        target_return = (
            request.target_return if request.target_return is not None else 0.11
        )

        # Run progressive optimization
        result = service.progressive_optimize(
            mu, cov, weight_bounds, sector_constraints, target_return
        )

        logger.info(
            f"Progressive optimization successful: "
            f"strategy={result['strategy_used']}, "
            f"constraint_level={result['constraint_level']}, "
            f"attempts={result['attempts']}"
        )

        return ServiceResponse(success=True, data=result)

    except Exception as e:
        logger.exception("Progressive optimization failed")
        return ServiceResponse(success=False, error=str(e))
