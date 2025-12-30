"""Tests for error response utilities.

These tests validate the error_response and success_response utility functions
used throughout the API for standardized response formatting.
"""

from app.api.errors import error_response, success_response


class TestErrorResponse:
    """Test the error_response utility function."""

    def test_creates_standard_error_response(self):
        """Test that error_response creates a standard error format."""
        result = error_response("Something went wrong")

        assert result["status"] == "error"
        assert result["message"] == "Something went wrong"

    def test_allows_custom_status(self):
        """Test that error_response accepts custom status values."""
        result = error_response("Not found", status="not_found")

        assert result["status"] == "not_found"
        assert result["message"] == "Not found"

    def test_includes_additional_fields(self):
        """Test that error_response includes additional kwargs."""
        result = error_response(
            "Validation failed",
            status="validation_error",
            field="email",
            code=400,
        )

        assert result["status"] == "validation_error"
        assert result["message"] == "Validation failed"
        assert result["field"] == "email"
        assert result["code"] == 400

    def test_handles_empty_message(self):
        """Test that error_response handles empty messages."""
        result = error_response("")

        assert result["status"] == "error"
        assert result["message"] == ""

    def test_handles_none_values_in_kwargs(self):
        """Test that error_response handles None values in kwargs."""
        result = error_response("Error", detail=None, code=None)

        assert result["status"] == "error"
        assert result["message"] == "Error"
        assert result["detail"] is None
        assert result["code"] is None

    def test_handles_nested_data_structures(self):
        """Test that error_response handles nested data structures."""
        result = error_response(
            "Validation errors",
            errors={"field1": ["Error 1", "Error 2"], "field2": ["Error 3"]},
        )

        assert result["status"] == "error"
        assert result["message"] == "Validation errors"
        assert result["errors"]["field1"] == ["Error 1", "Error 2"]
        assert result["errors"]["field2"] == ["Error 3"]


class TestSuccessResponse:
    """Test the success_response utility function."""

    def test_creates_standard_success_response(self):
        """Test that success_response creates a standard success format."""
        result = success_response()

        assert result["status"] == "ok"
        assert "data" not in result

    def test_includes_data_when_provided(self):
        """Test that success_response includes data when provided."""
        data = {"key": "value"}
        result = success_response(data)

        assert result["status"] == "ok"
        assert result["data"] == data

    def test_includes_additional_fields(self):
        """Test that success_response includes additional kwargs."""
        result = success_response(
            data={"items": [1, 2, 3]},
            total=3,
            page=1,
        )

        assert result["status"] == "ok"
        assert result["data"] == {"items": [1, 2, 3]}
        assert result["total"] == 3
        assert result["page"] == 1

    def test_handles_none_data(self):
        """Test that success_response handles None data correctly."""
        result = success_response(data=None)

        assert result["status"] == "ok"
        assert "data" not in result  # None data should not be included

    def test_handles_empty_data_structures(self):
        """Test that success_response handles empty data structures."""
        result = success_response(data=[])

        assert result["status"] == "ok"
        assert result["data"] == []

        result = success_response(data={})

        assert result["status"] == "ok"
        assert result["data"] == {}

    def test_handles_nested_data_structures(self):
        """Test that success_response handles nested data structures."""
        nested_data = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            "metadata": {"count": 2, "page": 1},
        }
        result = success_response(data=nested_data)

        assert result["status"] == "ok"
        assert result["data"]["users"][0]["name"] == "Alice"
        assert result["data"]["metadata"]["count"] == 2

    def test_kwargs_added_separately_from_data(self):
        """Test that kwargs are added as separate fields in response."""
        result = success_response(data={"items": [1, 2]}, count=2, page=1)

        assert result["status"] == "ok"
        assert result["data"] == {"items": [1, 2]}
        assert result["count"] == 2
        assert result["page"] == 1
