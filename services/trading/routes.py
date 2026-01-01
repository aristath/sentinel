"""REST API routes for Trading service."""

from fastapi import APIRouter, Depends, Query, Path

from app.modules.trading.services.local_trading_service import LocalTradingService
from app.modules.trading.services.trading_service_interface import TradeRequest
from services.trading.dependencies import get_trading_service
from services.trading.models import (
    BatchExecuteTradesRequest,
    BatchExecuteTradesResponse,
    CancelTradeResponse,
    ExecuteTradeRequest,
    ExecuteTradeResponse,
    HealthResponse,
    TradeExecution,
    TradeHistoryResponse,
    TradeStatusResponse,
    ValidateTradeRequest,
    ValidateTradeResponse,
)

router = APIRouter()


@router.post("/execute", response_model=ExecuteTradeResponse)
async def execute_trade(
    request: ExecuteTradeRequest,
    service: LocalTradingService = Depends(get_trading_service),
):
    """
    Execute a single trade.

    Args:
        request: Trade execution request
        service: Trading service instance

    Returns:
        Trade execution result
    """
    # Convert to domain TradeRequest
    domain_request = TradeRequest(
        account_id=request.account_id,
        isin=request.isin,
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        limit_price=request.limit_price,
    )

    result = await service.execute_trade(domain_request)

    execution = None
    if result.executed_quantity > 0:
        execution = TradeExecution(
            trade_id=result.trade_id,
            isin=request.isin,
            symbol=request.symbol,
            side=request.side,
            quantity_requested=request.quantity,
            quantity_filled=result.executed_quantity,
            average_price=result.executed_price or 0.0,
        )

    return ExecuteTradeResponse(
        success=result.success,
        trade_id=result.trade_id,
        status="EXECUTED" if result.success else "FAILED",
        message=result.message,
        execution=execution,
    )


@router.post("/execute/batch", response_model=BatchExecuteTradesResponse)
async def batch_execute_trades(
    request: BatchExecuteTradesRequest,
    service: LocalTradingService = Depends(get_trading_service),
):
    """
    Execute multiple trades in batch.

    Args:
        request: Batch trade execution request
        service: Trading service instance

    Returns:
        Batch execution results
    """
    # Convert to domain TradeRequests
    domain_requests = [
        TradeRequest(
            account_id=trade.account_id,
            isin=trade.isin,
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            limit_price=trade.limit_price,
        )
        for trade in request.trades
    ]

    results = await service.batch_execute_trades(domain_requests)

    response_results = [
        ExecuteTradeResponse(
            success=result.success,
            trade_id=result.trade_id,
            status="EXECUTED" if result.success else "FAILED",
            message=result.message,
        )
        for result in results
    ]

    successful = sum(1 for r in results if r.success)

    return BatchExecuteTradesResponse(
        all_success=successful == len(results),
        results=response_results,
        successful=successful,
        failed=len(results) - successful,
    )


@router.get("/status/{trade_id}", response_model=TradeStatusResponse)
async def get_trade_status(
    trade_id: str = Path(

        ...,

        pattern=r'^[a-zA-Z0-9_-]{1,64}$',

        description="Trade ID (alphanumeric with hyphens/underscores)",

    ),
    service: LocalTradingService = Depends(get_trading_service),
):
    """
    Get trade status by ID.

    Args:
        trade_id: Trade identifier
        service: Trading service instance

    Returns:
        Trade status

    Note:
        Current implementation executes trades immediately - status tracking not yet implemented
    """
    # In full implementation, would query trade status from database/broker
    # For now, return not found (trades are executed immediately in current implementation)
    return TradeStatusResponse(
        found=False,
        trade_id=trade_id,
        status="UNKNOWN",
        message="Trade status tracking not yet implemented",
    )


@router.get("/history", response_model=TradeHistoryResponse)
async def get_trade_history(
    account_id: str = Query(default="default", description="Account identifier"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of trades to return"),
    service: LocalTradingService = Depends(get_trading_service),
):
    """
    Get trade execution history.

    Args:
        account_id: Account identifier
        limit: Maximum number of trades to return
        service: Trading service instance

    Returns:
        Trade history
    """
    history = await service.get_trade_history(account_id=account_id, limit=limit)

    # Convert to TradeExecution
    executions = [
        TradeExecution(
            trade_id=str(trade.id) if trade.id else "",
            isin=trade.isin or "",
            symbol=trade.symbol,
            side=trade.side,
            quantity_requested=trade.quantity,
            quantity_filled=trade.quantity,
            average_price=trade.price,
        )
        for trade in history
    ]

    return TradeHistoryResponse(
        executions=executions,
        total=len(executions),
    )


@router.post("/cancel/{trade_id}", response_model=CancelTradeResponse)
async def cancel_trade(
    trade_id: str = Path(

        ...,

        pattern=r'^[a-zA-Z0-9_-]{1,64}$',

        description="Trade ID (alphanumeric with hyphens/underscores)",

    ),
    service: LocalTradingService = Depends(get_trading_service),
):
    """
    Cancel a pending trade.

    Args:
        trade_id: Trade identifier
        service: Trading service instance

    Returns:
        Cancellation result

    Note:
        Current implementation executes trades immediately - cancellation not supported
    """
    # Current implementation executes trades immediately, so cancellation not applicable
    # In full implementation with pending orders, would call broker API to cancel
    return CancelTradeResponse(
        success=False,
        message="Trade cancellation not supported - trades execute immediately",
    )


@router.post("/validate", response_model=ValidateTradeResponse)
async def validate_trade(
    request: ValidateTradeRequest,
    service: LocalTradingService = Depends(get_trading_service),
):
    """
    Validate a trade before execution (pre-execution checks).

    Args:
        request: Trade to validate
        service: Trading service instance

    Returns:
        Validation result with errors and warnings
    """
    errors = []
    warnings = []

    # Basic validation
    if request.quantity <= 0:
        errors.append("Quantity must be positive")

    if not request.symbol and not request.isin:
        errors.append("Either symbol or ISIN must be provided")

    if request.side not in ["BUY", "SELL"]:
        errors.append("Side must be BUY or SELL")

    # Check if sufficient cash (simplified - full implementation would check actual balance)
    if request.side == "BUY" and request.limit_price:
        estimated_cost = request.quantity * request.limit_price
        if estimated_cost > 10000:  # Placeholder limit
            warnings.append("Trade value exceeds typical limit")

    return ValidateTradeResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        Service health status
    """
    return HealthResponse(
        healthy=True,
        version="1.0.0",
        status="OK",
        checks={},
    )
