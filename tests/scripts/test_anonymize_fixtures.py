"""Tests for anonymize_fixtures script."""

from __future__ import annotations

import json

from scripts.anonymize_fixtures import anonymize_payload


def test_redacts_urls_tokens_and_notes() -> None:
    raw = {
        "status": "OK",
        "result": [
            {
                "_id": "abc123def456",
                "sgv": 142,
                "direction": "Flat",
                "date": 1713780000000,
                "notes": "ate pizza at CornerCafe's",
                "enteredBy": "user@example.invalid",
                "url": "https://dev-nightscout.example.invalid/api/v3/entries",
            }
        ],
    }
    anon = anonymize_payload(raw, epoch_offset_ms=1713780000000)
    entry = anon["result"][0]
    assert entry["sgv"] == 142
    assert entry["direction"] == "Flat"
    assert entry["date"] == 0
    assert "CornerCafe" not in json.dumps(anon)
    assert "example-private" not in json.dumps(anon)
    assert "timm" not in json.dumps(anon).lower()
    assert entry["_id"] != "abc123def456"
    assert len(entry["_id"]) == 24


def test_treatment_carbs_bucketed() -> None:
    raw = {
        "status": "OK",
        "result": [{"eventType": "Meal Bolus", "carbs": 47, "insulin": 3.1, "date": 1713780000000}],
    }
    anon = anonymize_payload(raw, epoch_offset_ms=1713780000000)
    t = anon["result"][0]
    assert t["carbs"] in (40, 50)
    assert t["insulin"] == 3.1


def test_preserves_status_envelope() -> None:
    raw = {"status": "OK", "result": []}
    assert anonymize_payload(raw, epoch_offset_ms=0) == raw


def test_main_writes_dst(tmp_path) -> None:
    from scripts.anonymize_fixtures import main

    src = tmp_path / "entries.json"
    src.write_text(json.dumps({"status": "OK", "result": [{"sgv": 100}]}), encoding="utf-8")
    dst = tmp_path / "out"
    rc = main([str(src), str(dst), "--epoch-offset", "0"])
    assert rc == 0
    written = json.loads((dst / "entries.json").read_text(encoding="utf-8"))
    assert written["result"][0]["sgv"] == 100


def test_redacts_device_and_pump_identifiers() -> None:
    raw = {
        "status": "OK",
        "result": [
            {
                "_id": "abc",
                "identifier": "real-patient-uuid",
                "device": "xDrip-DexbridgeWixel-12345",
                "pumpSerial": "PUMP_10154415",
                "pumpType": "Medtronic 722",
                "ActiveProfile": "primary-user-profile",
                "reason": "sensitivity raised to 1.3 because pump at CornerCafe's",
                "pumpId": "xyz-pump-id",
                "Version": "AAPS build abc123",
                "sgv": 100,
            }
        ],
    }
    anon = anonymize_payload(raw, epoch_offset_ms=0)
    dumped = json.dumps(anon)
    for leaked in (
        "xDrip-DexbridgeWixel-12345",
        "PUMP_10154415",
        "Medtronic",
        "primary-user-profile",
        "CornerCafe",
        "AAPS build",
        "real-patient-uuid",
        "xyz-pump-id",
    ):
        assert leaked not in dumped, f"leak: {leaked}"
    # numeric shape preserved
    assert anon["result"][0]["sgv"] == 100


def test_main_processes_directory(tmp_path) -> None:
    from scripts.anonymize_fixtures import main

    src_dir = tmp_path / "captures"
    src_dir.mkdir()
    (src_dir / "a.json").write_text(json.dumps({"status": "OK", "result": []}), encoding="utf-8")
    (src_dir / "b.json").write_text(json.dumps({"status": "OK", "result": []}), encoding="utf-8")
    dst = tmp_path / "out"
    rc = main([str(src_dir), str(dst)])
    assert rc == 0
    assert (dst / "a.json").exists()
    assert (dst / "b.json").exists()
