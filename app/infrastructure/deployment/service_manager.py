"""Service management for restarting and health checking."""

import asyncio
import logging
import subprocess
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ServiceRestartError(Exception):
    """Raised when service restart fails."""


class HealthCheckError(Exception):
    """Raised when health check fails."""


class ServiceManager:
    """Manage systemd service restarts and health checks."""

    def __init__(self, service_name: str, api_url: str = "http://localhost:8000"):
        """Initialize service manager.

        Args:
            service_name: Name of systemd service (e.g., "arduino-trader")
            api_url: Base URL for API health checks
        """
        self.service_name = service_name
        self.api_url = api_url

    async def restart_service(self, max_attempts: int = 3) -> None:
        """Restart systemd service with retry logic.

        Args:
            max_attempts: Maximum number of restart attempts

        Raises:
            ServiceRestartError: If restart fails after all attempts
        """
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"Restarting {self.service_name} service (attempt {attempt}/{max_attempts})..."
                )

                # Restart service
                # Note: When restarting from within the service, the process may be killed
                # by systemd before subprocess.run() can return. This is expected behavior.
                try:
                    result = subprocess.run(
                        ["sudo", "systemctl", "restart", self.service_name],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if result.returncode != 0:
                        error_msg = result.stderr or result.stdout
                        logger.warning(
                            f"Service restart command failed (attempt {attempt}): {error_msg}"
                        )
                        if attempt < max_attempts:
                            await asyncio.sleep(5)
                            continue
                        raise ServiceRestartError(
                            f"Failed to restart service: {error_msg}"
                        )
                except (KeyboardInterrupt, SystemExit):
                    # Process is being killed by systemd during restart - this is expected
                    # The service will restart and the new code will be active
                    logger.info(
                        "Service restart initiated - current process will be terminated by systemd"
                    )
                    # Give systemd a moment to process the restart
                    await asyncio.sleep(1)
                    # Exit gracefully - systemd will restart the service
                    raise SystemExit(0)

                # Wait for service to start
                logger.debug("Waiting for service to start...")
                await asyncio.sleep(2)

                # Verify service is active
                status_result = subprocess.run(
                    ["sudo", "systemctl", "is-active", "--quiet", self.service_name],
                    timeout=5,
                )

                if status_result.returncode == 0:
                    logger.info(f"{self.service_name} service restarted successfully")
                    return
                else:
                    logger.warning(
                        f"Service restart command succeeded but service is not active (attempt {attempt})"
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(5)
                        continue
                    raise ServiceRestartError(
                        "Service restart command succeeded but service is not active"
                    )

            except subprocess.TimeoutExpired:
                logger.warning(f"Service restart timed out (attempt {attempt})")
                if attempt < max_attempts:
                    await asyncio.sleep(5)
                    continue
                raise ServiceRestartError("Service restart timed out")
            except ServiceRestartError:
                raise
            except Exception as e:
                logger.warning(f"Error during service restart (attempt {attempt}): {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(5)
                    continue
                raise ServiceRestartError(f"Error restarting service: {e}") from e

        raise ServiceRestartError(
            f"Failed to restart service after {max_attempts} attempts"
        )

    async def check_health(self, max_attempts: int = 5, timeout: float = 10.0) -> None:
        """Check API health after deployment.

        Args:
            max_attempts: Maximum number of health check attempts
            timeout: Timeout per attempt in seconds

        Raises:
            HealthCheckError: If health check fails after all attempts
        """
        health_endpoint = f"{self.api_url}/health"

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug(f"Health check attempt {attempt}/{max_attempts}...")

                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(health_endpoint)

                    if response.status_code == 200:
                        logger.info("Health check passed - API is responding")
                        return

                    logger.warning(
                        f"Health check failed: HTTP {response.status_code} (attempt {attempt})"
                    )

            except httpx.TimeoutException:
                logger.warning(f"Health check timed out (attempt {attempt})")
            except httpx.ConnectError:
                logger.warning(f"Health check connection error (attempt {attempt})")
            except Exception as e:
                logger.warning(f"Health check error (attempt {attempt}): {e}")

            if attempt < max_attempts:
                wait_time = 2  # 2 seconds between attempts
                logger.debug(f"Retrying health check in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

        raise HealthCheckError(
            f"Health check failed after {max_attempts} attempts - API is not responding"
        )

    def get_service_status(self) -> Optional[str]:
        """Get current service status.

        Returns:
            Service status ("active", "inactive", "failed", etc.) or None on error
        """
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "is-active", self.service_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return "inactive"
        except Exception as e:
            logger.warning(f"Error getting service status: {e}")
            return None
