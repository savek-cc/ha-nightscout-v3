"""Lightweight probe against a Nightscout v3 instance.

Can be configured to refuse known production hosts. Outputs a compact
JSON summary suitable for log inspection.

Usage:
    python -m scripts.smoke_test --url https://example.invalid --token $NS_TOKEN
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import aiohttp

FORBIDDEN_HOSTS_ENV = "NIGHTSCOUT_FORBIDDEN_HOSTS"


def refuse_forbidden_hosts(url: str) -> None:
    """Exit if `url` points to a known production host."""
    for forbidden in _configured_forbidden_hosts():
        if forbidden in url.lower():
            sys.stderr.write(f"smoke_test refuses to target {forbidden}\n")
            raise SystemExit(3)


def _configured_forbidden_hosts() -> set[str]:
    """Return lower-cased forbidden-host substrings from the environment."""
    raw = os.environ.get(FORBIDDEN_HOSTS_ENV, "")
    return {host.strip().lower() for host in raw.split(",") if host.strip()}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse smoke_test CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--limit", type=int, default=3)
    return parser.parse_args(argv)


async def _run(url: str, token: str, limit: int) -> dict[str, object]:
    from custom_components.nightscout_v3.api.auth import JwtManager
    from custom_components.nightscout_v3.api.capabilities import probe_capabilities
    from custom_components.nightscout_v3.api.client import NightscoutV3Client

    base = url.rstrip("/")
    async with aiohttp.ClientSession() as session:
        jwt = JwtManager(session, base, token)
        await jwt.initial_exchange()
        client = NightscoutV3Client(session, base, jwt)
        status = await client.get_status()
        caps = await probe_capabilities(client)
        entries = await client.get_entries(limit=limit)
        devicestatus = await client.get_devicestatus(limit=limit)

        entries_list = (
            entries.get("result", []) if isinstance(entries, dict) else (entries or [])
        )
        devicestatus_list = (
            devicestatus.get("result", [])
            if isinstance(devicestatus, dict)
            else (devicestatus or [])
        )
        return {
            "status_version": (
                status.get("version") if isinstance(status, dict) else None
            ),
            "capabilities": caps.to_dict(),
            "entries_count": len(entries_list),
            "devicestatus_count": len(devicestatus_list),
        }


def main(argv: list[str] | None = None) -> int:
    """Run the smoke_test CLI."""
    args = parse_args(argv)
    refuse_forbidden_hosts(args.url)
    summary = asyncio.run(_run(args.url, args.token, args.limit))
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
