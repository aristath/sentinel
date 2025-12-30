"""Auto-deploy job.

Runs the auto-deploy script at configured intervals to check for updates
and deploy changes from GitHub.
"""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to the auto-deploy script
AUTO_DEPLOY_SCRIPT = Path("/home/arduino/bin/auto-deploy.sh")


async def run_auto_deploy():
    """Run the auto-deploy script to check for updates and deploy changes."""
    if not AUTO_DEPLOY_SCRIPT.exists():
        logger.warning(f"Auto-deploy script not found at {AUTO_DEPLOY_SCRIPT}")
        return

    try:
        logger.info("Running auto-deploy check...")
        # Run the script in a subprocess
        process = await asyncio.create_subprocess_exec(
            str(AUTO_DEPLOY_SCRIPT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            if stdout:
                logger.info(f"Auto-deploy completed: {stdout.decode().strip()}")
        else:
            logger.error(
                f"Auto-deploy failed with exit code {process.returncode}: "
                f"{stderr.decode().strip() if stderr else 'No error output'}"
            )
    except Exception as e:
        logger.error(f"Error running auto-deploy script: {e}", exc_info=True)
