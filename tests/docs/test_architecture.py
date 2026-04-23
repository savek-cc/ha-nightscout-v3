"""Ensure architecture doc names the load-bearing modules."""

from __future__ import annotations

from pathlib import Path

import pytest

ARCH = Path("docs/architecture.md")


@pytest.mark.parametrize(
    "needle",
    [
        "JwtManager",
        "NightscoutV3Client",
        "ServerCapabilities",
        "DataUpdateCoordinator",
        "HistoryStore",
        "FEATURE_REGISTRY",
        "runtime_data",
    ],
)
def test_arch_mentions(needle: str) -> None:
    assert needle in ARCH.read_text(encoding="utf-8")
