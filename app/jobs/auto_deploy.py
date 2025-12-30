"""Auto-deploy job.

Checks for updates from GitHub and deploys changes automatically.
Uses Python-based deployment infrastructure for better reliability.
"""

import logging
from pathlib import Path

from app.infrastructure.deployment.deployment_manager import DeploymentManager
from app.infrastructure.locking import file_lock

logger = logging.getLogger(__name__)

# Deployment paths
REPO_DIR = Path("/home/arduino/repos/autoTrader")
DEPLOY_DIR = Path("/home/arduino/arduino-trader")
STAGING_DIR = Path("/home/arduino/arduino-trader-staging")
VENV_DIR = DEPLOY_DIR / "venv"
SERVICE_NAME = "arduino-trader"


async def run_auto_deploy():
    """Run auto-deployment check and deploy if changes are detected.

    Uses file-based locking to prevent concurrent deployments.
    """
    # Acquire deployment lock (5 minute timeout)
    try:
        async with file_lock("auto_deploy", timeout=300.0):
            await _run_auto_deploy_internal()
    except TimeoutError:
        logger.warning(
            "Could not acquire deployment lock - another deployment may be in progress"
        )
    except Exception as e:
        logger.error(f"Error during deployment: {e}", exc_info=True)


async def _run_auto_deploy_internal():
    """Internal deployment logic (called with lock held)."""
    # Verify paths exist
    if not REPO_DIR.exists():
        logger.error(f"Repository directory not found: {REPO_DIR}")
        return

    if not DEPLOY_DIR.exists():
        logger.warning(
            f"Deployment directory not found: {DEPLOY_DIR} (will be created)"
        )

    # Initialize deployment manager
    manager = DeploymentManager(
        repo_dir=REPO_DIR,
        deploy_dir=DEPLOY_DIR,
        staging_dir=STAGING_DIR,
        venv_dir=VENV_DIR,
        service_name=SERVICE_NAME,
    )

    # Run deployment
    result = await manager.deploy()

    # Log results
    if result.success:
        if result.deployed:
            logger.info(
                f"Deployment successful: {result.commit_before[:8] if result.commit_before else 'unknown'} -> "
                f"{result.commit_after[:8] if result.commit_after else 'unknown'} "
                f"({result.duration_seconds:.1f}s)"
            )
            if result.sketch_deployed:
                logger.info("Sketch also deployed successfully")
        else:
            logger.debug("No changes to deploy")
    else:
        logger.error(f"Deployment failed: {result.error}")
