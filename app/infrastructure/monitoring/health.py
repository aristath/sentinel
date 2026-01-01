"""Health check system for microservices."""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional, cast

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    status: HealthStatus
    message: str = ""
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class HealthCheck:
    """Individual health check."""

    def __init__(
        self,
        name: str,
        check_func: Callable[[], Awaitable[HealthCheckResult]],
        critical: bool = True,
    ):
        """
        Initialize health check.

        Args:
            name: Name of the health check
            check_func: Async function that performs the check
            critical: If True, failure of this check marks service as unhealthy
        """
        self.name = name
        self.check_func = check_func
        self.critical = critical
        self.last_result: Optional[HealthCheckResult] = None
        self.last_check_time: Optional[float] = None

    async def run(self) -> HealthCheckResult:
        """Run the health check."""
        try:
            result = await asyncio.wait_for(self.check_func(), timeout=5.0)
            self.last_result = result
            self.last_check_time = asyncio.get_event_loop().time()
            return result
        except asyncio.TimeoutError:
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY, message="Health check timed out"
            )
            self.last_result = result
            self.last_check_time = asyncio.get_event_loop().time()
            return result
        except Exception as e:
            logger.error(f"Health check '{self.name}' failed: {e}", exc_info=True)
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY, message=f"Health check error: {e}"
            )
            self.last_result = result
            self.last_check_time = asyncio.get_event_loop().time()
            return result


class HealthCheckRegistry:
    """Registry for managing health checks."""

    def __init__(self, service_name: str):
        """Initialize health check registry."""
        self.service_name = service_name
        self._checks: Dict[str, HealthCheck] = {}

    def register(
        self,
        name: str,
        check_func: Callable[[], Awaitable[HealthCheckResult]],
        critical: bool = True,
    ):
        """Register a health check."""
        self._checks[name] = HealthCheck(name, check_func, critical)
        logger.info(
            f"Registered health check '{name}' for {self.service_name} "
            f"(critical={critical})"
        )

    async def run_all(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks concurrently."""
        results = {}

        tasks = {name: check.run() for name, check in self._checks.items()}

        completed = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for (name, _), result in zip(tasks.items(), completed):
            if isinstance(result, Exception):
                logger.error(f"Health check '{name}' failed with exception: {result}")
                results[name] = HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Exception: {result}",
                )
            else:
                results[name] = cast(HealthCheckResult, result)

        return results

    async def get_overall_health(self) -> HealthCheckResult:
        """Get overall service health based on all checks."""
        if not self._checks:
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="No health checks registered",
            )

        results = await self.run_all()

        # Check critical checks
        critical_unhealthy = []
        non_critical_unhealthy = []

        for name, check in self._checks.items():
            result = results.get(name)
            if result and result.status != HealthStatus.HEALTHY:
                if check.critical:
                    critical_unhealthy.append(name)
                else:
                    non_critical_unhealthy.append(name)

        # Determine overall status
        if critical_unhealthy:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Critical checks failing: {', '.join(critical_unhealthy)}",
                details={"checks": results},
            )
        elif non_critical_unhealthy:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                message=f"Non-critical checks failing: {', '.join(non_critical_unhealthy)}",
                details={"checks": results},
            )
        else:
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="All health checks passed",
                details={"checks": results},
            )

    def get_check_results(self) -> Dict[str, HealthCheckResult]:
        """Get last results of all health checks without running them."""
        return {
            name: check.last_result or HealthCheckResult(status=HealthStatus.UNKNOWN)
            for name, check in self._checks.items()
        }


# Common health check functions
async def check_database_connection() -> HealthCheckResult:
    """Example: Check database connection."""
    # TODO: Implement actual database check
    return HealthCheckResult(
        status=HealthStatus.HEALTHY, message="Database connection OK"
    )


async def check_grpc_service_availability(
    service_name: str, health_check_func
) -> HealthCheckResult:
    """Check if a gRPC service is available."""
    try:
        result = await asyncio.wait_for(health_check_func(), timeout=3.0)
        if result.healthy:
            return HealthCheckResult(
                status=HealthStatus.HEALTHY, message=f"{service_name} is available"
            )
        else:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"{service_name} reported unhealthy",
            )
    except asyncio.TimeoutError:
        return HealthCheckResult(
            status=HealthStatus.UNHEALTHY,
            message=f"{service_name} health check timed out",
        )
    except Exception as e:
        return HealthCheckResult(
            status=HealthStatus.UNHEALTHY,
            message=f"{service_name} health check failed: {e}",
        )


async def check_memory_usage(threshold_pct: float = 90.0) -> HealthCheckResult:
    """Check memory usage."""
    try:
        import psutil

        memory = psutil.virtual_memory()
        if memory.percent > threshold_pct:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                message=f"Memory usage high: {memory.percent:.1f}%",
                details={
                    "percent": memory.percent,
                    "available_mb": memory.available / 1024 / 1024,
                },
            )
        else:
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message=f"Memory usage OK: {memory.percent:.1f}%",
                details={"percent": memory.percent},
            )
    except ImportError:
        return HealthCheckResult(
            status=HealthStatus.UNKNOWN, message="psutil not available"
        )
    except Exception as e:
        return HealthCheckResult(
            status=HealthStatus.UNHEALTHY, message=f"Memory check failed: {e}"
        )


async def check_disk_space(
    path: str = "/", threshold_pct: float = 90.0
) -> HealthCheckResult:
    """Check disk space."""
    try:
        import psutil

        disk = psutil.disk_usage(path)
        if disk.percent > threshold_pct:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                message=f"Disk space low: {disk.percent:.1f}%",
                details={
                    "percent": disk.percent,
                    "free_gb": disk.free / 1024 / 1024 / 1024,
                },
            )
        else:
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message=f"Disk space OK: {disk.percent:.1f}%",
                details={"percent": disk.percent},
            )
    except ImportError:
        return HealthCheckResult(
            status=HealthStatus.UNKNOWN, message="psutil not available"
        )
    except Exception as e:
        return HealthCheckResult(
            status=HealthStatus.UNHEALTHY, message=f"Disk check failed: {e}"
        )
