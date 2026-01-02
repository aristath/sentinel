"""Git operations for checking and fetching updates."""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GitFetchError(Exception):
    """Raised when Git fetch fails."""


class GitPullError(Exception):
    """Raised when Git pull fails."""


class GitChecker:
    """Check for Git updates and get changed files."""

    def __init__(self, repo_dir: Path):
        """Initialize Git checker.

        Args:
            repo_dir: Path to Git repository
        """
        self.repo_dir = repo_dir
        self._ensure_git_safe_directory()

    def _ensure_git_safe_directory(self) -> None:
        """Ensure git safe directory is configured for this repo."""
        try:
            # Check if already configured
            result = subprocess.run(
                ["git", "config", "--global", "--get-all", "safe.directory"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if str(self.repo_dir) in result.stdout:
                return  # Already configured

            # Add to safe directories
            subprocess.run(
                [
                    "git",
                    "config",
                    "--global",
                    "--add",
                    "safe.directory",
                    str(self.repo_dir),
                ],
                capture_output=True,
                timeout=5,
            )
            logger.debug(f"Configured git safe directory: {self.repo_dir}")
        except Exception as e:
            logger.warning(f"Could not configure git safe directory: {e}")

    async def fetch_updates(self, max_retries: int = 3) -> None:
        """Fetch latest changes from remote.

        Args:
            max_retries: Maximum number of retry attempts

        Raises:
            GitFetchError: If fetch fails after retries
        """
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Fetching updates from remote (attempt {attempt}/{max_retries})..."
                )
                result = subprocess.run(
                    ["git", "fetch", "origin"],
                    cwd=self.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    logger.info("Successfully fetched updates from remote")
                    return
                else:
                    last_error = result.stderr or result.stdout
                    logger.warning(
                        f"Git fetch failed (attempt {attempt}): {last_error}"
                    )

            except subprocess.TimeoutExpired:
                last_error = "Git fetch timed out after 30 seconds"
                logger.warning(f"Git fetch timed out (attempt {attempt})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Error during git fetch (attempt {attempt}): {e}")

            if attempt < max_retries:
                wait_time = 2**attempt  # Exponential backoff: 2s, 4s, 8s
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

        raise GitFetchError(
            f"Failed to fetch updates after {max_retries} attempts: {last_error}"
        )

    def get_current_branch(self) -> Optional[str]:
        """Get current branch name.

        Returns:
            Branch name or None if error
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                logger.debug(f"Current branch: {branch}")
                return branch
            logger.warning("Could not determine current branch")
            return None
        except Exception as e:
            logger.error(f"Error getting current branch: {e}")
            return None

    def has_changes(self) -> tuple[bool, Optional[str], Optional[str]]:
        """Check if there are changes between local and remote.

        Returns:
            Tuple of (has_changes, local_commit, remote_commit)
            Returns (False, None, None) on error
        """
        try:
            branch = self.get_current_branch()
            if not branch:
                return False, None, None

            # Get local commit
            local_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if local_result.returncode != 0:
                logger.warning("Could not get local commit")
                return False, None, None

            local_commit = local_result.stdout.strip()

            # Get remote commit (try origin/branch first, then origin/main)
            remote_result = subprocess.run(
                ["git", "rev-parse", f"origin/{branch}"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if remote_result.returncode != 0:
                # Try origin/main as fallback
                remote_result = subprocess.run(
                    ["git", "rev-parse", "origin/main"],
                    cwd=self.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if remote_result.returncode != 0:
                    logger.warning("Could not get remote commit")
                    return False, None, None

            remote_commit = remote_result.stdout.strip()
            has_changes = local_commit != remote_commit

            if has_changes:
                logger.info(
                    f"Changes detected: local {local_commit[:8]} -> remote {remote_commit[:8]}"
                )
            else:
                logger.debug(
                    f"No changes: local {local_commit[:8]} == remote {remote_commit[:8]}"
                )

            return has_changes, local_commit, remote_commit

        except Exception as e:
            logger.error(f"Error checking for changes: {e}", exc_info=True)
            return False, None, None

    def get_changed_files(self, from_commit: str, to_commit: str) -> list[str]:
        """Get list of changed files between two commits.

        Args:
            from_commit: Starting commit
            to_commit: Ending commit

        Returns:
            List of changed file paths (relative to repo root)
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", from_commit, to_commit],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning(f"Git diff failed: {result.stderr}")
                return []

            files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            logger.debug(f"Changed files: {len(files)} files")
            return files

        except Exception as e:
            logger.error(f"Error getting changed files: {e}", exc_info=True)
            return []

    def categorize_changes(self, files: list[str]) -> dict[str, bool]:
        """Categorize changed files.

        Args:
            files: List of changed file paths

        Returns:
            Dictionary with categories: main_app, sketch, requirements, deploy_script, go_evaluator
        """
        categories = {
            "main_app": False,
            "sketch": False,
            "requirements": False,
            "deploy_script": False,
            "go_evaluator": False,
        }

        for file in files:
            # Main app changes
            if (
                file.startswith("app/")
                or file.startswith("static/")
                or file.startswith("scripts/")
                or file.startswith("deploy/")
                or file == "requirements.txt"
                or file.endswith(".py")
            ):
                categories["main_app"] = True
                if file == "requirements.txt":
                    categories["requirements"] = True

            # Sketch changes
            if file.startswith("arduino-app/sketch/"):
                categories["sketch"] = True

            # Deploy script changes (legacy bash script)
            if file == "arduino-app/deploy/auto-deploy.sh":
                categories["deploy_script"] = True

            # Go evaluator service changes
            if file.startswith("services/evaluator-go/"):
                categories["go_evaluator"] = True

        return categories

    async def pull_changes(self, branch: str, max_retries: int = 3) -> None:
        """Pull latest changes from remote.

        Args:
            branch: Branch name to pull
            max_retries: Maximum number of retry attempts

        Raises:
            GitPullError: If pull fails after retries
        """
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Pulling changes from origin/{branch} (attempt {attempt}/{max_retries})..."
                )

                # Reset any local changes first
                reset_result = subprocess.run(
                    ["git", "reset", "--hard", "HEAD"],
                    cwd=self.repo_dir,
                    capture_output=True,
                    timeout=10,
                )
                if reset_result.returncode != 0:
                    error_msg = (
                        reset_result.stderr.decode()
                        if reset_result.stderr
                        else "Unknown error"
                    )
                    logger.warning(f"Git reset failed: {error_msg}")

                # Clean untracked files
                clean_result = subprocess.run(
                    ["git", "clean", "-fd"],
                    cwd=self.repo_dir,
                    capture_output=True,
                    timeout=10,
                )
                if clean_result.returncode != 0:
                    error_msg = (
                        clean_result.stderr.decode()
                        if clean_result.stderr
                        else "Unknown error"
                    )
                    logger.warning(f"Git clean failed: {error_msg}")

                # Pull changes
                result = subprocess.run(
                    ["git", "pull", "origin", branch],
                    cwd=self.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    logger.info(f"Successfully pulled changes from origin/{branch}")
                    return
                else:
                    last_error = result.stderr or result.stdout
                    logger.warning(f"Git pull failed (attempt {attempt}): {last_error}")

            except subprocess.TimeoutExpired:
                last_error = "Git pull timed out after 60 seconds"
                logger.warning(f"Git pull timed out (attempt {attempt})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Error during git pull (attempt {attempt}): {e}")

            if attempt < max_retries:
                wait_time = 2**attempt  # Exponential backoff: 2s, 4s, 8s
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

        raise GitPullError(
            f"Failed to pull changes after {max_retries} attempts: {last_error}"
        )
