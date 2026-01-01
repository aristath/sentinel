"""Unit tests for PlannerConfigService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.planning.domain.planner_config import (
    PlannerConfig,
    PlannerConfigHistory,
)
from app.modules.planning.services.planner_config_service import PlannerConfigService


@pytest.fixture
def mock_repository():
    """Create a mock planner config repository."""
    repo = MagicMock()
    repo.get_all = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_bucket = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.get_history = AsyncMock()
    return repo


@pytest.fixture
def service(mock_repository):
    """Create a PlannerConfigService with mocked repository."""
    service = PlannerConfigService()
    service.repository = mock_repository
    return service


@pytest.fixture
def sample_toml():
    """Sample valid TOML configuration."""
    return """
[planner]
name = "Test Planner"

[[calculators]]
name = "momentum"
type = "momentum"
weight = 1.0
"""


@pytest.fixture
def invalid_toml():
    """Sample invalid TOML (missing closing bracket)."""
    return """
[planner
name = "Invalid"
"""


@pytest.fixture
def sample_config():
    """Sample PlannerConfig."""
    return PlannerConfig(
        id="test-id",
        name="Test Planner",
        toml_config="[planner]\nname = 'Test'",
        bucket_id="bucket-1",
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
    )


class TestValidateToml:
    """Tests for TOML validation."""

    @pytest.mark.asyncio
    async def test_valid_toml(self, service, sample_toml):
        """Test validation of valid TOML."""
        result = await service.validate_toml(sample_toml)

        assert result["valid"] is True
        assert result["error"] is None
        assert result["config"] is not None

    @pytest.mark.asyncio
    async def test_invalid_toml_syntax(self, service, invalid_toml):
        """Test validation of TOML with syntax errors."""
        result = await service.validate_toml(invalid_toml)

        assert result["valid"] is False
        assert "Invalid TOML syntax" in result["error"]
        assert result["config"] is None

    @pytest.mark.asyncio
    async def test_minimal_toml_structure(self, service):
        """Test validation accepts minimal TOML (validator is lenient)."""
        # Valid TOML syntax with minimal structure
        # Parser is lenient and uses defaults for missing sections
        minimal_structure = "[something]\nelse = 'value'"

        result = await service.validate_toml(minimal_structure)

        assert result["valid"] is True
        assert result["error"] is None
        assert result["config"] is not None  # Config created with defaults


class TestCreate:
    """Tests for creating planner configurations."""

    @pytest.mark.asyncio
    async def test_create_success(self, service, mock_repository, sample_toml):
        """Test successful creation of planner config."""
        mock_repository.create.return_value = PlannerConfig(
            id="new-id",
            name="Test Planner",
            toml_config=sample_toml,
            bucket_id="bucket-1",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )

        result = await service.create(
            name="Test Planner", toml_config=sample_toml, bucket_id="bucket-1"
        )

        assert result["success"] is True
        assert result["config"] is not None
        assert result["config"].name == "Test Planner"
        assert result["error"] is None
        mock_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_invalid_toml(self, service, invalid_toml):
        """Test creation with invalid TOML."""
        result = await service.create(
            name="Invalid Planner", toml_config=invalid_toml, bucket_id=None
        )

        assert result["success"] is False
        assert result["config"] is None
        assert "Invalid TOML syntax" in result["error"]

    @pytest.mark.asyncio
    async def test_create_template_no_bucket(
        self, service, mock_repository, sample_toml
    ):
        """Test creation of template config (no bucket_id)."""
        mock_repository.create.return_value = PlannerConfig(
            id="template-id",
            name="Template Planner",
            toml_config=sample_toml,
            bucket_id=None,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )

        result = await service.create(
            name="Template Planner", toml_config=sample_toml, bucket_id=None
        )

        assert result["success"] is True
        assert result["config"].bucket_id is None


class TestUpdate:
    """Tests for updating planner configurations."""

    @pytest.mark.asyncio
    async def test_update_success(
        self, service, mock_repository, sample_config, sample_toml
    ):
        """Test successful update of planner config."""
        updated_config = PlannerConfig(
            id=sample_config.id,
            name="Updated Name",
            toml_config=sample_toml,
            bucket_id=sample_config.bucket_id,
            created_at=sample_config.created_at,
            updated_at="2024-01-02T00:00:00",
        )
        mock_repository.update.return_value = updated_config

        result = await service.update(
            config_id=sample_config.id, name="Updated Name", toml_config=sample_toml
        )

        assert result["success"] is True
        assert result["config"].name == "Updated Name"
        assert result["error"] is None
        mock_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_invalid_toml(self, service, sample_config, invalid_toml):
        """Test update with invalid TOML."""
        result = await service.update(
            config_id=sample_config.id, toml_config=invalid_toml
        )

        assert result["success"] is False
        assert result["config"] is None
        assert "Invalid TOML syntax" in result["error"]

    @pytest.mark.asyncio
    async def test_update_not_found(self, service, mock_repository):
        """Test update of non-existent config."""
        mock_repository.update.return_value = None

        result = await service.update(config_id="nonexistent", name="New Name")

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_update_name_only(self, service, mock_repository, sample_config):
        """Test updating only the name."""
        updated_config = PlannerConfig(
            id=sample_config.id,
            name="New Name Only",
            toml_config=sample_config.toml_config,
            bucket_id=sample_config.bucket_id,
            created_at=sample_config.created_at,
            updated_at="2024-01-02T00:00:00",
        )
        mock_repository.update.return_value = updated_config

        result = await service.update(config_id=sample_config.id, name="New Name Only")

        assert result["success"] is True
        assert result["config"].name == "New Name Only"
        # Verify TOML validation was NOT called since toml_config is None
        mock_repository.update.assert_called_once_with(
            sample_config.id,
            name="New Name Only",
            toml_config=None,
            bucket_id=None,
            create_backup=True,
        )


class TestDelete:
    """Tests for deleting planner configurations."""

    @pytest.mark.asyncio
    async def test_delete_success(self, service, mock_repository, sample_config):
        """Test successful deletion."""
        mock_repository.delete.return_value = True

        result = await service.delete(sample_config.id)

        assert result["success"] is True
        assert result["error"] is None
        mock_repository.delete.assert_called_once_with(sample_config.id)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, service, mock_repository):
        """Test deletion of non-existent config."""
        mock_repository.delete.return_value = False

        result = await service.delete("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]


class TestGetHistory:
    """Tests for retrieving version history."""

    @pytest.mark.asyncio
    async def test_get_history(self, service, mock_repository):
        """Test retrieving version history."""
        history = [
            PlannerConfigHistory(
                id="hist-1",
                planner_config_id="config-1",
                name="Version 2",
                toml_config="[planner]\nname = 'v2'",
                saved_at="2024-01-02T00:00:00",
            ),
            PlannerConfigHistory(
                id="hist-2",
                planner_config_id="config-1",
                name="Version 1",
                toml_config="[planner]\nname = 'v1'",
                saved_at="2024-01-01T00:00:00",
            ),
        ]
        mock_repository.get_history.return_value = history

        result = await service.get_history("config-1")

        assert len(result) == 2
        assert result[0].name == "Version 2"
        assert result[1].name == "Version 1"
        mock_repository.get_history.assert_called_once_with("config-1")
