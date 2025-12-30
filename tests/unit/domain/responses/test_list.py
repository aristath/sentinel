"""Tests for ListResult response type.

These tests validate the ListResult generic type for list operations.
"""

from app.domain.responses.list import ListResult


class TestListResult:
    """Test ListResult generic type."""

    def test_list_result_creation(self):
        """Test creating ListResult with items and total."""
        result = ListResult(items=[1, 2, 3], total=3)

        assert result.items == [1, 2, 3]
        assert result.total == 3
        assert result.metadata is None

    def test_list_result_with_metadata(self):
        """Test creating ListResult with metadata."""
        result = ListResult(
            items=["a", "b"],
            total=100,
            metadata={"page": 1, "page_size": 10},
        )

        assert result.items == ["a", "b"]
        assert result.total == 100
        assert result.metadata == {"page": 1, "page_size": 10}

    def test_list_result_pagination(self):
        """Test ListResult for paginated results."""
        result = ListResult(
            items=[1, 2, 3, 4, 5],
            total=100,
            metadata={"page": 1, "page_size": 5, "total_pages": 20},
        )

        assert len(result.items) == 5
        assert result.total == 100
        assert result.metadata["page"] == 1
        assert result.metadata["page_size"] == 5

    def test_list_result_empty_items(self):
        """Test ListResult with empty items list."""
        result = ListResult(items=[], total=0)

        assert result.items == []
        assert result.total == 0

    def test_list_result_total_auto_set_from_items(self):
        """Test that total is auto-set from items length when total is 0."""
        result = ListResult(items=[1, 2, 3], total=0)

        # After __post_init__, total should be set to len(items)
        assert result.total == 3
        assert len(result.items) == 3

    def test_list_result_with_strings(self):
        """Test ListResult with string items."""
        result = ListResult(items=["apple", "banana", "cherry"], total=3)

        assert result.items == ["apple", "banana", "cherry"]
        assert result.total == 3

    def test_list_result_with_dicts(self):
        """Test ListResult with dictionary items."""
        items = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        result = ListResult(items=items, total=2)

        assert result.items == items
        assert result.total == 2
        assert result.items[0]["id"] == 1
