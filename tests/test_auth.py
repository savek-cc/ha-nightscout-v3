"""Tests for the JWT manager."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock

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
        m.get(
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
        m.get(
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
        m.get(
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
        m.get(f"{BASE_URL}/api/v2/authorization/request/{TOKEN}", status=502, repeat=3)
        m.get(f"{BASE_URL}/api/v2/authorization/request/{TOKEN}", payload=payload)
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
        m.get(f"{BASE_URL}/api/v2/authorization/request/{TOKEN}", status=502, repeat=True)
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        with pytest.raises(ApiError):
            await mgr.initial_exchange()


@pytest.fixture
async def aiohttp_client_session():
    import aiohttp

    async with aiohttp.ClientSession() as s:
        yield s
