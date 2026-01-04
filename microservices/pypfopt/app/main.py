"""FastAPI application for PyPortfolioOpt microservice."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import logging
from datetime import datetime

from app.models import (
    ServiceResponse,
    MeanVarianceRequest,
    HRPRequest,
    CovarianceRequest,
    OptimizationResult
)
from app.service import PyPortfolioOptService
from app.converters import (
    timeseries_to_dataframe,
    matrix_to_dataframe,
    dataframe_to_matrix,
    dict_to_series
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PyPortfolioOpt Microservice",
    description="Minimal wrapper for portfolio optimization using PyPortfolioOpt library",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize service
service = PyPortfolioOptService()


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Basic service health information
    """
    return {
        "status": "healthy",
        "service": "pypfopt",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/optimize/mean-variance", response_model=ServiceResponse)
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
        weight_bounds = [tuple(b) for b in request.weight_bounds]
        sector_constraints = [c.model_dump() for c in request.sector_constraints]

        # Run optimization
        result = service.mean_variance_optimize(
            mu, cov,
            weight_bounds,
            sector_constraints,
            request.strategy,
            request.target_return,
            request.target_volatility
        )

        logger.info(f"Optimization successful: {len(result['weights'])} securities")

        return ServiceResponse(
            success=True,
            data={
                "weights": result["weights"],
                "strategy_used": request.strategy,
                "achieved_return": result["achieved_return"],
                "achieved_volatility": result["achieved_volatility"]
            }
        )

    except Exception as e:
        logger.exception("Mean-variance optimization failed")
        return ServiceResponse(success=False, error=str(e))


@app.post("/optimize/hrp", response_model=ServiceResponse)
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

        return ServiceResponse(
            success=True,
            data={"weights": weights}
        )

    except Exception as e:
        logger.exception("HRP optimization failed")
        return ServiceResponse(success=False, error=str(e))


@app.post("/risk-model/covariance", response_model=ServiceResponse)
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
        logger.info(f"Covariance calculation request: {len(request.prices.data)} securities")

        # Convert request to pandas DataFrame
        prices_df = timeseries_to_dataframe(request.prices)

        # Calculate covariance matrix
        cov_df = service.calculate_covariance(prices_df)

        # Convert back to nested list
        matrix, symbols = dataframe_to_matrix(cov_df)

        logger.info(f"Covariance calculation successful: {len(symbols)}x{len(symbols)} matrix")

        return ServiceResponse(
            success=True,
            data={
                "covariance_matrix": matrix,
                "symbols": symbols
            }
        )

    except Exception as e:
        logger.exception("Covariance calculation failed")
        return ServiceResponse(success=False, error=str(e))


@app.post("/optimize/progressive", response_model=ServiceResponse)
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
        weight_bounds = [tuple(b) for b in request.weight_bounds]
        sector_constraints = [c.model_dump() for c in request.sector_constraints]

        # Use target_return from request or default to 11%
        target_return = request.target_return if request.target_return is not None else 0.11

        # Run progressive optimization
        result = service.progressive_optimize(
            mu, cov,
            weight_bounds,
            sector_constraints,
            target_return
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
