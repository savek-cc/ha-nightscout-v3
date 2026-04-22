"""Static verifier for the Silver Quality Scale gate.

Exits non-zero if any check fails. Intended to be run from CI and locally
before toggling quality_scale entries from `todo` to `done`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

INTEGRATION = Path("custom_components/nightscout_v3")
SILVER_RULES_REQUIRED = {
    "runtime-data", "config-entry-unloading", "parallel-updates",
    "test-before-configure", "test-before-setup", "unique-config-entry",
    "has-entity-name", "entity-unique-id", "reauthentication-flow",
    "log-when-unavailable", "entity-unavailable", "integration-owner",
    "action-exceptions", "docs-actions", "docs-high-level-description",
    "docs-installation-instructions", "docs-removal-instructions",
    "docs-configuration-parameters",
}


class RuleStatus(str, Enum):
    DONE = "done"
    TODO = "todo"
    EXEMPT = "exempt"


@dataclass
class QsReport:
    statuses: dict[str, RuleStatus] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def _coerce(raw: str) -> RuleStatus:
    if raw in {"done", "todo", "exempt"}:
        return RuleStatus(raw)
    return RuleStatus.TODO


def check_quality_scale_yaml(path: Path) -> QsReport:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    report = QsReport()
    rules = (data or {}).get("rules", {})
    for rule in SILVER_RULES_REQUIRED:
        entry = rules.get(rule)
        if entry is None:
            report.failures.append(rule)
            continue
        if isinstance(entry, str):
            status = _coerce(entry)
            report.statuses[rule] = status
            if status is RuleStatus.TODO:
                report.failures.append(rule)
        elif isinstance(entry, dict):
            status = _coerce(str(entry.get("status", "todo")))
            report.statuses[rule] = status
            if status is RuleStatus.EXEMPT and not entry.get("comment"):
                report.failures.append(f"{rule}:exempt-without-comment")
            elif status is RuleStatus.TODO:
                report.failures.append(rule)
    return report


def _flatten(obj: object, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.update(_flatten(v, key))
            else:
                keys.add(key)
    return keys


def check_translations(root: Path) -> list[str]:
    strings_path = root / "strings.json"
    if not strings_path.exists():
        return []
    strings = json.loads(strings_path.read_text(encoding="utf-8"))
    translations_dir = root / "translations"
    if not translations_dir.exists():
        return []
    missing: list[str] = []
    for locale_file in sorted(translations_dir.glob("*.json")):
        trans = json.loads(locale_file.read_text(encoding="utf-8"))
        trans_keys = _flatten(trans)
        for key in _flatten(strings):
            if key not in trans_keys:
                missing.append(key)
    return missing


def check_parallel_updates(root: Path) -> list[str]:
    missing: list[str] = []
    for platform in ("sensor.py", "binary_sensor.py"):
        p = root / platform
        if not p.exists():
            continue
        if "PARALLEL_UPDATES" not in p.read_text(encoding="utf-8"):
            missing.append(platform)
    return missing


def check_has_entity_name(root: Path) -> list[str]:
    pattern = re.compile(r"_attr_has_entity_name\s*=\s*True")
    offenders: list[str] = []
    entity_file = root / "entity.py"
    if entity_file.exists() and pattern.search(entity_file.read_text(encoding="utf-8")):
        return offenders
    for p in (entity_file, root / "sensor.py", root / "binary_sensor.py"):
        if p.exists() and not pattern.search(p.read_text(encoding="utf-8")):
            offenders.append(p.name)
    return offenders


def check_manifest_declares_silver(root: Path) -> bool:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    return manifest.get("quality_scale") == "silver"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=INTEGRATION)
    parser.add_argument(
        "--strict-manifest", action="store_true",
        help="require manifest.json to declare quality_scale=silver",
    )
    args = parser.parse_args(argv)
    root: Path = args.root

    errors: list[str] = []

    qs = check_quality_scale_yaml(root / "quality_scale.yaml")
    if qs.failures:
        errors.append(f"quality_scale.yaml open rules: {', '.join(sorted(qs.failures))}")

    missing_trans = check_translations(root)
    if missing_trans:
        errors.append(f"translation keys missing: {sorted(set(missing_trans))}")

    missing_pu = check_parallel_updates(root)
    if missing_pu:
        errors.append(f"PARALLEL_UPDATES missing in: {missing_pu}")

    missing_hen = check_has_entity_name(root)
    if missing_hen:
        errors.append(f"_attr_has_entity_name = True missing in: {missing_hen}")

    if args.strict_manifest and not check_manifest_declares_silver(root):
        errors.append("manifest.json does not declare quality_scale=silver")

    if errors:
        sys.stderr.write("\n".join(errors) + "\n")
        return 1
    sys.stdout.write("silver: ok\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
