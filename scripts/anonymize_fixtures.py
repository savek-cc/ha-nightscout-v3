"""Anonymize Nightscout JSON captures into public-safe fixtures.

Usage:
    python -m scripts.anonymize_fixtures captures/*.json tests/fixtures/

The goal is to strip anything that could identify a person, a server, or a
medical event while keeping the numeric *shape* of the response so that
offline tests exercise realistic code paths.
"""
from __future__ import annotations

import argparse
import json
import secrets
import string
import sys
from pathlib import Path
from typing import Any

SENSITIVE_STRING_KEYS = {
    "notes", "enteredBy", "profileJson", "created_at", "srvModified",
    "url", "baseURL", "instance", "hostname", "author", "email", "username",
    "name", "firstName", "lastName", "patient",
}

DROP_KEYS = {"_id"}
TIMESTAMP_KEYS = {"date", "sysTime", "srvCreated", "srvModified", "mills"}


def _fake_id() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(24))


def _rebase_ts(v: Any, offset: int) -> Any:
    if isinstance(v, int) and v > 1_000_000_000_000:
        return v - offset
    return v


def _bucket_carbs(v: Any) -> Any:
    if isinstance(v, int | float) and v > 0:
        return int(round(v / 10.0) * 10)
    return v


def _scrub(obj: Any, offset: int) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in DROP_KEYS:
                out[k] = _fake_id()
                continue
            if k in SENSITIVE_STRING_KEYS and isinstance(v, str):
                out[k] = "" if v == "" else "redacted"
                continue
            if k in TIMESTAMP_KEYS:
                out[k] = _rebase_ts(v, offset)
                continue
            if k == "carbs":
                out[k] = _bucket_carbs(v)
                continue
            out[k] = _scrub(v, offset)
        return out
    if isinstance(obj, list):
        return [_scrub(x, offset) for x in obj]
    return obj


def anonymize_payload(payload: dict[str, Any], epoch_offset_ms: int) -> dict[str, Any]:
    return _scrub(payload, epoch_offset_ms)


def _process_file(src: Path, dst_dir: Path, offset: int) -> Path:
    raw = json.loads(src.read_text(encoding="utf-8"))
    anon = anonymize_payload(raw, offset)
    dst = dst_dir / src.name
    dst.write_text(json.dumps(anon, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", nargs="+", help="Source JSON files or directories")
    parser.add_argument("dst", help="Destination directory")
    parser.add_argument("--epoch-offset", type=int, default=0, help="ms to subtract from timestamps")
    args = parser.parse_args(argv)

    dst_dir = Path(args.dst)
    dst_dir.mkdir(parents=True, exist_ok=True)

    for s in args.src:
        p = Path(s)
        if p.is_dir():
            for f in p.glob("*.json"):
                _process_file(f, dst_dir, args.epoch_offset)
        else:
            _process_file(p, dst_dir, args.epoch_offset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
