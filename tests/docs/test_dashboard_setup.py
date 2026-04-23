"""Ensure dashboard-setup doc names every required HACS plugin + shipped asset."""

from __future__ import annotations

from pathlib import Path

import pytest

DOC = Path("docs/dashboard-setup.md")


@pytest.mark.parametrize(
    "needle",
    [
        "apexcharts-card",
        "mini-graph-card",
        "mushroom",
        "card-mod",
        "dashboards/nightscout.yaml",
        "dashboards/examples/",
    ],
)
def test_dash_doc_mentions(needle: str) -> None:
    assert needle in DOC.read_text(encoding="utf-8")
