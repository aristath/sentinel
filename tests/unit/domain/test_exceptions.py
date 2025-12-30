"""Tests for domain exceptions.

These tests validate the domain exception classes and their behavior.
"""

import pytest

from app.domain.exceptions import DomainError, ValidationError


class TestDomainError:
    """Test DomainError exception."""

    def test_domain_error_is_exception(self):
        """Test that DomainError is an Exception."""
        error = DomainError()
        assert isinstance(error, Exception)

    def test_domain_error_can_have_message(self):
        """Test that DomainError can have a message."""
        message = "Something went wrong"
        error = DomainError(message)
        assert str(error) == message

    def test_domain_error_can_be_raised(self):
        """Test that DomainError can be raised and caught."""
        with pytest.raises(DomainError) as exc_info:
            raise DomainError("Test error")
        assert str(exc_info.value) == "Test error"


class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_is_domain_error(self):
        """Test that ValidationError is a DomainError."""
        error = ValidationError("Invalid input")
        assert isinstance(error, DomainError)
        assert isinstance(error, Exception)

    def test_validation_error_stores_message(self):
        """Test that ValidationError stores the message."""
        message = "Symbol cannot be empty"
        error = ValidationError(message)

        assert error.message == message
        assert "Validation error:" in str(error)
        assert message in str(error)

    def test_validation_error_can_be_raised(self):
        """Test that ValidationError can be raised and caught."""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Name cannot be empty")
        assert exc_info.value.message == "Name cannot be empty"
        assert "Validation error:" in str(exc_info.value)

    def test_validation_error_inherits_from_domain_error(self):
        """Test that ValidationError can be caught as DomainError."""
        with pytest.raises(DomainError) as exc_info:
            raise ValidationError("Invalid data")
        assert isinstance(exc_info.value, ValidationError)
        assert exc_info.value.message == "Invalid data"
