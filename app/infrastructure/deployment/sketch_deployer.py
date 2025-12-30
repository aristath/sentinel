"""Sketch compilation and upload for Arduino."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class SketchCompilationError(Exception):
    """Raised when sketch compilation fails."""


class SketchUploadError(Exception):
    """Raised when sketch upload fails."""


class SketchDeployer:
    """Compile and upload Arduino sketch."""

    def __init__(self, sketch_dir: Path, fqbn: str = "arduino:zephyr:unoq"):
        """Initialize sketch deployer.

        Args:
            sketch_dir: Path to sketch directory (contains sketch.ino)
            fqbn: Fully Qualified Board Name for Arduino CLI
        """
        self.sketch_dir = sketch_dir
        self.fqbn = fqbn
        self.serial_port = self._detect_serial_port()

    def _detect_serial_port(self) -> str:
        """Detect serial port for upload.

        Returns:
            Serial port path (defaults to /dev/ttyHS1)
        """
        # Try ttyHS1 first (Arduino Uno Q internal), then ttyACM0
        if Path("/dev/ttyHS1").exists():
            return "/dev/ttyHS1"
        elif Path("/dev/ttyACM0").exists():
            return "/dev/ttyACM0"
        else:
            return "/dev/ttyHS1"  # Default fallback

    async def compile_and_upload(self) -> None:
        """Compile and upload sketch.

        Raises:
            SketchCompilationError: If compilation fails
            SketchUploadError: If upload fails
        """
        await self._ensure_arduino_cli()
        await self._compile_sketch()
        await self._upload_sketch()

    async def _ensure_arduino_cli(self) -> None:
        """Ensure Arduino CLI is installed and configured."""
        try:
            # Check if arduino-cli is available
            result = subprocess.run(
                ["arduino-cli", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.debug("Arduino CLI is available")
                return

            # Try to find it in common locations
            for path in ["~/bin/arduino-cli", "/usr/local/bin/arduino-cli"]:
                expanded_path = Path(path).expanduser()
                if expanded_path.exists():
                    logger.debug(f"Found Arduino CLI at {expanded_path}")
                    return

            logger.warning("Arduino CLI not found - sketch compilation may fail")

        except Exception as e:
            logger.warning(f"Error checking for Arduino CLI: {e}")

    async def _compile_sketch(self) -> None:
        """Compile sketch.

        Raises:
            SketchCompilationError: If compilation fails
        """
        sketch_file = self.sketch_dir / "sketch.ino"
        if not sketch_file.exists():
            raise SketchCompilationError(f"Sketch file not found: {sketch_file}")

        try:
            logger.info(f"Compiling sketch: {sketch_file}")

            # Update core index (non-blocking, ignore errors)
            subprocess.run(
                ["arduino-cli", "core", "update-index"],
                capture_output=True,
                timeout=30,
            )

            # Install board platform
            logger.debug(f"Installing board platform: {self.fqbn}")
            result = subprocess.run(
                ["arduino-cli", "core", "install", "arduino:zephyr"],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes max
            )
            if result.returncode != 0:
                logger.warning(f"Failed to install board platform: {result.stderr}")

            # Compile sketch
            result = subprocess.run(
                ["arduino-cli", "compile", "--fqbn", self.fqbn, str(self.sketch_dir)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes max
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise SketchCompilationError(f"Compilation failed: {error_msg}")

            logger.info("Sketch compiled successfully")

        except subprocess.TimeoutExpired:
            raise SketchCompilationError("Sketch compilation timed out after 5 minutes")
        except SketchCompilationError:
            raise
        except Exception as e:
            raise SketchCompilationError(f"Error compiling sketch: {e}") from e

    async def _upload_sketch(self) -> None:
        """Upload sketch to MCU.

        Raises:
            SketchUploadError: If upload fails
        """
        # Check if serial port exists
        if not Path(self.serial_port).exists():
            logger.warning(f"Serial port {self.serial_port} not found, skipping upload")
            raise SketchUploadError(f"Serial port not found: {self.serial_port}")

        try:
            logger.info(f"Uploading sketch to MCU via {self.serial_port}...")

            result = subprocess.run(
                [
                    "arduino-cli",
                    "upload",
                    "--fqbn",
                    self.fqbn,
                    "--port",
                    self.serial_port,
                    str(self.sketch_dir),
                ],
                capture_output=True,
                text=True,
                timeout=120,  # 2 minutes max
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise SketchUploadError(f"Upload failed: {error_msg}")

            logger.info("Sketch uploaded successfully")

        except subprocess.TimeoutExpired:
            raise SketchUploadError("Sketch upload timed out after 2 minutes")
        except SketchUploadError:
            raise
        except Exception as e:
            raise SketchUploadError(f"Error uploading sketch: {e}") from e
