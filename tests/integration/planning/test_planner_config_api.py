"""Integration tests for planner configuration API endpoints."""

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.fixture
def sample_toml():
    """Sample valid TOML configuration for testing."""
    return """
[planner]
name = "Test Strategy"

[[calculators]]
name = "momentum"
type = "momentum"
weight = 1.0
"""


@pytest.fixture
def updated_toml():
    """Updated TOML configuration for testing."""
    return """
[planner]
name = "Updated Strategy"

[[calculators]]
name = "value"
type = "value"
weight = 1.5
"""


@pytest.fixture
def invalid_toml():
    """Invalid TOML for testing validation."""
    return """
[planner
name = "Invalid"
"""


@pytest.mark.asyncio
async def test_create_planner_config(sample_toml):
    """Test creating a new planner configuration via API."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/planners",
            json={
                "name": "Test Planner",
                "toml_config": sample_toml,
                "bucket_id": None,  # Template config
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Planner"
        assert data["id"] is not None
        assert data["bucket_id"] is None


@pytest.mark.asyncio
async def test_create_planner_invalid_toml(invalid_toml):
    """Test creating planner with invalid TOML returns error."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/planners",
            json={
                "name": "Invalid Planner",
                "toml_config": invalid_toml,
                "bucket_id": None,
            },
        )

        assert response.status_code == 400
        assert "Invalid TOML syntax" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_planners(sample_toml):
    """Test listing all planner configurations."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a planner first
        create_response = await client.post(
            "/api/planners",
            json={
                "name": "List Test Planner",
                "toml_config": sample_toml,
                "bucket_id": None,
            },
        )
        assert create_response.status_code == 201

        # List planners
        list_response = await client.get("/api/planners")
        assert list_response.status_code == 200
        planners = list_response.json()
        assert isinstance(planners, list)
        assert len(planners) > 0
        assert any(p["name"] == "List Test Planner" for p in planners)


@pytest.mark.asyncio
async def test_get_planner_by_id(sample_toml):
    """Test retrieving a specific planner configuration."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a planner
        create_response = await client.post(
            "/api/planners",
            json={
                "name": "Get Test Planner",
                "toml_config": sample_toml,
                "bucket_id": None,
            },
        )
        assert create_response.status_code == 201
        planner_id = create_response.json()["id"]

        # Get the planner
        get_response = await client.get(f"/api/planners/{planner_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == planner_id
        assert data["name"] == "Get Test Planner"


@pytest.mark.asyncio
async def test_get_nonexistent_planner():
    """Test getting a planner that doesn't exist returns 404."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/planners/nonexistent-id")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_planner(sample_toml, updated_toml):
    """Test updating a planner configuration."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a planner
        create_response = await client.post(
            "/api/planners",
            json={
                "name": "Update Test Planner",
                "toml_config": sample_toml,
                "bucket_id": None,
            },
        )
        assert create_response.status_code == 201
        planner_id = create_response.json()["id"]

        # Update the planner
        update_response = await client.put(
            f"/api/planners/{planner_id}",
            json={"name": "Updated Planner Name", "toml_config": updated_toml},
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["name"] == "Updated Planner Name"
        assert "Updated Strategy" in data["toml_config"]


@pytest.mark.asyncio
async def test_update_planner_name_only(sample_toml):
    """Test updating only the planner name."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a planner
        create_response = await client.post(
            "/api/planners",
            json={
                "name": "Original Name",
                "toml_config": sample_toml,
                "bucket_id": None,
            },
        )
        assert create_response.status_code == 201
        planner_id = create_response.json()["id"]

        # Update only the name
        update_response = await client.put(
            f"/api/planners/{planner_id}", json={"name": "New Name Only"}
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["name"] == "New Name Only"
        # TOML should remain unchanged
        assert "Test Strategy" in data["toml_config"]


@pytest.mark.asyncio
async def test_update_planner_invalid_toml(sample_toml, invalid_toml):
    """Test updating planner with invalid TOML returns error."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a planner
        create_response = await client.post(
            "/api/planners",
            json={
                "name": "Valid Planner",
                "toml_config": sample_toml,
                "bucket_id": None,
            },
        )
        assert create_response.status_code == 201
        planner_id = create_response.json()["id"]

        # Try to update with invalid TOML
        update_response = await client.put(
            f"/api/planners/{planner_id}", json={"toml_config": invalid_toml}
        )
        assert update_response.status_code == 400
        assert "Invalid TOML syntax" in update_response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_planner(sample_toml):
    """Test deleting a planner configuration."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a planner
        create_response = await client.post(
            "/api/planners",
            json={
                "name": "Delete Test Planner",
                "toml_config": sample_toml,
                "bucket_id": None,
            },
        )
        assert create_response.status_code == 201
        planner_id = create_response.json()["id"]

        # Delete the planner
        delete_response = await client.delete(f"/api/planners/{planner_id}")
        assert delete_response.status_code == 204

        # Verify it's gone
        get_response = await client.get(f"/api/planners/{planner_id}")
        assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_validate_toml_valid(sample_toml):
    """Test TOML validation endpoint with valid TOML."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/planners/validate", json={"toml": sample_toml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["error"] is None


@pytest.mark.asyncio
async def test_validate_toml_invalid(invalid_toml):
    """Test TOML validation endpoint with invalid TOML."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/planners/validate", json={"toml": invalid_toml}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["error"] is not None
        assert "Invalid TOML syntax" in data["error"]


@pytest.mark.asyncio
async def test_get_planner_history(sample_toml, updated_toml):
    """Test retrieving version history for a planner."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a planner
        create_response = await client.post(
            "/api/planners",
            json={
                "name": "History Test Planner",
                "toml_config": sample_toml,
                "bucket_id": None,
            },
        )
        assert create_response.status_code == 201
        planner_id = create_response.json()["id"]

        # Update it to create history
        update_response = await client.put(
            f"/api/planners/{planner_id}",
            json={"name": "Updated Name", "toml_config": updated_toml},
        )
        assert update_response.status_code == 200

        # Get history
        history_response = await client.get(f"/api/planners/{planner_id}/history")
        assert history_response.status_code == 200
        history = history_response.json()
        assert isinstance(history, list)
        # Should have at least one history entry (from the update)
        assert len(history) > 0
        assert history[0]["planner_config_id"] == planner_id


@pytest.mark.asyncio
async def test_apply_planner_without_bucket(sample_toml):
    """Test applying a planner without an associated bucket fails."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a template planner (no bucket)
        create_response = await client.post(
            "/api/planners",
            json={
                "name": "Template Planner",
                "toml_config": sample_toml,
                "bucket_id": None,
            },
        )
        assert create_response.status_code == 201
        planner_id = create_response.json()["id"]

        # Try to apply it
        apply_response = await client.post(f"/api/planners/{planner_id}/apply")
        assert apply_response.status_code == 400
        assert "no associated bucket" in apply_response.json()["detail"].lower()
