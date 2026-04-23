"""Ensure README advertises the main user-visible promises."""

from __future__ import annotations

from pathlib import Path

import pytest

README = Path("README.md")


@pytest.mark.parametrize(
    "needle",
    [
        "Nightscout v3",
        "HACS",
        "Silver",
        "DevInstance",
        "reauthentication",
        "dashboards/nightscout.yaml",
    ],
)
def test_readme_mentions(needle: str) -> None:
    assert needle in README.read_text(encoding="utf-8")
