
import sqlite3
import time
import subprocess
from config import BLACKBOX_CRASH_GAP_SEC
from blackbox.recorder import _get_lock, _noop_ctx


JOURNALCTL_TIMEOUT_SEC = 5


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
    # Record a clean exit and the time at which it was requested
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        conn.execute(
            """UPDATE blackbox_heartbeat
               SET last_beat = ?, graceful_shutdown = 1
               WHERE id = 1""",
            (time.time(),),
        )
        conn.commit()


def check_crash_on_startup(conn: sqlite3.Connection) -> tuple[bool, float]:
    # Return whether the prior run appears to have stopped unexpectedly
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        row = conn.execute(
            "SELECT last_beat, graceful_shutdown FROM blackbox_heartbeat WHERE id = 1"
        ).fetchone()

        if row is not None:
            conn.execute(
                "UPDATE blackbox_heartbeat SET graceful_shutdown = 0 WHERE id = 1"
            )
            conn.commit()

    if row is None:
        return False, 0.0

    last_beat, graceful = row
    # A clock correction can put last_beat slightly in the future.  A negative
    # duration is not meaningful to callers and must not look like a crash.

    gap = max(0.0, round(time.time() - last_beat, 1))

    if graceful:
        return False, gap

    return gap > BLACKBOX_CRASH_GAP_SEC, gap


def detect_crash_via_systemd() -> bool:
    """Conservatively classify the end of the previous boot from journald.

    The daemon must still start on machines without systemd or retained journal
    history, so journalctl failures are converted into a suspicious result
    instead of propagating an exception from startup.
    """
    try:
        result = subprocess.run(
            ["journalctl", "-b", "-1", "-n", "10", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=JOURNALCTL_TIMEOUT_SEC,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True

    output = result.stdout.lower()

    # journalctl returns a non-zero status when no previous boot is available.
    # With no usable journal evidence, preserve the existing fail-safe result.
    if result.returncode != 0 and not output.strip():
        return True

    clean_signals = ["power-off", "shutdown", "reboot", "stopped target"]
    crash_signals = ["kernel panic", "oom", "oom-killer", "out of memory", "segfault"]

    if any(s in output for s in crash_signals):
        return True
    if any(s in output for s in clean_signals):
        return False
    return True


# Combined startup check

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
