"""Tests for NightscoutV3Client."""
from __future__ import annotations

from unittest.mock import AsyncMock

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.nightscout_v3.api.auth import JwtManager, JwtState
from custom_components.nightscout_v3.api.client import NightscoutV3Client
from custom_components.nightscout_v3.api.exceptions import ApiError, AuthError
from tests.conftest import load_fixture

BASE_URL = "https://ns.example"


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as s:
        yield s


@pytest.fixture
def jwt_manager(session: aiohttp.ClientSession) -> JwtManager:
    mgr = JwtManager(session, BASE_URL, "access-token")
    mgr._state = JwtState(token="jwt-anon", iat=0, exp=9999999999)
    return mgr


async def test_get_status(session, jwt_manager):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v3/status", payload=load_fixture("status"))
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_status()
    assert result["apiVersion"].startswith("3.0")


async def test_get_last_modified(session, jwt_manager):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v3/lastModified", payload=load_fixture("lastmodified"))
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_last_modified()
    assert "collections" in result


async def test_get_devicestatus(session, jwt_manager):
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/devicestatus?limit=1&sort$desc=date",
            payload=load_fixture("devicestatus_latest"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_devicestatus(limit=1)
    assert result[0]["pump"]["battery"]["percent"] == 82


async def test_get_entries_since(session, jwt_manager):
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/entries?date$gte=1745000000000&limit=1000&sort$desc=date",
            payload=load_fixture("entries_latest"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_entries(since_date=1745000000000, limit=1000)
    assert result[0]["sgv"] == 142


async def test_get_treatments_event_filter(session, jwt_manager):
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/treatments?eventType$eq=Sensor%20Change&limit=1&sort$desc=date",
            payload=load_fixture("treatments_sensor_change"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_treatments(event_type="Sensor Change", limit=1)
    assert result[0]["eventType"] == "Sensor Change"


async def test_get_profile_latest(session, jwt_manager):
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/profile?limit=1&sort$desc=date",
            payload=load_fixture("profile_latest"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_profile(latest=True)
    assert result["defaultProfile"] == "TestProfile"


async def test_401_raises_auth_error(session, jwt_manager):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v3/status", status=401, payload={"status": 401})
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        with pytest.raises(AuthError):
            await client.get_status()


async def test_5xx_raises_api_error(session, jwt_manager):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v3/status", status=503, payload={"status": 503})
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        with pytest.raises(ApiError):
            await client.get_status()


async def test_authorization_header_sent(session, jwt_manager):
    captured = {}

    async def handler(url, **kwargs):
        captured["headers"] = dict(kwargs.get("headers") or {})

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/status",
            payload=load_fixture("status"),
            callback=handler,
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        await client.get_status()
    assert captured["headers"]["Authorization"] == "Bearer jwt-anon"
