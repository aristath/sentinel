"""Staged file deployment with atomic swaps."""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class DeploymentError(Exception):
    """Raised when deployment operations fail."""


class FileDeployer:
    """Space-efficient staged deployment with atomic swaps.

    Uses a single staging directory that is reused. On success, staging becomes
    the new deployment. On failure, staging is deleted.
    """

    def __init__(
        self,
        repo_dir: Path,
        deploy_dir: Path,
        staging_dir: Path,
        venv_dir: Path,
    ):
        """Initialize file deployer.

        Args:
            repo_dir: Path to Git repository
            deploy_dir: Path to current deployment directory
            staging_dir: Path to staging directory (reused)
            venv_dir: Path to virtual environment
        """
        self.repo_dir = repo_dir
        self.deploy_dir = deploy_dir
        self.staging_dir = staging_dir
        self.venv_dir = venv_dir

    def _cleanup_staging(self) -> None:
        """Remove staging directory if it exists."""
        if self.staging_dir.exists():
            try:
                logger.debug(f"Cleaning up staging directory: {self.staging_dir}")
                shutil.rmtree(self.staging_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up staging directory: {e}")

    async def deploy_to_staging(self, requirements_changed: bool = False) -> None:
        """Deploy code to staging directory.

        Args:
            requirements_changed: Whether requirements.txt changed

        Raises:
            DeploymentError: If deployment fails
        """
        try:
            # Clean up any existing staging directory
            self._cleanup_staging()

            # Create staging directory
            self.staging_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Deploying to staging: {self.staging_dir}")

            # Files/directories to copy (excluding venv, data, .git, node_modules)
            items_to_copy = [
                "app",
                "static",
                "scripts",
                "deploy",
                "requirements.txt",
            ]

            for item in items_to_copy:
                src = self.repo_dir / item
                if not src.exists():
                    logger.debug(f"Skipping {item} (not found in repo)")
                    continue

                dst = self.staging_dir / item
                try:
                    if src.is_dir():
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
                    logger.debug(f"Copied {item} to staging")
                except Exception as e:
                    raise DeploymentError(f"Failed to copy {item}: {e}") from e

            # Clean up __pycache__ directories
            logger.debug("Cleaning up __pycache__ directories...")
            for pycache_dir in self.staging_dir.rglob("__pycache__"):
                shutil.rmtree(pycache_dir, ignore_errors=True)
            for pyc_file in self.staging_dir.rglob("*.pyc"):
                pyc_file.unlink(missing_ok=True)

            # Update dependencies if requirements changed
            if requirements_changed:
                await self._update_dependencies()

            logger.info("Staging deployment complete")

        except DeploymentError:
            raise
        except Exception as e:
            self._cleanup_staging()
            raise DeploymentError(f"Error deploying to staging: {e}") from e

    async def _update_dependencies(self) -> None:
        """Update Python dependencies in staging.

        Raises:
            DeploymentError: If dependency update fails
        """
        if not self.venv_dir.exists():
            logger.warning(f"Virtual environment not found: {self.venv_dir}")
            raise DeploymentError(f"Virtual environment not found: {self.venv_dir}")

        requirements_file = self.staging_dir / "requirements.txt"
        if not requirements_file.exists():
            logger.warning("requirements.txt not found in staging")
            raise DeploymentError("requirements.txt not found in staging")

        try:
            # Use venv Python to install requirements
            venv_python = self.venv_dir / "bin" / "python"
            if not venv_python.exists():
                raise DeploymentError(f"Python not found in venv: {venv_python}")

            logger.info("Updating Python dependencies...")
            result = subprocess.run(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    str(requirements_file),
                ],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes max
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise DeploymentError(f"Failed to install dependencies: {error_msg}")

            logger.info("Dependencies updated successfully")

        except subprocess.TimeoutExpired:
            raise DeploymentError(
                "Dependency update timed out after 5 minutes"
            ) from None
        except DeploymentError:
            raise
        except Exception as e:
            raise DeploymentError(f"Error updating dependencies: {e}") from e

    def verify_staging(self) -> None:
        """Verify staging directory is valid.

        Raises:
            DeploymentError: If staging is invalid
        """
        # Check that essential directories exist
        required_dirs = ["app"]
        for dir_name in required_dirs:
            if not (self.staging_dir / dir_name).exists():
                raise DeploymentError(
                    f"Required directory missing in staging: {dir_name}"
                )

        # Check that main.py exists
        if not (self.staging_dir / "app" / "main.py").exists():
            raise DeploymentError("app/main.py missing in staging")

        logger.debug("Staging verification passed")

    async def atomic_swap(self) -> None:
        """Atomically swap staging to deployment.

        Preserves venv, data, .env and other important directories.
        Only replaces code files from staging.

        Safety measures:
        1. Creates backups of data and .env before deployment
        2. Validates staging doesn't contain preserved items
        3. Skips preserved items when copying from staging
        4. Verifies preserved items exist after deployment, restores from backup if missing

        Raises:
            DeploymentError: If swap fails
        """
        # Critical items that must be backed up and preserved
        critical_items = ["data", ".env"]
        preserve_items = ["venv", "data", ".env", ".git"]
        preserved = {}
        backups = {}

        try:
            if not self.deploy_dir.exists():
                # First deployment - just move staging
                logger.info(f"First deployment - moving staging to: {self.deploy_dir}")
                shutil.move(str(self.staging_dir), str(self.deploy_dir))
                logger.info("Atomic swap completed successfully")
                return

            # Step 1: Create backups of critical items before deployment
            logger.info("Creating backups of critical items (data, .env)...")
            for critical_item in critical_items:
                item_path = self.deploy_dir / critical_item
                if item_path.exists():
                    backup_path = self.deploy_dir.parent / f".{critical_item}.backup"
                    # Remove old backup if exists
                    if backup_path.exists():
                        if backup_path.is_dir():
                            shutil.rmtree(backup_path)
                        else:
                            backup_path.unlink()

                    try:
                        if item_path.is_dir():
                            shutil.copytree(str(item_path), str(backup_path))
                        else:
                            shutil.copy2(str(item_path), str(backup_path))
                        backups[critical_item] = backup_path
                        logger.info(
                            f"Created backup of {critical_item} at {backup_path}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to create backup of {critical_item}: {e}")
                        raise DeploymentError(
                            f"Failed to create backup of {critical_item}: {e}"
                        ) from e

            # Step 2: Validate staging doesn't contain preserved items
            logger.info(
                "Validating staging directory doesn't contain preserved items..."
            )
            for preserved_item in preserve_items:
                staging_item = self.staging_dir / preserved_item
                if staging_item.exists():
                    raise DeploymentError(
                        f"Staging directory contains preserved item '{preserved_item}'. "
                        "This should never happen - staging should only contain code files."
                    )
            logger.debug("Staging validation passed - no preserved items found")

            # Step 3: Preserve important directories/files
            logger.info(f"Preserving important directories in {self.deploy_dir}...")
            for preserved_item in preserve_items:
                item_path = self.deploy_dir / preserved_item
                if item_path.exists():
                    # Create temp location for preserved item
                    temp_path = self.deploy_dir.parent / f".{preserved_item}.preserve"
                    if temp_path.exists():
                        (
                            shutil.rmtree(temp_path)
                            if temp_path.is_dir()
                            else temp_path.unlink()
                        )

                    try:
                        if item_path.is_dir():
                            shutil.move(str(item_path), str(temp_path))
                        else:
                            shutil.copy2(str(item_path), str(temp_path))
                        preserved[preserved_item] = temp_path
                        logger.info(f"Preserved {preserved_item} to {temp_path}")
                    except Exception as e:
                        logger.error(f"Failed to preserve {preserved_item}: {e}")
                        # Rollback: restore any already preserved items
                        for (
                            already_preserved_name,
                            already_temp_path,
                        ) in preserved.items():
                            try:
                                restore_dst = self.deploy_dir / already_preserved_name
                                if already_temp_path.is_dir():
                                    shutil.move(
                                        str(already_temp_path), str(restore_dst)
                                    )
                                else:
                                    shutil.copy2(
                                        str(already_temp_path), str(restore_dst)
                                    )
                                    already_temp_path.unlink()
                            except Exception:
                                pass
                        raise DeploymentError(
                            f"Failed to preserve {preserved_item}: {e}"
                        ) from e

            # Step 4: Remove old code files (but keep preserved items)
            logger.info(f"Removing old code files from {self.deploy_dir}...")
            for item_path in self.deploy_dir.iterdir():
                item: Path = item_path
                if item.name not in preserve_items:
                    try:
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to remove {item.name}: {e}")

            # Step 5: Copy new code files from staging (skip preserved items)
            logger.info("Copying new code files from staging...")
            for staging_item_path in self.staging_dir.iterdir():
                staging_path: Path = staging_item_path
                # Skip preserved items - they should never be in staging, but double-check
                if staging_path.name in preserve_items:
                    logger.warning(
                        f"Skipping preserved item '{staging_path.name}' in staging "
                        "(this should not happen)"
                    )
                    continue

                dst = self.deploy_dir / staging_path.name
                try:
                    if staging_path.is_dir():
                        shutil.copytree(staging_path, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(staging_path, dst)
                    logger.debug(f"Copied {staging_path.name} from staging")
                except Exception as e:
                    logger.error(f"Failed to copy {staging_path.name}: {e}")
                    raise DeploymentError(
                        f"Failed to copy {staging_path.name} from staging: {e}"
                    ) from e

            # Step 6: Restore preserved items
            logger.info("Restoring preserved directories...")
            for preserved_item_name, temp_path in preserved.items():
                dst = self.deploy_dir / preserved_item_name
                try:
                    if temp_path.is_dir():
                        shutil.move(str(temp_path), str(dst))
                    else:
                        shutil.copy2(str(temp_path), str(dst))
                        temp_path.unlink()
                    logger.info(f"Restored {preserved_item_name}")
                except Exception as e:
                    logger.error(f"Failed to restore {preserved_item_name}: {e}")
                    raise DeploymentError(
                        f"Failed to restore {preserved_item_name}: {e}"
                    ) from e

            # Step 7: Verify critical items exist after deployment, restore from backup if missing
            logger.info("Verifying critical items exist after deployment...")
            for critical_item in critical_items:
                item_path = self.deploy_dir / critical_item
                if not item_path.exists():
                    logger.error(
                        f"CRITICAL: {critical_item} is missing after deployment! "
                        "Restoring from backup..."
                    )
                    if critical_item not in backups:
                        raise DeploymentError(
                            f"CRITICAL: {critical_item} is missing and no backup exists!"
                        )

                    backup_path = backups[critical_item]
                    try:
                        if backup_path.is_dir():
                            shutil.copytree(str(backup_path), str(item_path))
                        else:
                            shutil.copy2(str(backup_path), str(item_path))
                        logger.info(f"Restored {critical_item} from backup")
                    except Exception as e:
                        raise DeploymentError(
                            f"CRITICAL: Failed to restore {critical_item} from backup: {e}"
                        ) from e
                else:
                    logger.debug(f"Verified {critical_item} exists after deployment")

            # Clean up staging
            self._cleanup_staging()

            # Clean up backups (they're no longer needed)
            logger.info("Cleaning up backup files...")
            for backup_path in backups.values():
                try:
                    if backup_path.exists():
                        if backup_path.is_dir():
                            shutil.rmtree(backup_path)
                        else:
                            backup_path.unlink()
                        logger.debug(f"Removed backup {backup_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove backup {backup_path}: {e}")

            # Ensure venv exists after swap
            if not self.venv_dir.exists():
                logger.warning(
                    f"Virtual environment missing after swap: {self.venv_dir}. "
                    "It will need to be recreated manually."
                )

            logger.info("Atomic swap completed successfully")

        except DeploymentError:
            # Re-raise deployment errors
            raise
        except Exception as e:
            # Clean up staging and any preserved items on failure
            self._cleanup_staging()
            for temp_path in self.deploy_dir.parent.glob(".*.preserve"):
                try:
                    if temp_path.is_dir():
                        shutil.rmtree(temp_path)
                    else:
                        temp_path.unlink()
                except Exception:
                    pass

            # Try to restore critical items from backup if deployment failed
            logger.error(
                "Deployment failed - attempting to restore critical items from backup..."
            )
            for critical_item in critical_items:
                backup_path = self.deploy_dir.parent / f".{critical_item}.backup"
                if backup_path.exists():
                    item_path = self.deploy_dir / critical_item
                    if not item_path.exists():
                        try:
                            logger.info(f"Restoring {critical_item} from backup...")
                            if backup_path.is_dir():
                                shutil.copytree(str(backup_path), str(item_path))
                            else:
                                shutil.copy2(str(backup_path), str(item_path))
                            logger.info(f"Restored {critical_item} from backup")
                        except Exception as restore_error:
                            logger.error(
                                f"Failed to restore {critical_item} from backup: {restore_error}"
                            )

            raise DeploymentError(f"Error during atomic swap: {e}") from e

    def get_staging_size_mb(self) -> float:
        """Get size of staging directory in MB.

        Returns:
            Size in MB
        """
        if not self.staging_dir.exists():
            return 0.0

        total_size = 0
        for file_path in self.staging_dir.rglob("*"):
            if file_path.is_file():
                try:
                    total_size += file_path.stat().st_size
                except (OSError, FileNotFoundError):
                    pass

        return total_size / (1024 * 1024)
