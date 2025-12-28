"""Error response utilities for API endpoints."""

from typing import Any, Dict


def error_response(
    message: str, status: str = "error", **kwargs: Any
) -> Dict[str, Any]:
    """Create a standardized error response.

    Args:
        message: Error message
        status: Status string (default: "error")
        **kwargs: Additional fields to include in response

    Returns:
        Standardized error response dictionary
    """
    response: Dict[str, Any] = {
        "status": status,
        "message": message,
    }
    response.update(kwargs)
    return response


def success_response(data: Any = None, **kwargs: Any) -> Dict[str, Any]:
    """Create a standardized success response.

    Args:
        data: Response data (optional)
        **kwargs: Additional fields to include in response

    Returns:
        Standardized success response dictionary
    """
    response: Dict[str, Any] = {
        "status": "ok",
    }
    if data is not None:
        response["data"] = data
    response.update(kwargs)
    return response
