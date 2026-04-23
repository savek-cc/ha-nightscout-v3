"""Capture raw Nightscout v3 responses for offline fixture creation.

SAFETY: can be configured to refuse known production instances.
Outputs go to `captures/` -- anonymize with `scripts.anonymize_fixtures`
before committing.

Env:
    NS_URL                      base URL of a non-production Nightscout instance
    NS_TOKEN                    access token
    NIGHTSCOUT_FORBIDDEN_HOSTS  comma-separated host substrings that must
                                never be targeted by this script

Usage:
    python -m scripts.capture_fixtures status entries devicestatus
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import aiohttp

FORBIDDEN_HOSTS_ENV = "NIGHTSCOUT_FORBIDDEN_HOSTS"


@dataclass
class ClientConfig:
    """Base URL and token for a capture target."""

    base_url: str
    token: str


def build_client_config() -> ClientConfig:
    """Read NS_URL/NS_TOKEN from the environment and reject forbidden hosts."""
    url = os.environ.get("NS_URL")
    token = os.environ.get("NS_TOKEN")
    if not url or not token:
        sys.stderr.write("NS_URL and NS_TOKEN must be set\n")
        raise SystemExit(2)
    for forbidden in _configured_forbidden_hosts():
        if forbidden in url.lower():
            sys.stderr.write(
                f"scripts.capture_fixtures refuses to target {forbidden} (production)\n"
            )
            raise SystemExit(3)
    return ClientConfig(base_url=url.rstrip("/"), token=token)


def _configured_forbidden_hosts() -> set[str]:
    """Return lower-cased forbidden-host substrings from the environment."""
    raw = os.environ.get(FORBIDDEN_HOSTS_ENV, "")
    return {host.strip().lower() for host in raw.split(",") if host.strip()}


async def _capture(cfg: ClientConfig, endpoints: list[str], dst: Path) -> None:
    from custom_components.nightscout_v3.api.auth import JwtManager
    from custom_components.nightscout_v3.api.client import NightscoutV3Client

    async with aiohttp.ClientSession() as session:
        jwt = JwtManager(session, cfg.base_url, cfg.token)
        await jwt.initial_exchange()
        client = NightscoutV3Client(session, cfg.base_url, jwt)

        dispatch = {
            "status": lambda: client.get_status(),
            "entries": lambda: client.get_entries(limit=200),
            "devicestatus": lambda: client.get_devicestatus(limit=50),
            "treatments": lambda: client.get_treatments(limit=100),
            "profile": lambda: client.get_profile(),
        }

        for ep in endpoints:
            fetch = dispatch.get(ep)
            if fetch is None:
                sys.stderr.write(f"unknown endpoint: {ep}\n")
                continue
            data = await fetch()
            (dst / f"{ep}.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            sys.stdout.write(f"captured {ep} -> {dst / (ep + '.json')}\n")


def main(argv: list[str] | None = None) -> int:
    """Run the capture_fixtures CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("endpoints", nargs="+")
    parser.add_argument("--dst", default="captures", type=Path)
    args = parser.parse_args(argv)
    cfg = build_client_config()
    args.dst.mkdir(parents=True, exist_ok=True)
    asyncio.run(_capture(cfg, args.endpoints, args.dst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
