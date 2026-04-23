"""Tests for nightscout_v3 API exceptions."""

from custom_components.nightscout_v3.api.exceptions import (
    ApiError,
    AuthError,
)


def test_exception_hierarchy() -> None:
    """All exceptions inherit from ApiError."""
    assert issubclass(AuthError, ApiError)


def test_api_error_carries_status() -> None:
    """ApiError captures HTTP status code."""
    err = ApiError("boom", status=502)
    assert err.status == 502
    assert "boom" in str(err)


def test_auth_error_defaults_to_401() -> None:
    """AuthError defaults to HTTP 401."""
    err = AuthError("token rejected")
    assert err.status == 401
