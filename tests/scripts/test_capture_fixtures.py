"""Tests for capture_fixtures CLI arg parsing (no network)."""

from __future__ import annotations

import pytest

from scripts.capture_fixtures import build_client_config


def test_requires_ns_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NS_URL", raising=False)
    monkeypatch.delenv("NS_TOKEN", raising=False)
    monkeypatch.delenv("NIGHTSCOUT_FORBIDDEN_HOSTS", raising=False)
    with pytest.raises(SystemExit):
        build_client_config()


def test_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NS_URL", "https://example.invalid")
    monkeypatch.setenv("NS_TOKEN", "tok-redacted")
    monkeypatch.delenv("NIGHTSCOUT_FORBIDDEN_HOSTS", raising=False)
    cfg = build_client_config()
    assert cfg.base_url == "https://example.invalid"
    assert cfg.token == "tok-redacted"


def test_strips_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NS_URL", "https://example.invalid/")
    monkeypatch.setenv("NS_TOKEN", "tok")
    monkeypatch.delenv("NIGHTSCOUT_FORBIDDEN_HOSTS", raising=False)
    cfg = build_client_config()
    assert cfg.base_url == "https://example.invalid"


def test_refuses_configured_production_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard-rail: refuses to run against a configured production host."""
    monkeypatch.setenv("NS_URL", "https://prod.example.invalid")
    monkeypatch.setenv("NS_TOKEN", "tok-redacted")
    monkeypatch.setenv("NIGHTSCOUT_FORBIDDEN_HOSTS", "prod.example.invalid")
    with pytest.raises(SystemExit) as exc:
        build_client_config()
    assert exc.value.code == 3


def test_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NS_URL", "https://example.invalid")
    monkeypatch.delenv("NS_TOKEN", raising=False)
    monkeypatch.delenv("NIGHTSCOUT_FORBIDDEN_HOSTS", raising=False)
    with pytest.raises(SystemExit):
        build_client_config()
