"""Nightscout v3 REST client."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import aiohttp

from .auth import JwtManager
from .exceptions import ApiError, AuthError

_LOGGER = logging.getLogger(__name__)
_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20)
_HARD_TIMEOUT_SECONDS = 35


def _ms_to_iso(ms: int) -> str:
    """Convert epoch-ms to ISO-8601 UTC string for v3 created_at filters."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat().replace("+00:00", "Z")


class NightscoutV3Client:
    """Thin wrapper around the Nightscout v3 REST API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        jwt_manager: JwtManager,
    ) -> None:
        """Initialize the Nightscout v3 client."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._jwt_manager = jwt_manager

    async def get_status(self) -> dict[str, Any]:
        """Return the server's /api/v3/status payload."""
        return await self._get("/api/v3/status", envelope=True)

    async def get_last_modified(self) -> dict[str, Any]:
        """Return the server's per-collection last-modified timestamps."""
        return await self._get("/api/v3/lastModified", envelope=True)

    async def get_devicestatus(
        self,
        limit: int = 1,
        *,
        last_modified: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return the latest devicestatus documents, newest first.

        Sorts by `created_at` rather than `date`: v3 passes sort keys to
        Mongo literally, and devicestatus is indexed on `created_at`, not
        `date`. Sorting by `date` forces a SORT stage scan over the whole
        collection (observed: ~1.9M docs → OOM on small-RAM hosts).
        """
        params = [("limit", str(limit)), ("sort$desc", "created_at")]
        if last_modified is not None:
            params.append(("srvModified$gt", str(last_modified)))
        return await self._get_list("/api/v3/devicestatus", params)

    async def get_entries(
        self,
        limit: int = 1,
        *,
        since_date: int | None = None,
        before_date: int | None = None,
        last_modified: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return CGM entries matching the given window, newest first."""
        params: list[tuple[str, str]] = [("limit", str(limit)), ("sort$desc", "date")]
        if since_date is not None:
            params.insert(0, ("date$gte", str(since_date)))
        if before_date is not None:
            params.insert(0, ("date$lt", str(before_date)))
        if last_modified is not None:
            params.append(("srvModified$gt", str(last_modified)))
        return await self._get_list("/api/v3/entries", params)

    async def get_treatments(
        self,
        *,
        event_type: str | None = None,
        limit: int = 1,
        since_date: int | None = None,
        last_modified: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return treatments matching the given filters, newest first.

        Sorts/filters by `created_at` rather than `date`: treatments is
        indexed on `created_at` (ISO-8601 string), not `date`. The
        `since_date` argument stays epoch-ms for caller convenience and
        is converted to the ISO string form on the wire.
        """
        params: list[tuple[str, str]] = []
        if event_type is not None:
            params.append(("eventType$eq", event_type))
        if since_date is not None:
            params.append(("created_at$gte", _ms_to_iso(since_date)))
        params += [("limit", str(limit)), ("sort$desc", "created_at")]
        if last_modified is not None:
            params.append(("srvModified$gt", str(last_modified)))
        return await self._get_list("/api/v3/treatments", params)

    async def get_profile(self, *, latest: bool = True) -> dict[str, Any]:
        """Return the latest profile document, or raise if none exists."""
        params = [("limit", "1"), ("sort$desc", "date")] if latest else []
        result = await self._get_list("/api/v3/profile", params)
        if not result:
            raise ApiError("No profile returned")
        return result[0]

    async def _get(self, path: str, *, envelope: bool) -> dict[str, Any]:
        raw = await self._raw_get(path, [])
        if envelope and "result" in raw:
            return raw["result"]
        return raw

    async def _get_list(self, path: str, params: list[tuple[str, str]]) -> list[dict[str, Any]]:
        raw = await self._raw_get(path, params)
        result = raw.get("result", [])
        if not isinstance(result, list):
            raise ApiError(f"Expected list at {path}, got {type(result).__name__}")
        return result

    async def _raw_get(self, path: str, params: list[tuple[str, str]]) -> dict[str, Any]:
        jwt = await self._jwt_manager.get_valid_jwt()
        headers = {
            "Authorization": f"Bearer {jwt}",
            "Accept": "application/json",
        }
        qs = "&".join(f"{k}={quote(v, safe='$')}" for k, v in params)
        url = f"{self._base_url}{path}" + (f"?{qs}" if qs else "")
        try:
            async with asyncio.timeout(_HARD_TIMEOUT_SECONDS):
                async with self._session.get(
                    url,
                    headers=headers,
                    timeout=_DEFAULT_TIMEOUT,
                ) as resp:
                    if resp.status == 401:
                        raise AuthError(f"401 on {path}")
                    if resp.status >= 500:
                        raise ApiError(f"{resp.status} on {path}", status=resp.status)
                    if resp.status != 200:
                        raise ApiError(f"{resp.status} on {path}", status=resp.status)
                    return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise ApiError(f"Network error on {path}: {exc}") from exc
