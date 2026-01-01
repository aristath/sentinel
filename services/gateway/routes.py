"""REST API routes for Gateway service."""

from fastapi import APIRouter, Depends, Path, Query

from app.modules.gateway.services.local_gateway_service import LocalGatewayService
from services.gateway.dependencies import get_gateway_service
from services.gateway.models import (
    HealthResponse,
    ProcessDepositRequest,
    ProcessDepositResponse,
    ServiceHealthResponse,
    ServiceStatus,
    SystemStatusResponse,
    TradingCycleResponse,
    TradingCycleUpdate,
    TriggerTradingCycleRequest,
)

router = APIRouter()


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    service: LocalGatewayService = Depends(get_gateway_service),
):
    """
    Get overall system status.

    Args:
        service: Gateway service instance

    Returns:
        System status with all services
    """
    status = await service.get_system_status()

    # Convert service statuses to response
    service_statuses = [
        ServiceStatus(
            service_name=svc["service_name"],
            healthy=svc["healthy"],
            version=svc.get("version", ""),
            status_message=svc.get("status_message", ""),
        )
        for svc in status.services
    ]

    return SystemStatusResponse(
        system_healthy=status.system_healthy,
        services=service_statuses,
        overall_message=status.overall_message,
    )


@router.post("/trading-cycle", response_model=TradingCycleResponse)
async def trigger_trading_cycle(
    request: TriggerTradingCycleRequest,
    service: LocalGatewayService = Depends(get_gateway_service),
):
    """
    Trigger a complete trading cycle.

    Args:
        request: Trading cycle request
        service: Gateway service instance

    Returns:
        Trading cycle result

    Note:
        Streaming operation converted to blocking - returns final result
    """
    cycle_id = ""
    final_update = None
    error = None

    try:
        # Collect all updates from streaming operation
        async for update in service.trigger_trading_cycle(
            force=request.force,
            deposit_amount=request.deposit_amount,
        ):
            cycle_id = update.cycle_id
            if update.complete:
                final_update = TradingCycleUpdate(
                    cycle_id=update.cycle_id,
                    phase=update.phase,
                    progress_pct=update.progress_pct,
                    message=update.message,
                    complete=update.complete,
                    success=update.success,
                    error=update.error,
                    results=update.results or {},
                )
                break
    except Exception as e:
        error = str(e)

    if error:
        return TradingCycleResponse(
            cycle_id=cycle_id,
            success=False,
            message=error,
            final_update=None,
        )

    if final_update:
        return TradingCycleResponse(
            cycle_id=cycle_id,
            success=final_update.success,
            message=final_update.message,
            final_update=final_update,
        )
    else:
        return TradingCycleResponse(
            cycle_id=cycle_id,
            success=False,
            message="Trading cycle failed - no final update",
            final_update=None,
        )


@router.post("/deposit", response_model=ProcessDepositResponse)
async def process_deposit(
    request: ProcessDepositRequest,
    service: LocalGatewayService = Depends(get_gateway_service),
):
    """
    Process a deposit.

    Args:
        request: Deposit request
        service: Gateway service instance

    Returns:
        Deposit processing result
    """
    result = await service.process_deposit(
        account_id=request.account_id,
        amount=request.amount,
    )

    return ProcessDepositResponse(
        success=result.success,
        new_balance=result.new_balance,
        message=result.message,
    )


@router.get("/services/{service_name}/health", response_model=ServiceHealthResponse)
async def get_service_health(
    service_name: str = Path(
        ...,
        pattern=r'^[a-z][a-z0-9_-]*$',
        description="Service name (lowercase alphanumeric with hyphens/underscores)",
    ),
    service: LocalGatewayService = Depends(get_gateway_service),
):
    """
    Get health of a specific service.

    Args:
        service_name: Name of the service
        service: Gateway service instance

    Returns:
        Service health status
    """
    # Get system status and find the requested service
    status = await service.get_system_status()

    service_status = None
    for svc in status.services:
        if svc["service_name"] == service_name:
            service_status = svc
            break

    if service_status:
        status_response = ServiceStatus(
            service_name=service_status["service_name"],
            healthy=service_status["healthy"],
            version=service_status.get("version", ""),
            status_message=service_status.get("status_message", ""),
        )

        return ServiceHealthResponse(found=True, status=status_response)
    else:
        return ServiceHealthResponse(found=False)


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
