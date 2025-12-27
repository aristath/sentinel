"""Tests for settings repository.

These tests validate settings CRUD operations with type conversions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSettingsRepositoryGet:
    """Test settings get operations."""

    @pytest.mark.asyncio
    async def test_get_existing_key(self):
        """Test getting an existing setting."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value={"value": "test_value"})

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get("test_key")

        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Test getting a non-existent setting."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get("nonexistent")

        assert result is None


class TestSettingsRepositorySet:
    """Test settings set operations."""

    @pytest.mark.asyncio
    async def test_set_with_description(self):
        """Test setting a value with description."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            await repo.set("test_key", "test_value", description="Test description")

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_without_description(self):
        """Test setting a value without description."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            await repo.set("test_key", "test_value")

        mock_db.execute.assert_called_once()


class TestSettingsRepositoryGetAll:
    """Test getting all settings."""

    @pytest.mark.asyncio
    async def test_get_all(self):
        """Test getting all settings."""
        from app.repositories.settings import SettingsRepository

        mock_rows = [
            {"key": "setting1", "value": "value1"},
            {"key": "setting2", "value": "value2"},
        ]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=mock_rows)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get_all()

        assert result == {"setting1": "value1", "setting2": "value2"}


class TestSettingsRepositoryTypedGetters:
    """Test typed getter methods."""

    @pytest.mark.asyncio
    async def test_get_float_valid(self):
        """Test getting a valid float value."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value={"value": "3.14"})

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get_float("pi")

        assert result == 3.14

    @pytest.mark.asyncio
    async def test_get_float_default(self):
        """Test getting float with default when key not found."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get_float("missing", default=1.5)

        assert result == 1.5

    @pytest.mark.asyncio
    async def test_get_float_invalid(self):
        """Test getting float with invalid value returns default."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value={"value": "not_a_number"})

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get_float("invalid", default=2.0)

        assert result == 2.0

    @pytest.mark.asyncio
    async def test_get_int_valid(self):
        """Test getting a valid int value."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value={"value": "42"})

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get_int("answer")

        assert result == 42

    @pytest.mark.asyncio
    async def test_get_int_from_float_string(self):
        """Test getting int from float string (e.g., '12.0')."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value={"value": "12.0"})

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get_int("number")

        assert result == 12

    @pytest.mark.asyncio
    async def test_get_int_default(self):
        """Test getting int with default when key not found."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get_int("missing", default=10)

        assert result == 10

    @pytest.mark.asyncio
    async def test_get_int_invalid(self):
        """Test getting int with invalid value returns default."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value={"value": "not_a_number"})

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get_int("invalid", default=5)

        assert result == 5

    @pytest.mark.asyncio
    async def test_get_bool_true_values(self):
        """Test getting boolean true values."""
        from app.repositories.settings import SettingsRepository

        for true_value in ["true", "1", "yes", "on", "TRUE", "True"]:
            mock_db = AsyncMock()
            mock_db.fetchone = AsyncMock(return_value={"value": true_value})

            with patch(
                "app.repositories.settings.get_db_manager"
            ) as mock_get_db:
                mock_manager = MagicMock()
                mock_manager.config = mock_db
                mock_get_db.return_value = mock_manager

                repo = SettingsRepository()
                result = await repo.get_bool("flag")

            assert result is True, f"Expected True for '{true_value}'"

    @pytest.mark.asyncio
    async def test_get_bool_false_values(self):
        """Test getting boolean false values."""
        from app.repositories.settings import SettingsRepository

        for false_value in ["false", "0", "no", "off", "other"]:
            mock_db = AsyncMock()
            mock_db.fetchone = AsyncMock(return_value={"value": false_value})

            with patch(
                "app.repositories.settings.get_db_manager"
            ) as mock_get_db:
                mock_manager = MagicMock()
                mock_manager.config = mock_db
                mock_get_db.return_value = mock_manager

                repo = SettingsRepository()
                result = await repo.get_bool("flag")

            assert result is False, f"Expected False for '{false_value}'"

    @pytest.mark.asyncio
    async def test_get_bool_default(self):
        """Test getting bool with default when key not found."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            result = await repo.get_bool("missing", default=True)

        assert result is True


class TestSettingsRepositoryTypedSetters:
    """Test typed setter methods."""

    @pytest.mark.asyncio
    async def test_set_float(self):
        """Test setting a float value."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            await repo.set_float("pi", 3.14)

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_int(self):
        """Test setting an int value."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            await repo.set_int("count", 42)

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_bool_true(self):
        """Test setting a boolean true value."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            await repo.set_bool("enabled", True)

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_bool_false(self):
        """Test setting a boolean false value."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            await repo.set_bool("enabled", False)

        mock_db.execute.assert_called_once()


class TestSettingsRepositoryDelete:
    """Test settings delete operations."""

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting a setting."""
        from app.repositories.settings import SettingsRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.repositories.settings.get_db_manager"
        ) as mock_get_db:
            mock_manager = MagicMock()
            mock_manager.config = mock_db
            mock_get_db.return_value = mock_manager

            repo = SettingsRepository()
            await repo.delete("test_key")

        mock_db.execute.assert_called_once()
