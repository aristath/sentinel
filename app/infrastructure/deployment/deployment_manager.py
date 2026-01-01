"""Deployment manager orchestrates the deployment process."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.infrastructure.deployment.file_deployer import DeploymentError, FileDeployer
from app.infrastructure.deployment.git_checker import (
    GitChecker,
    GitFetchError,
    GitPullError,
)
from app.infrastructure.deployment.go_evaluator_deployer import (
    GoDeploymentError,
    GoEvaluatorDeployer,
)
from app.infrastructure.deployment.service_manager import (
    HealthCheckError,
    ServiceManager,
    ServiceRestartError,
)
from app.infrastructure.deployment.sketch_deployer import (
    SketchCompilationError,
    SketchDeployer,
    SketchUploadError,
)

logger = logging.getLogger(__name__)


@dataclass
class DeploymentResult:
    """Result of a deployment attempt."""

    success: bool
    deployed: bool  # Whether deployment actually happened (vs no changes)
    commit_before: Optional[str] = None
    commit_after: Optional[str] = None
    error: Optional[str] = None
    sketch_deployed: bool = False
    go_evaluator_deployed: bool = False
    duration_seconds: float = 0.0


class DeploymentManager:
    """Orchestrates the deployment process."""

    def __init__(
        self,
        repo_dir: Path,
        deploy_dir: Path,
        staging_dir: Path,
        venv_dir: Path,
        service_name: str = "arduino-trader",
        api_url: str = "http://localhost:8000",
    ):
        """Initialize deployment manager.

        Args:
            repo_dir: Path to Git repository
            deploy_dir: Path to current deployment directory
            staging_dir: Path to staging directory (reused)
            venv_dir: Path to virtual environment
            service_name: Name of systemd service
            api_url: Base URL for API health checks
        """
        self.repo_dir = repo_dir
        self.deploy_dir = deploy_dir
        self.staging_dir = staging_dir
        self.venv_dir = venv_dir
        self.service_name = service_name

        # Initialize components
        self.git_checker = GitChecker(repo_dir)
        self.file_deployer = FileDeployer(repo_dir, deploy_dir, staging_dir, venv_dir)
        self.service_manager = ServiceManager(service_name, api_url)

        # Sketch deployer (only initialized if sketch directory exists)
        sketch_dir = repo_dir / "arduino-app" / "sketch"
        if sketch_dir.exists():
            self.sketch_deployer: Optional[SketchDeployer] = SketchDeployer(sketch_dir)
        else:
            self.sketch_deployer = None

        # Go evaluator deployer
        self.go_evaluator_deployer = GoEvaluatorDeployer(repo_dir)

    async def deploy(self) -> DeploymentResult:
        """Run deployment process.

        Returns:
            DeploymentResult with deployment status
        """
        start_time = datetime.now()
        result = DeploymentResult(success=False, deployed=False)

        try:
            logger.info("Starting deployment check...")

            # Step 1: Fetch updates from remote
            try:
                await self.git_checker.fetch_updates()
            except GitFetchError as e:
                result.error = f"Failed to fetch updates: {e}"
                logger.error(result.error)
                return result

            # Step 2: Check for changes
            has_changes, local_commit, remote_commit = self.git_checker.has_changes()
            result.commit_before = local_commit

            if not has_changes:
                logger.info("No changes detected - deployment not needed")
                result.success = True
                result.deployed = False
                return result

            if local_commit and remote_commit:
                logger.info(
                    f"Changes detected: {local_commit[:8]} -> {remote_commit[:8]}"
                )

            # Step 3: Get changed files and categorize
            if not local_commit or not remote_commit:
                result.error = "Could not determine commit hashes"
                logger.error(result.error)
                return result

            changed_files = self.git_checker.get_changed_files(
                local_commit, remote_commit
            )
            categories = self.git_checker.categorize_changes(changed_files)

            logger.info(
                f"Change categories: main_app={categories['main_app']}, "
                f"sketch={categories['sketch']}, requirements={categories['requirements']}"
            )

            # Step 4: Pull changes
            branch = self.git_checker.get_current_branch()
            if not branch:
                result.error = "Could not determine current branch"
                logger.error(result.error)
                return result

            try:
                await self.git_checker.pull_changes(branch)
            except GitPullError as e:
                result.error = f"Failed to pull changes: {e}"
                logger.error(result.error)
                return result

            # Step 5: Deploy main app if changed
            if categories["main_app"]:
                try:
                    await self.file_deployer.deploy_to_staging(
                        requirements_changed=categories["requirements"]
                    )
                    self.file_deployer.verify_staging()
                    await self.file_deployer.atomic_swap()
                    logger.info("Main app deployed successfully")

                    # Ensure venv exists after deployment
                    if not self.venv_dir.exists():
                        logger.warning(
                            f"Virtual environment missing: {self.venv_dir}. "
                            "It will need to be recreated manually."
                        )

                    # Step 6: Restart service
                    try:
                        await self.service_manager.restart_service()
                        await self.service_manager.check_health()
                        logger.info("Service restarted and health check passed")
                    except (ServiceRestartError, HealthCheckError) as e:
                        result.error = f"Service restart/health check failed: {e}"
                        logger.error(result.error)
                        # Deployment succeeded but service failed - this is a partial failure
                        # We'll mark it as success=False but deployed=True
                        result.deployed = True
                        return result

                except DeploymentError as e:
                    result.error = f"Deployment failed: {e}"
                    logger.error(result.error)
                    return result

            # Step 7: Deploy sketch if changed
            if categories["sketch"] and self.sketch_deployer:
                try:
                    logger.info("Sketch files changed - compiling and uploading...")
                    await self.sketch_deployer.compile_and_upload()
                    result.sketch_deployed = True
                    logger.info("Sketch deployed successfully")
                except (SketchCompilationError, SketchUploadError) as e:
                    # Sketch deployment failure is non-fatal
                    logger.warning(f"Sketch deployment failed (non-fatal): {e}")
                    result.error = f"Main app deployed but sketch failed: {e}"

            # Step 8: Deploy Go evaluator if changed
            if categories["go_evaluator"]:
                try:
                    logger.info("Go evaluator files changed - deploying binary...")
                    await self.go_evaluator_deployer.deploy()
                    result.go_evaluator_deployed = True
                    logger.info("Go evaluator deployed successfully")
                except GoDeploymentError as e:
                    # Go deployment failure is non-fatal
                    logger.warning(f"Go evaluator deployment failed (non-fatal): {e}")
                    if result.error:
                        result.error += f"; Go evaluator: {e}"
                    else:
                        result.error = f"Go evaluator deployment failed: {e}"

            # Get final commit
            _, _, final_commit = self.git_checker.has_changes()
            result.commit_after = final_commit or remote_commit

            result.success = True
            result.deployed = True
            duration = (datetime.now() - start_time).total_seconds()
            result.duration_seconds = duration

            before_hash = (
                result.commit_before[:8] if result.commit_before else "unknown"
            )
            after_hash = result.commit_after[:8] if result.commit_after else "unknown"
            logger.info(
                f"Deployment completed successfully in {duration:.1f}s - "
                f"commit {before_hash} -> {after_hash}"
            )

            return result

        except Exception as e:
            result.error = f"Unexpected error during deployment: {e}"
            logger.error(result.error, exc_info=True)
            return result

    def get_deployment_status(self) -> dict:
        """Get current deployment status.

        Returns:
            Dictionary with deployment status information
        """
        try:
            has_changes, local_commit, remote_commit = self.git_checker.has_changes()
            service_status = self.service_manager.get_service_status()

            return {
                "repo_dir": str(self.repo_dir),
                "deploy_dir": str(self.deploy_dir),
                "has_changes": has_changes,
                "local_commit": local_commit[:8] if local_commit else None,
                "remote_commit": remote_commit[:8] if remote_commit else None,
                "service_status": service_status,
                "staging_exists": self.staging_dir.exists(),
            }
        except Exception as e:
            logger.error(f"Error getting deployment status: {e}", exc_info=True)
            return {
                "error": str(e),
            }
