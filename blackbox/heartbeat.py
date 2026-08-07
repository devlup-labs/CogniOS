"""Crash/freeze detection via heartbeat timestamps and systemd journal analysis."""

import sqlite3
import time
import subprocess
from config import BLACKBOX_CRASH_GAP_SEC
from blackbox.recorder import _get_lock, _noop_ctx


# ── Heartbeat table ──────────────────────────────────────────────────────────

def create_heartbeat_table(conn: sqlite3.Connection) -> None:
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        conn.execute("""
            CREATE TABLE IF NOT EXISTS blackbox_heartbeat (
                id                INTEGER PRIMARY KEY CHECK (id = 1),
                last_beat         REAL    NOT NULL,
                graceful_shutdown INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO blackbox_heartbeat (id, last_beat, graceful_shutdown)
            VALUES (1, ?, 0)
        """, (time.time(),))
        conn.commit()


def update_heartbeat(conn: sqlite3.Connection) -> None:
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        conn.execute(
            "UPDATE blackbox_heartbeat SET last_beat = ? WHERE id = 1",
            (time.time(),)
        )
        conn.commit()


def mark_graceful_shutdown(conn: sqlite3.Connection) -> None:
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        conn.execute(
            "UPDATE blackbox_heartbeat SET graceful_shutdown = 1 WHERE id = 1"
        )
        conn.commit()


def check_crash_on_startup(conn: sqlite3.Connection) -> tuple[bool, float]:
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        row = conn.execute(
            "SELECT last_beat, graceful_shutdown FROM blackbox_heartbeat WHERE id = 1"
        ).fetchone()

    if row is None:
        return False, 0.0

    last_beat, graceful = row
    gap = round(time.time() - last_beat, 1)

    conn.execute(
        "UPDATE blackbox_heartbeat SET graceful_shutdown = 0 WHERE id = 1"
    )
    conn.commit()

    if graceful:
        return False, gap

    return gap > BLACKBOX_CRASH_GAP_SEC, gap


# ── Systemd journal crash detection ─────────────────────────────────────────

def detect_crash_via_systemd() -> bool:
    result = subprocess.run(
        ["journalctl", "-b", "-1", "-n", "10", "--no-pager"],
        capture_output=True, text=True
    )
    output = result.stdout.lower()

    clean_signals = ["power-off", "shutdown", "reboot", "stopped target"]
    crash_signals = ["kernel panic", "oom", "out of memory", "segfault"]

    if any(s in output for s in crash_signals):
        return True
    if any(s in output for s in clean_signals):
        return False
    return True


# ── Combined startup check ───────────────────────────────────────────────────

def full_crash_check(conn: sqlite3.Connection) -> dict:
    """
    Runs both heartbeat and systemd checks on startup.
    Returns a dict with results from both so the daemon can decide what to do.
    """
    hb_crashed, gap = check_crash_on_startup(conn)
    sys_crashed = detect_crash_via_systemd()

    return {
        "heartbeat_crash": hb_crashed,
        "heartbeat_gap":   gap,
        "systemd_crash":   sys_crashed,
        "any_crash":       hb_crashed or sys_crashed,
    }


# ── Test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Testing detect_crash_via_systemd ===\n")
    result = subprocess.run(
        ["journalctl", "-b", "-1", "-n", "10", "--no-pager"],
        capture_output=True, text=True
    )
    print("--- Last 10 lines of previous boot ---")
    print(result.stdout if result.stdout else "No previous boot logs found.")
    print("--------------------------------------\n")

    if not result.stdout.strip():
        print("No previous boot found — either first boot or logs are cleared.")
    else:
        crashed = detect_crash_via_systemd()
        print(f"detect_crash_via_systemd() returned: {crashed}")
        print(f"Conclusion: {'CRASH detected' if crashed else 'Clean shutdown detected'}")