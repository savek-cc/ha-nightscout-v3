"""Tests for NightscoutV3Client."""

from __future__ import annotations

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
            f"{BASE_URL}/api/v3/devicestatus?limit=1&sort$desc=created_at",
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
            f"{BASE_URL}/api/v3/treatments?eventType$eq=Sensor%20Change&limit=1&sort$desc=created_at",
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


# ---------------------------------------------------------------------------
# Coverage for the query-filter branches on get_devicestatus / get_entries /
# get_treatments — each optional kwarg gets its own exercised path.
# ---------------------------------------------------------------------------


async def test_get_devicestatus_with_last_modified(session, jwt_manager):
    """srvModified$gt filter is appended when last_modified is given."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/devicestatus"
            f"?limit=1&sort$desc=created_at&srvModified$gt=1745009999000",
            payload=load_fixture("devicestatus_latest"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_devicestatus(limit=1, last_modified=1745009999000)
    assert result[0]["pump"]["battery"]["percent"] == 82


async def test_get_entries_before_date(session, jwt_manager):
    """before_date filter prepends date$lt to the query."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/entries?date$lt=1745009999000&limit=1&sort$desc=date",
            payload=load_fixture("entries_latest"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_entries(before_date=1745009999000, limit=1)
    assert result[0]["sgv"] == 142


async def test_get_entries_last_modified(session, jwt_manager):
    """last_modified filter appends srvModified$gt to the query."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/entries?limit=1&sort$desc=date&srvModified$gt=1745000000000",
            payload=load_fixture("entries_latest"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_entries(limit=1, last_modified=1745000000000)
    assert result[0]["sgv"] == 142


async def test_get_treatments_without_event_type(session, jwt_manager):
    """event_type=None skips the eventType$eq filter (covers the false branch)."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/treatments?limit=1&sort$desc=created_at",
            payload=load_fixture("treatments_sensor_change"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_treatments(limit=1)
    assert result[0]["eventType"] == "Sensor Change"


async def test_get_treatments_since_and_last_modified(session, jwt_manager):
    """event_type + since_date + last_modified all compose into one query."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/treatments"
            f"?eventType$eq=Sensor%20Change&created_at$gte=2025-04-18T18%3A13%3A20Z"
            f"&limit=1&sort$desc=created_at&srvModified$gt=1745000000000",
            payload=load_fixture("treatments_sensor_change"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_treatments(
            event_type="Sensor Change",
            since_date=1745000000000,
            last_modified=1745000000000,
            limit=1,
        )
    assert result[0]["eventType"] == "Sensor Change"


async def test_get_profile_raises_when_empty(session, jwt_manager):
    """Empty profile list raises ApiError('No profile returned')."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/profile?limit=1&sort$desc=date",
            payload={"status": 200, "result": []},
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        with pytest.raises(ApiError, match="No profile returned"):
            await client.get_profile(latest=True)


async def test_get_status_handles_non_enveloped_response(session, jwt_manager):
    """_get falls through and returns the raw body when 'result' is missing."""
    raw = {"version": "15.0.3", "apiVersion": "3.0.3-alpha"}
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v3/status", payload=raw)
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_status()
    assert result == raw


async def test_get_list_raises_when_result_not_list(session, jwt_manager):
    """_get_list rejects a body whose 'result' is not a list."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/entries?limit=1&sort$desc=date",
            payload={"status": 200, "result": {"not": "a list"}},
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        with pytest.raises(ApiError, match="Expected list"):
            await client.get_entries(limit=1)


async def test_client_raises_api_error_on_403(session, jwt_manager):
    """Non-200/non-401/non-5xx response on a v3 endpoint raises ApiError."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v3/status", status=403, payload={"status": 403})
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        with pytest.raises(ApiError) as excinfo:
            await client.get_status()
    assert excinfo.value.status == 403
    assert not isinstance(excinfo.value, AuthError)


async def test_client_raises_api_error_on_network_error(session, jwt_manager):
    """aiohttp.ClientError on a v3 endpoint is wrapped in ApiError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/status",
            exception=aiohttp.ClientConnectionError("boom"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        with pytest.raises(ApiError, match="Network error"):
            await client.get_status()
