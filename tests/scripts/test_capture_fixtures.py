"""Tests for capture_fixtures CLI arg parsing (no network)."""

from __future__ import annotations

import pytest

from scripts.capture_fixtures import build_client_config


def test_requires_ns_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NS_URL", raising=False)
    monkeypatch.delenv("NS_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        build_client_config()


def test_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NS_URL", "https://example.invalid")
    monkeypatch.setenv("NS_TOKEN", "tok-redacted")
    cfg = build_client_config()
    assert cfg.base_url == "https://example.invalid"
    assert cfg.token == "tok-redacted"


def test_strips_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NS_URL", "https://example.invalid/")
    monkeypatch.setenv("NS_TOKEN", "tok")
    cfg = build_client_config()
    assert cfg.base_url == "https://example.invalid"


def test_refuses_felicia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard-rail: refuses to run against the production host."""
    monkeypatch.setenv("NS_URL", "https://prod-nightscout.example.invalid")
    monkeypatch.setenv("NS_TOKEN", "tok-redacted")
    with pytest.raises(SystemExit) as exc:
        build_client_config()
    assert exc.value.code == 3


def test_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NS_URL", "https://example.invalid")
    monkeypatch.delenv("NS_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        build_client_config()
