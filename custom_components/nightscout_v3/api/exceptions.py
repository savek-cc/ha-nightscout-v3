"""Exceptions raised by the Nightscout v3 API client."""
from __future__ import annotations


class ApiError(Exception):
    """Base class for all API errors."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        """Initialize the API error with an optional HTTP status."""
        super().__init__(message)
        self.status = status


class AuthError(ApiError):
    """Raised when the server rejects our credentials (401)."""

    def __init__(self, message: str, *, status: int = 401) -> None:
        """Initialize the auth error, defaulting to HTTP 401."""
        super().__init__(message, status=status)
