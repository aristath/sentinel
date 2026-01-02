"""Go evaluator service deployer.

Downloads ARM64 binary from GitHub Actions and deploys to production.
"""

import asyncio
import hashlib
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class GoDeploymentError(Exception):
    """Raised when Go evaluator deployment fails."""


class GoEvaluatorDeployer:
    """Deploy Go evaluator service from GitHub Actions artifacts."""

    def __init__(
        self,
        repo_dir: Path,
        binary_path: Path = Path("/home/arduino/arduino-trader/evaluator-go"),
        service_name: str = "evaluator-go",
    ):
        """Initialize Go evaluator deployer.

        Args:
            repo_dir: Path to Git repository
            binary_path: Path where binary should be deployed
            service_name: Systemd service name

        Raises:
            ValueError: If binary_path is invalid or contains path traversal
        """
        # Validate binary_path to prevent command injection
        if not binary_path.is_absolute():
            raise ValueError(f"Binary path must be absolute: {binary_path}")

        if ".." in str(binary_path):
            raise ValueError(f"Binary path cannot contain '..': {binary_path}")

        self.repo_dir = repo_dir
        self.binary_path = binary_path
        self.service_name = service_name

    async def deploy(self) -> bool:
        """Deploy Go evaluator service.

        Downloads latest ARM64 binary from GitHub Actions and deploys it.

        Returns:
            True if deployment successful, False otherwise

        Raises:
            GoDeploymentError: If deployment fails
        """
        try:
            logger.info("Deploying Go evaluator service...")

            # Step 1: Build binary locally (for now, until GitHub Actions artifact download is implemented)
            # In production, this will download from GitHub Actions artifacts
            binary_source = self.repo_dir / "services" / "evaluator-go" / "evaluator-go"

            if not binary_source.exists():
                # Try to build it
                logger.info("Binary not found, attempting to build...")
                await self._build_binary()

            if not binary_source.exists():
                raise GoDeploymentError(
                    f"Go binary not found at {binary_source}. "
                    "Build may have failed or GitHub Actions artifact not downloaded."
                )

            # Step 2: Stop service if running
            await self._stop_service()

            # Step 3: Deploy binary with verification
            logger.info(f"Copying binary to {self.binary_path}")

            # Calculate checksum of source binary
            source_checksum = self._calculate_checksum(binary_source)
            logger.debug(f"Source binary checksum: {source_checksum}")

            subprocess.run(
                ["cp", str(binary_source), str(self.binary_path)],
                check=True,
                capture_output=True,
                timeout=10,
            )

            # Verify checksum after copy
            dest_checksum = self._calculate_checksum(self.binary_path)
            if source_checksum != dest_checksum:
                raise GoDeploymentError(
                    f"Binary checksum mismatch! Source: {source_checksum}, Dest: {dest_checksum}"
                )
            logger.info("Binary checksum verified successfully")

            # Make executable
            subprocess.run(
                ["chmod", "+x", str(self.binary_path)],
                check=True,
                capture_output=True,
                timeout=5,
            )

            # Step 4: Create systemd service if it doesn't exist
            await self._ensure_systemd_service()

            # Step 5: Start service
            await self._start_service()

            # Step 6: Check health with retry loop
            healthy = False
            for attempt in range(10):  # Up to 10 seconds
                await asyncio.sleep(1)
                if await self._check_health():
                    healthy = True
                    break
                if attempt < 9:  # Don't log on last attempt
                    logger.debug(
                        f"Health check attempt {attempt + 1}/10 failed, retrying..."
                    )

            if not healthy:
                # Rollback: stop the failed service
                logger.error(
                    "Service started but health check failed after 10 attempts"
                )
                await self._stop_service()
                raise GoDeploymentError(
                    "Service started but health check failed after 10 attempts"
                )

            logger.info("Go evaluator deployed successfully")
            return True

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            raise GoDeploymentError(f"Command failed: {error_msg}") from e
        except Exception as e:
            raise GoDeploymentError(f"Deployment failed: {e}") from e

    async def _build_binary(self) -> None:
        """Build Go binary locally (fallback if artifact not available)."""
        try:
            logger.info("Building Go binary...")
            go_dir = self.repo_dir / "services" / "evaluator-go"

            # Run go build
            result = subprocess.run(
                ["go", "build", "-o", "evaluator-go", "./cmd/server"],
                cwd=go_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                logger.warning(f"Go build failed: {result.stderr}")
                raise GoDeploymentError(f"Go build failed: {result.stderr}")

            logger.info("Go binary built successfully")

        except FileNotFoundError:
            logger.warning("Go not installed, cannot build binary locally")
            raise GoDeploymentError(
                "Go not installed and GitHub Actions artifact not available"
            )

    async def _stop_service(self) -> None:
        """Stop the Go evaluator service."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "stop", self.service_name],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info("Service stopped")
            else:
                logger.debug("Service was not running or stop failed")
        except Exception as e:
            logger.warning(f"Could not stop service: {e}")

    async def _start_service(self) -> None:
        """Start the Go evaluator service."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "start", self.service_name],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                error = result.stderr.decode() if result.stderr else "Unknown error"
                raise GoDeploymentError(f"Failed to start service: {error}")

            logger.info("Service started")

        except subprocess.TimeoutExpired:
            raise GoDeploymentError("Service start timed out")

    async def _ensure_systemd_service(self) -> None:
        """Ensure systemd service file exists."""
        service_file = (
            Path.home()
            / ".config"
            / "systemd"
            / "user"
            / f"{self.service_name}.service"
        )

        if service_file.exists():
            logger.debug("Systemd service file already exists")
            return

        logger.info("Creating systemd service file")
        service_content = f"""[Unit]
Description=Go Planner Evaluation Service
After=network.target

[Service]
Type=simple
WorkingDirectory={self.binary_path.parent}
ExecStart={self.binary_path}
Restart=always
RestartSec=5s
Environment=PORT=9000
Environment=GIN_MODE=release

# Security hardening
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
NoNewPrivileges=true
ReadWritePaths={self.binary_path.parent}

[Install]
WantedBy=default.target
"""

        service_file.parent.mkdir(parents=True, exist_ok=True)
        service_file.write_text(service_content)
        logger.info(f"Created systemd service: {service_file}")

        # Reload systemd
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True,
            timeout=10,
        )

    async def _check_health(self) -> bool:
        """Check if Go evaluator service is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:9000/api/v1/health")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "healthy":
                        logger.info("Health check passed")
                        return True

            logger.warning("Health check failed - unexpected response")
            return False

        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of SHA256 checksum
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
