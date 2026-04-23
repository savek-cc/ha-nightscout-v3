"""Unit tests for the smoke-test argument surface (no network)."""

from __future__ import annotations

import pytest

from scripts.smoke_test import parse_args, refuse_forbidden_hosts


def test_parses_defaults() -> None:
    ns = parse_args(["--url", "https://example.invalid", "--token", "tok"])
    assert ns.url == "https://example.invalid"
    assert ns.token == "tok"
    assert ns.limit == 3


def test_parses_custom_limit() -> None:
    ns = parse_args(["--url", "https://example.invalid", "--token", "tok", "--limit", "10"])
    assert ns.limit == 10


def test_refuses_configured_production_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NIGHTSCOUT_FORBIDDEN_HOSTS", "prod.example.invalid")
    with pytest.raises(SystemExit) as exc:
        refuse_forbidden_hosts("https://prod.example.invalid")
    assert exc.value.code == 3


def test_allows_non_forbidden_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NIGHTSCOUT_FORBIDDEN_HOSTS", raising=False)
    # Should NOT raise
    refuse_forbidden_hosts("https://example.invalid")
