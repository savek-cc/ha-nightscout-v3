"""Tests for HistoryStore."""
from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.nightscout_v3.history_store import HistoryStore, SyncState


@pytest.fixture
async def store(tmp_path: Path):
    s = await HistoryStore.open(tmp_path / "history.db")
    try:
        yield s
    finally:
        await s.close()


async def test_schema_version_is_1(store: HistoryStore) -> None:
    assert await store.schema_version() == 1


async def test_insert_batch_and_window(store: HistoryStore) -> None:
    rows = [
        {
            "identifier": f"id-{i:04d}",
            "date": 1_745_000_000_000 + i * 300_000,
            "sgv": 140 + i,
            "direction": "Flat",
            "type": "sgv",
            "noise": 0,
            "srvModified": 1_745_000_000_000 + i * 300_000 + 1,
        }
        for i in range(10)
    ]
    inserted = await store.insert_batch(rows)
    assert inserted == 10
    window = await store.entries_in_window(days=365 * 30)
    assert len(window) == 10


async def test_insert_batch_is_idempotent(store: HistoryStore) -> None:
    rows = [
        {"identifier": "same", "date": 1, "sgv": 100, "direction": "Flat",
         "type": "sgv", "noise": 0, "srvModified": 1}
    ]
    assert await store.insert_batch(rows) == 1
    assert await store.insert_batch(rows) == 0


async def test_sync_state_roundtrip(store: HistoryStore) -> None:
    await store.update_sync_state("entries", last_modified=5, oldest_date=1, newest_date=10)
    state = await store.get_sync_state("entries")
    assert state == SyncState(
        collection="entries", last_modified=5, oldest_date=1, newest_date=10, updated_at_ms=state.updated_at_ms
    )


async def test_prune_removes_old(store: HistoryStore) -> None:
    rows = [
        {"identifier": "old", "date": 1_000_000_000_000, "sgv": 90, "direction": "Flat",
         "type": "sgv", "noise": 0, "srvModified": 1},
        {"identifier": "new", "date": 1_745_000_000_000, "sgv": 150, "direction": "Flat",
         "type": "sgv", "noise": 0, "srvModified": 2},
    ]
    await store.insert_batch(rows)
    removed = await store.prune(keep_days=7, now_ms=1_745_000_000_000)
    assert removed == 1
    remaining = await store.entries_in_window(days=365 * 30)
    assert len(remaining) == 1
    assert remaining[0]["identifier"] == "new"


async def test_stats_cache_roundtrip(store: HistoryStore) -> None:
    payload = {"window_days": 14, "mean": 136.2}
    await store.set_stats_cache(14, payload)
    got = await store.get_stats_cache(14)
    assert got["mean"] == 136.2


async def test_detects_corruption(tmp_path: Path) -> None:
    db = tmp_path / "broken.db"
    db.write_bytes(b"not a sqlite database")
    store = await HistoryStore.open(db)
    try:
        assert await store.is_corrupt() is True
        backup = await store.recover_from_corruption()
        assert backup.exists()
        assert await store.is_corrupt() is False
    finally:
        await store.close()
