"""aiosqlite-backed rolling history for Nightscout v3 entries."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

_LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1

_DDL = [
    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY) WITHOUT ROWID",
    "CREATE TABLE IF NOT EXISTS entries ("
    "  identifier   TEXT PRIMARY KEY,"
    "  date         INTEGER NOT NULL,"
    "  sgv          INTEGER NOT NULL,"
    "  direction    TEXT,"
    "  type         TEXT NOT NULL,"
    "  noise        INTEGER,"
    "  srv_modified INTEGER NOT NULL"
    ") WITHOUT ROWID",
    "CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(date DESC)",
    "CREATE TABLE IF NOT EXISTS sync_state ("
    "  collection     TEXT PRIMARY KEY,"
    "  last_modified  INTEGER NOT NULL,"
    "  oldest_date    INTEGER NOT NULL,"
    "  newest_date    INTEGER NOT NULL,"
    "  updated_at_ms  INTEGER NOT NULL"
    ") WITHOUT ROWID",
    "CREATE TABLE IF NOT EXISTS stats_cache ("
    "  window_days  INTEGER PRIMARY KEY,"
    "  computed_at  INTEGER NOT NULL,"
    "  payload      TEXT NOT NULL"
    ") WITHOUT ROWID",
]


@dataclass(slots=True, frozen=True)
class SyncState:
    """Per-collection sync state."""

    collection: str
    last_modified: int
    oldest_date: int
    newest_date: int
    updated_at_ms: int


class HistoryStore:
    """aiosqlite-backed rolling history for a single config entry."""

    def __init__(self, path: Path, db: aiosqlite.Connection) -> None:
        """Initialize the history store with an open aiosqlite connection."""
        self._path = path
        self._db = db

    @classmethod
    async def open(cls, path: Path) -> HistoryStore:
        """Open (or create) the history store at the given path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(path)
        db.row_factory = aiosqlite.Row
        store = cls(path, db)
        await store._initialize_schema()
        return store

    async def close(self) -> None:
        """Close the underlying aiosqlite connection."""
        await self._db.close()

    async def schema_version(self) -> int:
        """Return the persisted schema version, or 0 if missing."""
        async with self._db.execute("SELECT version FROM schema_version LIMIT 1") as cur:
            row = await cur.fetchone()
        return int(row["version"]) if row else 0

    async def insert_batch(self, entries: list[dict[str, Any]]) -> int:
        """Insert SGV entries (ignoring duplicates) and return the number newly added.

        Nightscout's `entries` collection is mixed: sgv, mbg, cal, smb, etc.
        Only sgv rows carry a `sgv` reading; everything else is skipped here
        since the stats pipeline downstream is CGM-only.
        """
        if not entries:
            return 0
        rows = [
            (
                e["identifier"],
                int(e["date"]),
                int(e["sgv"]),
                e.get("direction"),
                e.get("type", "sgv"),
                e.get("noise"),
                int(e.get("srvModified", e["date"])),
            )
            for e in entries
            if e.get("sgv") is not None and e.get("identifier")
        ]
        if not rows:
            return 0
        async with self._db.execute("SELECT COUNT(*) AS n FROM entries") as cur:
            before = (await cur.fetchone())["n"]
        await self._db.executemany(
            "INSERT OR IGNORE INTO entries "
            "(identifier, date, sgv, direction, type, noise, srv_modified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        await self._db.commit()
        async with self._db.execute("SELECT COUNT(*) AS n FROM entries") as cur:
            after = (await cur.fetchone())["n"]
        return int(after - before)

    async def entries_in_window(
        self, days: int, *, now_ms: int | None = None
    ) -> list[dict[str, Any]]:
        """Return entries within the last `days` days, oldest first."""
        now_ms = now_ms or int(time.time() * 1000)
        cutoff = now_ms - days * 86_400_000
        async with self._db.execute(
            "SELECT identifier, date, sgv, direction, type, noise, srv_modified "
            "FROM entries WHERE date >= ? ORDER BY date ASC",
            (cutoff,),
        ) as cur:
            return [dict(row) async for row in cur]

    async def get_sync_state(self, collection: str) -> SyncState | None:
        """Return the sync state for a collection, or None if missing."""
        async with self._db.execute(
            "SELECT collection, last_modified, oldest_date, newest_date, updated_at_ms "
            "FROM sync_state WHERE collection = ?",
            (collection,),
        ) as cur:
            row = await cur.fetchone()
        return SyncState(**dict(row)) if row else None

    async def update_sync_state(
        self, collection: str, *, last_modified: int, oldest_date: int, newest_date: int
    ) -> None:
        """Upsert the sync state row for a collection."""
        now_ms = int(time.time() * 1000)
        await self._db.execute(
            "INSERT INTO sync_state "
            "(collection, last_modified, oldest_date, newest_date, updated_at_ms) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(collection) DO UPDATE SET "
            "  last_modified = excluded.last_modified,"
            "  oldest_date   = excluded.oldest_date,"
            "  newest_date   = excluded.newest_date,"
            "  updated_at_ms = excluded.updated_at_ms",
            (collection, last_modified, oldest_date, newest_date, now_ms),
        )
        await self._db.commit()

    async def prune(self, keep_days: int, *, now_ms: int | None = None) -> int:
        """Delete entries older than `keep_days` and return the row count removed."""
        now_ms = now_ms or int(time.time() * 1000)
        cutoff = now_ms - keep_days * 86_400_000
        cur = await self._db.execute("DELETE FROM entries WHERE date < ?", (cutoff,))
        await self._db.commit()
        return cur.rowcount or 0

    async def get_stats_cache(self, window_days: int) -> dict[str, Any] | None:
        """Return the cached stats payload for a window, or None if missing."""
        async with self._db.execute(
            "SELECT payload FROM stats_cache WHERE window_days = ?", (window_days,)
        ) as cur:
            row = await cur.fetchone()
        return json.loads(row["payload"]) if row else None

    async def set_stats_cache(self, window_days: int, payload: dict[str, Any]) -> None:
        """Upsert the cached stats payload for a window."""
        await self._db.execute(
            "INSERT INTO stats_cache (window_days, computed_at, payload) VALUES (?, ?, ?) "
            "ON CONFLICT(window_days) DO UPDATE SET "
            "  computed_at = excluded.computed_at,"
            "  payload     = excluded.payload",
            (window_days, int(time.time() * 1000), json.dumps(payload)),
        )
        await self._db.commit()

    async def is_corrupt(self) -> bool:
        """Return True if SQLite integrity_check reports a problem."""
        try:
            async with self._db.execute("PRAGMA integrity_check") as cur:
                row = await cur.fetchone()
        except (aiosqlite.Error, sqlite3.Error):
            return True
        return not row or row[0] != "ok"

    async def recover_from_corruption(self) -> Path:
        """Move the broken file aside and re-initialize."""
        await self._db.close()
        backup = self._path.with_suffix(self._path.suffix + f".broken.{int(time.time())}")
        self._path.rename(backup)
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._initialize_schema()
        return backup

    async def _initialize_schema(self) -> None:
        try:
            for stmt in _DDL:
                await self._db.execute(stmt)
            await self._db.execute(
                "INSERT OR IGNORE INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
            )
            await self._db.commit()
        except sqlite3.DatabaseError:
            _LOGGER.warning(
                "Cannot initialize schema on %s; file may be corrupt. "
                "is_corrupt() will return True; call recover_from_corruption() to rebuild.",
                self._path,
            )
