"""Exceptions raised by the Nightscout v3 API client."""
from __future__ import annotations


class ApiError(Exception):
    """Base class for all API errors."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class AuthError(ApiError):
    """Raised when the server rejects our credentials (401)."""

    def __init__(self, message: str, *, status: int = 401) -> None:
        super().__init__(message, status=status)


class NotReady(ApiError):
    """Raised for transient errors (5xx, timeout, DNS)."""
