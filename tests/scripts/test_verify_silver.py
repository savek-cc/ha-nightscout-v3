"""Tests for the silver verifier."""
from __future__ import annotations

from pathlib import Path

from scripts.verify_silver import (
    RuleStatus,
    check_has_entity_name,
    check_manifest_declares_silver,
    check_parallel_updates,
    check_quality_scale_yaml,
    check_translations,
    main,
)


def test_quality_scale_detects_missing_rule(tmp_path: Path) -> None:
    qs = tmp_path / "quality_scale.yaml"
    qs.write_text(
        "rules:\n"
        "  runtime-data: done\n"
        "  test-before-configure: todo\n",
        encoding="utf-8",
    )
    report = check_quality_scale_yaml(qs)
    assert RuleStatus.DONE == report.statuses["runtime-data"]
    assert "test-before-configure" in report.failures


def test_quality_scale_exempt_requires_comment(tmp_path: Path) -> None:
    qs = tmp_path / "quality_scale.yaml"
    qs.write_text(
        "rules:\n"
        "  docs-actions:\n"
        "    status: exempt\n"
        "    comment: N/A\n"
        "  action-exceptions:\n"
        "    status: exempt\n",
        encoding="utf-8",
    )
    report = check_quality_scale_yaml(qs)
    assert "action-exceptions:exempt-without-comment" in report.failures
    assert "docs-actions:exempt-without-comment" not in report.failures


def test_translations_detects_missing_key(tmp_path: Path) -> None:
    (tmp_path / "strings.json").write_text(
        '{"config": {"step": {"user": {"data": {"host": "Host"}}}}}',
        encoding="utf-8",
    )
    (tmp_path / "translations").mkdir()
    (tmp_path / "translations" / "de.json").write_text(
        '{"config": {"step": {"user": {"data": {}}}}}',
        encoding="utf-8",
    )
    missing = check_translations(tmp_path)
    assert "config.step.user.data.host" in missing


def test_translations_no_strings_returns_empty(tmp_path: Path) -> None:
    assert check_translations(tmp_path) == []


def test_parallel_updates_detects_missing(tmp_path: Path) -> None:
    (tmp_path / "sensor.py").write_text("# no parallel updates\n", encoding="utf-8")
    (tmp_path / "binary_sensor.py").write_text(
        "PARALLEL_UPDATES = 0\n", encoding="utf-8"
    )
    missing = check_parallel_updates(tmp_path)
    assert missing == ["sensor.py"]


def test_has_entity_name_ok_when_on_base(tmp_path: Path) -> None:
    (tmp_path / "entity.py").write_text(
        "class X:\n    _attr_has_entity_name = True\n", encoding="utf-8"
    )
    assert check_has_entity_name(tmp_path) == []


def test_has_entity_name_detects_missing(tmp_path: Path) -> None:
    (tmp_path / "entity.py").write_text("class X:\n    pass\n", encoding="utf-8")
    (tmp_path / "sensor.py").write_text("class S:\n    pass\n", encoding="utf-8")
    (tmp_path / "binary_sensor.py").write_text(
        "_attr_has_entity_name = True\n", encoding="utf-8"
    )
    offenders = check_has_entity_name(tmp_path)
    assert "entity.py" in offenders
    assert "sensor.py" in offenders
    assert "binary_sensor.py" not in offenders


def test_manifest_declares_silver(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(
        '{"domain": "x", "quality_scale": "silver"}', encoding="utf-8"
    )
    assert check_manifest_declares_silver(tmp_path) is True


def test_manifest_missing_silver(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text('{"domain": "x"}', encoding="utf-8")
    assert check_manifest_declares_silver(tmp_path) is False


def test_main_happy_path(tmp_path: Path, capsys) -> None:
    qs = "rules:\n" + "".join(
        f"  {r}: done\n" for r in [
            "runtime-data", "config-entry-unloading", "parallel-updates",
            "test-before-configure", "test-before-setup", "unique-config-entry",
            "has-entity-name", "entity-unique-id", "reauthentication-flow",
            "log-when-unavailable", "entity-unavailable", "integration-owner",
            "action-exceptions", "docs-actions", "docs-high-level-description",
            "docs-installation-instructions", "docs-installation-parameters",
            "docs-removal-instructions", "docs-configuration-parameters",
        ]
    )
    (tmp_path / "quality_scale.yaml").write_text(qs, encoding="utf-8")
    (tmp_path / "strings.json").write_text("{}", encoding="utf-8")
    (tmp_path / "translations").mkdir()
    (tmp_path / "sensor.py").write_text("PARALLEL_UPDATES = 0\n", encoding="utf-8")
    (tmp_path / "binary_sensor.py").write_text("PARALLEL_UPDATES = 0\n", encoding="utf-8")
    (tmp_path / "entity.py").write_text("_attr_has_entity_name = True\n", encoding="utf-8")
    rc = main(["--root", str(tmp_path)])
    assert rc == 0
    assert "silver: ok" in capsys.readouterr().out


def test_main_reports_errors(tmp_path: Path, capsys) -> None:
    (tmp_path / "quality_scale.yaml").write_text("rules:\n  runtime-data: todo\n", encoding="utf-8")
    (tmp_path / "strings.json").write_text("{}", encoding="utf-8")
    (tmp_path / "translations").mkdir()
    (tmp_path / "sensor.py").write_text("# no\n", encoding="utf-8")
    (tmp_path / "binary_sensor.py").write_text("# no\n", encoding="utf-8")
    (tmp_path / "entity.py").write_text("# no\n", encoding="utf-8")
    rc = main(["--root", str(tmp_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "runtime-data" in err
    assert "PARALLEL_UPDATES" in err
    assert "_attr_has_entity_name" in err
