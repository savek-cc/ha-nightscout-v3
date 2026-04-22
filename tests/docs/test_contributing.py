"""Ensure CONTRIBUTING covers the non-negotiable workflow rules."""
from __future__ import annotations

from pathlib import Path

import pytest

CONTRIB = Path("CONTRIBUTING.md")


@pytest.mark.parametrize(
    "needle",
    [
        "DevInstance",
        "ProdInstance",
        "anonymize_fixtures",
        "pytest",
        "ruff",
        "hassfest",
        "verify_silver",
        "conventional commits",
    ],
)
def test_contrib_mentions(needle: str) -> None:
    assert needle in CONTRIB.read_text(encoding="utf-8")
