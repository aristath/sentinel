"""Tests for auto-deploy job.

These tests validate the auto-deploy script execution and error handling.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestRunAutoDeploy:
    """Test run_auto_deploy function."""

    @pytest.mark.asyncio
    async def test_runs_script_successfully(self):
        """Test successful execution of auto-deploy script."""
        from app.jobs.auto_deploy import run_auto_deploy

        mock_script_path = Path("/fake/path/auto-deploy.sh")
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"Deployment successful", b"")
        )
        mock_process.returncode = 0

        with patch("app.jobs.auto_deploy.AUTO_DEPLOY_SCRIPT", mock_script_path):
            with patch("pathlib.Path.exists", return_value=True):
                with patch(
                    "asyncio.create_subprocess_exec", return_value=mock_process
                ) as mock_subprocess:
                    await run_auto_deploy()

                    mock_subprocess.assert_called_once_with(
                        str(mock_script_path),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    mock_process.communicate.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_missing_script(self):
        """Test handling when script file does not exist."""
        from app.jobs.auto_deploy import run_auto_deploy

        mock_script_path = Path("/fake/path/auto-deploy.sh")

        with patch("app.jobs.auto_deploy.AUTO_DEPLOY_SCRIPT", mock_script_path):
            with patch("pathlib.Path.exists", return_value=False):
                # Should not raise, should just return
                await run_auto_deploy()

    @pytest.mark.asyncio
    async def test_handles_script_failure(self):
        """Test handling when script returns non-zero exit code."""
        from app.jobs.auto_deploy import run_auto_deploy

        mock_script_path = Path("/fake/path/auto-deploy.sh")
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"git pull failed: network error")
        )
        mock_process.returncode = 1

        with patch("app.jobs.auto_deploy.AUTO_DEPLOY_SCRIPT", mock_script_path):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                    # Should not raise, should handle error gracefully
                    await run_auto_deploy()

    @pytest.mark.asyncio
    async def test_logs_script_output_on_success(self):
        """Test that script output is logged on successful execution."""
        from app.jobs.auto_deploy import run_auto_deploy

        mock_script_path = Path("/fake/path/auto-deploy.sh")
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"Updated 3 files from repository", b"")
        )
        mock_process.returncode = 0

        with patch("app.jobs.auto_deploy.AUTO_DEPLOY_SCRIPT", mock_script_path):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                    with patch("app.jobs.auto_deploy.logger") as mock_logger:
                        await run_auto_deploy()

                        # Should log info about completion
                        mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_logs_error_on_script_failure(self):
        """Test that errors are logged when script fails."""
        from app.jobs.auto_deploy import run_auto_deploy

        mock_script_path = Path("/fake/path/auto-deploy.sh")
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Permission denied")
        )
        mock_process.returncode = 1

        with patch("app.jobs.auto_deploy.AUTO_DEPLOY_SCRIPT", mock_script_path):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                    with patch("app.jobs.auto_deploy.logger") as mock_logger:
                        await run_auto_deploy()

                        # Should log error
                        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_handles_exception_during_execution(self):
        """Test handling of exceptions during script execution."""
        from app.jobs.auto_deploy import run_auto_deploy

        mock_script_path = Path("/fake/path/auto-deploy.sh")

        with patch("app.jobs.auto_deploy.AUTO_DEPLOY_SCRIPT", mock_script_path):
            with patch("pathlib.Path.exists", return_value=True):
                with patch(
                    "asyncio.create_subprocess_exec", side_effect=OSError("No such file")
                ):
                    with patch("app.jobs.auto_deploy.logger") as mock_logger:
                        # Should not raise, should log error
                        await run_auto_deploy()

                        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_handles_empty_stdout_on_success(self):
        """Test handling when script succeeds but has no output."""
        from app.jobs.auto_deploy import run_auto_deploy

        mock_script_path = Path("/fake/path/auto-deploy.sh")
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch("app.jobs.auto_deploy.AUTO_DEPLOY_SCRIPT", mock_script_path):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                    # Should handle empty output gracefully
                    await run_auto_deploy()

    @pytest.mark.asyncio
    async def test_handles_empty_stderr_on_failure(self):
        """Test handling when script fails but has no error output."""
        from app.jobs.auto_deploy import run_auto_deploy

        mock_script_path = Path("/fake/path/auto-deploy.sh")
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 1

        with patch("app.jobs.auto_deploy.AUTO_DEPLOY_SCRIPT", mock_script_path):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                    with patch("app.jobs.auto_deploy.logger") as mock_logger:
                        await run_auto_deploy()

                        # Should log error with message about no error output
                        mock_logger.error.assert_called()
                        call_args = str(mock_logger.error.call_args)
                        assert "No error output" in call_args or "exit code" in call_args

    @pytest.mark.asyncio
    async def test_uses_correct_script_path(self):
        """Test that the correct script path is used."""
        from app.jobs.auto_deploy import AUTO_DEPLOY_SCRIPT, run_auto_deploy

        # Verify the path constant
        assert str(AUTO_DEPLOY_SCRIPT) == "/home/arduino/bin/auto-deploy.sh"

        mock_script_path = Path("/home/arduino/bin/auto-deploy.sh")
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"Success", b""))
        mock_process.returncode = 0

        with patch("app.jobs.auto_deploy.AUTO_DEPLOY_SCRIPT", mock_script_path):
            with patch("pathlib.Path.exists", return_value=True):
                with patch(
                    "asyncio.create_subprocess_exec", return_value=mock_process
                ) as mock_subprocess:
                    await run_auto_deploy()

                    # Verify script path is passed correctly
                    call_args = mock_subprocess.call_args[0]
                    assert str(call_args[0]) == str(mock_script_path)
