"""Lightweight probe against a Nightscout v3 instance.

Refuses to run against known production hosts (ProdInstance). Outputs a compact
JSON summary suitable for log inspection.

Usage:
    python -m scripts.smoke_test --url https://example.invalid --token $NS_TOKEN
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

import aiohttp

FORBIDDEN_HOSTS = {"prod-nightscout.example.invalid"}


def refuse_forbidden_hosts(url: str) -> None:
    for forbidden in FORBIDDEN_HOSTS:
        if forbidden in url:
            sys.stderr.write(f"smoke_test refuses to target {forbidden}\n")
            raise SystemExit(3)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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

        return {
            "status_version": status.get("version") if isinstance(status, dict) else None,
            "capabilities": caps.to_dict(),
            "entries_count": len(entries.get("result", []) if isinstance(entries, dict) else entries or []),
            "devicestatus_count": len(
                devicestatus.get("result", []) if isinstance(devicestatus, dict) else devicestatus or []
            ),
        }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    refuse_forbidden_hosts(args.url)
    summary = asyncio.run(_run(args.url, args.token, args.limit))
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
