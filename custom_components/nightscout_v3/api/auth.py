"""JWT exchange + refresh for Nightscout v3."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import aiohttp

from .exceptions import ApiError, AuthError

_LOGGER = logging.getLogger(__name__)

REFRESH_THRESHOLD_SECONDS = 3600
MAX_REFRESH_ATTEMPTS = 5
_BACKOFF_BASE = 1.0


@dataclass(slots=True)
class JwtState:
    """Last-known JWT state."""

    token: str
    iat: int
    exp: int


class JwtManager:
    """Manages the Nightscout v3 JWT: initial exchange + on-demand refresh."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, access_token: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._state: JwtState | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> JwtState | None:
        return self._state

    async def initial_exchange(self) -> JwtState:
        """Perform the first JWT exchange."""
        return await self._exchange_with_retry()

    async def get_valid_jwt(self) -> str:
        """Return a currently-valid JWT, refreshing if needed."""
        async with self._lock:
            if self._state is None or self._state.exp - time.time() < REFRESH_THRESHOLD_SECONDS:
                await self._exchange_with_retry()
            assert self._state is not None
            return self._state.token

    async def refresh(self) -> JwtState:
        """Force a refresh regardless of current TTL."""
        async with self._lock:
            return await self._exchange_with_retry()

    async def _exchange_with_retry(self) -> JwtState:
        url = f"{self._base_url}/api/v2/authorization/request/{self._access_token}"
        last_exc: Exception | None = None
        for attempt in range(MAX_REFRESH_ATTEMPTS):
            try:
                return await self._exchange_once(url)
            except AuthError:
                raise
            except (ApiError, aiohttp.ClientError, TimeoutError) as exc:
                last_exc = exc
                backoff = _BACKOFF_BASE * (2**attempt)
                _LOGGER.debug("JWT exchange attempt %d failed; sleeping %.1fs", attempt + 1, backoff)
                await asyncio.sleep(backoff)
        raise ApiError(f"JWT exchange gave up after {MAX_REFRESH_ATTEMPTS} attempts: {last_exc}")

    async def _exchange_once(self, url: str) -> JwtState:
        try:
            async with self._session.post(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 401:
                    raise AuthError("Access token rejected")
                if resp.status >= 500:
                    raise ApiError(f"Server error {resp.status}", status=resp.status)
                if resp.status != 200:
                    raise ApiError(f"Unexpected status {resp.status}", status=resp.status)
                body = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as exc:
            # Avoid `{exc}` interpolation: the exchange URL embeds the raw
            # access token, and some aiohttp error reprs include that URL.
            raise ApiError(
                f"Network error during JWT exchange: {type(exc).__name__}"
            ) from exc

        result = body.get("result", {})
        token = result.get("token")
        exp = result.get("exp")
        iat = result.get("iat")
        if token is None or exp is None or iat is None:
            missing = [
                name for name, value in (("token", token), ("exp", exp), ("iat", iat))
                if value is None
            ]
            raise ApiError(f"Malformed JWT response: missing fields {missing}")
        self._state = JwtState(token=token, iat=int(iat), exp=int(exp))
        return self._state
