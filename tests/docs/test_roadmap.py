"""Roadmap must list the four headline out-of-scope items."""

from __future__ import annotations

from pathlib import Path

import pytest

ROADMAP = Path("docs/roadmap.md")


@pytest.mark.parametrize(
    "needle",
    [
        "Gold",
        "AAPS write-back",
        "BG chart",
        "xDrip+",
    ],
)
def test_roadmap_mentions(needle: str) -> None:
    assert needle in ROADMAP.read_text(encoding="utf-8")
