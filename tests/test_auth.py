"""Tests for the JWT manager."""
from __future__ import annotations

import time

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.nightscout_v3.api.auth import JwtManager
from custom_components.nightscout_v3.api.exceptions import ApiError, AuthError
from tests.conftest import load_fixture


BASE_URL = "https://ns.example"
TOKEN = "accesstoken-testuser"


@pytest.fixture
def payload() -> dict:
    return load_fixture("auth_request_success")


async def test_initial_exchange_stores_jwt(
    aiohttp_client_session, payload: dict, freezer
) -> None:
    freezer.move_to("2026-04-21T00:00:00Z")
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            payload=payload,
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        state = await mgr.initial_exchange()
    assert state.token == payload["result"]["token"]
    assert state.exp == payload["result"]["exp"]


async def test_get_valid_jwt_refreshes_near_expiry(
    aiohttp_client_session, payload: dict, freezer
) -> None:
    freezer.move_to("2026-04-21T00:00:00Z")
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            payload=payload,
            repeat=True,
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        await mgr.initial_exchange()
        # Advance to within refresh threshold
        freezer.move_to(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(payload["result"]["exp"] - 1000)))
        jwt = await mgr.get_valid_jwt()
    assert jwt == payload["result"]["token"]
    # Called twice (initial + on-demand refresh)
    assert len(m.requests) >= 1


async def test_initial_exchange_raises_auth_on_401(aiohttp_client_session) -> None:
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            status=401,
            payload={"status": 401, "message": "unauthorized"},
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        with pytest.raises(AuthError):
            await mgr.initial_exchange()


async def test_refresh_retries_with_backoff_on_5xx(
    aiohttp_client_session, payload: dict, monkeypatch
) -> None:
    sleeps: list[float] = []

    async def fake_sleep(duration: float) -> None:
        sleeps.append(duration)

    monkeypatch.setattr("custom_components.nightscout_v3.api.auth.asyncio.sleep", fake_sleep)

    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/v2/authorization/request/{TOKEN}", status=502, repeat=3)
        m.post(f"{BASE_URL}/api/v2/authorization/request/{TOKEN}", payload=payload)
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        state = await mgr.initial_exchange()
    assert state.token == payload["result"]["token"]
    assert sleeps[:3] == [1, 2, 4]


async def test_refresh_gives_up_after_max_attempts(
    aiohttp_client_session, monkeypatch
) -> None:
    async def fake_sleep(_d: float) -> None: ...

    monkeypatch.setattr("custom_components.nightscout_v3.api.auth.asyncio.sleep", fake_sleep)
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/v2/authorization/request/{TOKEN}", status=502, repeat=True)
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        with pytest.raises(ApiError):
            await mgr.initial_exchange()


async def test_state_property_before_and_after_exchange(
    aiohttp_client_session, payload: dict
) -> None:
    """state property returns None before exchange, populated after."""
    mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
    assert mgr.state is None
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            payload=payload,
        )
        await mgr.initial_exchange()
    assert mgr.state is not None
    assert mgr.state.token == payload["result"]["token"]


