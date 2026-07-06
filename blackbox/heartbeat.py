#Crash/freeze detection via heartbeat timestamps

import sqlite3
import time
from config import BLACKBOX_CRASH_GAP_SEC
from blackbox.recorder import _get_lock, _noop_ctx


def create_heartbeat_table(conn: sqlite3.Connection) -> None:
    # single row table to store the last heartbeat timestamp and graceful shutdown flag
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        conn.execute("""
            CREATE TABLE IF NOT EXISTS blackbox_heartbeat (
                id        INTEGER PRIMARY KEY CHECK (id = 1),
                last_beat REAL NOT NULL,
                graceful_shutdown INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Insert an initial heartbeat record if it doesn't exist
        conn.execute("""
            INSERT OR IGNORE INTO blackbox_heartbeat (id, last_beat, graceful_shutdown)
            VALUES (1, ?, 0)
        """, (time.time(),))
        conn.commit()


def update_heartbeat(conn: sqlite3.Connection) -> None:
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        conn.execute("""
            UPDATE blackbox_heartbeat
            SET last_beat = ?
            WHERE id = 1
        """, (time.time(),))
        conn.commit()


def mark_graceful_shutdown(conn: sqlite3.Connection) -> None:
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        conn.execute(
            "UPDATE blackbox_heartbeat SET graceful_shutdown = 1 WHERE id = 1"
        )
        conn.commit()


def check_crash_on_startup(conn: sqlite3.Connection) -> tuple[bool, float]:
    # check if the last run ended gracefully or if there was a crash
    # based on the heartbeat timestamp and graceful shutdown flag.
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        row = conn.execute(
            "SELECT last_beat, graceful_shutdown FROM blackbox_heartbeat WHERE id = 1"
        ).fetchone()

        if row is None:
            return False, 0.0

        last_beat, graceful = row
        gap = round(time.time() - last_beat, 1)

        # Reset flag atomically in the same transaction
        conn.execute(
            "UPDATE blackbox_heartbeat SET graceful_shutdown = 0 WHERE id = 1"
        )
        conn.commit()

    if graceful:
        return False, gap

    return gap > BLACKBOX_CRASH_GAP_SEC, gap