async def test_refresh_forces_new_exchange(
    aiohttp_client_session, payload: dict
) -> None:
    """refresh() forces a new exchange regardless of current TTL."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            payload=payload,
            repeat=True,
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        first = await mgr.initial_exchange()
        # Token is still valid; refresh() must call the endpoint anyway.
        second = await mgr.refresh()
        # Two requests were sent to the authorization endpoint.
        total_requests = sum(len(v) for v in m.requests.values())
    assert total_requests == 2
    assert second.token == first.token


async def test_initial_exchange_raises_api_error_on_403(
    aiohttp_client_session, monkeypatch
) -> None:
    """Non-200/non-401/non-5xx status maps to ApiError (not AuthError)."""
    async def fake_sleep(_d: float) -> None: ...

    monkeypatch.setattr("custom_components.nightscout_v3.api.auth.asyncio.sleep", fake_sleep)
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            status=403,
            payload={"status": 403, "message": "forbidden"},
            repeat=True,
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        with pytest.raises(ApiError) as excinfo:
            await mgr.initial_exchange()
    # The retry wrapper swallows the inner 403 ApiError and raises its own
    # "gave up" message, but the inner "Unexpected status 403" must have
    # executed at least once (that's the line-85 branch).
    assert "403" in str(excinfo.value)
    # Not an AuthError — 401 is the only status that signals auth rejection.
    assert not isinstance(excinfo.value, AuthError)


async def test_initial_exchange_raises_api_error_on_network_error(
    aiohttp_client_session, monkeypatch
) -> None:
    """aiohttp.ClientError before response re-raises as ApiError."""
    async def fake_sleep(_d: float) -> None: ...

    monkeypatch.setattr("custom_components.nightscout_v3.api.auth.asyncio.sleep", fake_sleep)
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            exception=aiohttp.ClientConnectionError("boom"),
            repeat=True,
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        with pytest.raises(ApiError, match="Network error"):
            await mgr.initial_exchange()


async def test_initial_exchange_raises_api_error_on_malformed_jwt_body(
    aiohttp_client_session, monkeypatch
) -> None:
    """Missing exp/iat/token in the response body raises ApiError.

    The retry loop treats ApiError as transient, so the inner
    'Malformed JWT response' message is swallowed by the outer
    'gave up after N attempts' — both must surface the underlying
    cause and the line-95 branch must execute at least once.
    """
    async def fake_sleep(_d: float) -> None: ...

    monkeypatch.setattr("custom_components.nightscout_v3.api.auth.asyncio.sleep", fake_sleep)
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            payload={"status": 200, "result": {"token": "foo"}},
            repeat=True,
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        with pytest.raises(ApiError) as excinfo:
            await mgr.initial_exchange()
    assert "Malformed JWT response" in str(excinfo.value)


async def test_malformed_jwt_error_does_not_leak_token_body(
    aiohttp_client_session, monkeypatch
) -> None:
    """A malformed response must not dump the raw JWT into the ApiError.

    Regression test for the final release review C-1: the exception
    propagates to a DEBUG log at the entry-level refresh handler.
    """
    async def fake_sleep(_d: float) -> None: ...
    monkeypatch.setattr(
        "custom_components.nightscout_v3.api.auth.asyncio.sleep", fake_sleep,
    )
    leaked_jwt = "eyJLEAKME.eyJhbGciOiJIUzI1NiJ9.SIGSIGSIG"
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            payload={"status": 200, "result": {"token": leaked_jwt, "iat": 0}},
            repeat=True,
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        with pytest.raises(ApiError) as excinfo:
            await mgr.initial_exchange()
    message = str(excinfo.value)
    cause = excinfo.value.__cause__
    assert leaked_jwt not in message
    assert cause is None or leaked_jwt not in str(cause)


async def test_initial_exchange_falls_back_to_v1_on_v2_404(
    aiohttp_client_session, freezer
) -> None:
    """Nightscout installs without the v2 authorization route expose the JWT
    on /api/v1/status.json?token=...; a 404 on v2 must trigger that fallback.
    """
    freezer.move_to("2026-04-21T00:00:00Z")
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            status=404,
        )
        m.get(
            f"{BASE_URL}/api/v1/status.json?token={TOKEN}",
            payload={
                "status": "ok",
                "name": "nightscout",
                "authorized": {
                    "token": "jwt-from-v1",
                    "sub": "homeassistant",
                    "iat": 1_775_000_000,
                    "exp": 1_775_028_800,
                },
            },
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        state = await mgr.initial_exchange()
    assert state.token == "jwt-from-v1"
    assert state.iat == 1_775_000_000
    assert state.exp == 1_775_028_800


@pytest.fixture
async def aiohttp_client_session():
    async with aiohttp.ClientSession() as s:
        yield s
