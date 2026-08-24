"""Rolling 30-minute telemetry recorder."""
import sqlite3
import threading
import time
from config import BLACKBOX_DB_PATH, BLACKBOX_WINDOW_SEC
from pathlib import Path

_conn_locks: dict = {}


def _get_lock(conn: sqlite3.Connection):
    # Return the Lock registered for this connection, or None
    return _conn_locks.get(id(conn))


def get_blackbox_conn(db_path: str | Path | None = None) -> sqlite3.Connection:
    # Open a Blackbox database connection
    path = Path(db_path or BLACKBOX_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)

    # WAL mode: crash-safe writes — data survive karta hai daemon crash pe bhi
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")

    # Register a dedicated Lock for this connection
    _conn_locks[id(conn)] = threading.Lock()
    return conn


def create_blackbox_table(conn: sqlite3.Connection) -> None:
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        conn.execute("""
            CREATE TABLE IF NOT EXISTS blackbox_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,

                -- CPU Metrics
                cpu_usage_percent   REAL,
                cpu_ctx_switches    REAL,
                cpu_busy_time       REAL,
                cpu_iowait_time     REAL,

                -- Memory Metrics
                memory_percent      REAL,
                memory_used         INTEGER,
                swap_percent        REAL,

                -- Disk Metrics
                disk_read           REAL,
                disk_write          REAL,

                -- Network Metrics
                net_rate_mb_s       REAL,
                net_bytes_sent      INTEGER,
                net_bytes_received  INTEGER,

                -- Process Metrics
                total_processes     INTEGER,
                running_processes   INTEGER,
                zombie_processes    INTEGER,

                -- System load
                load_avg1           REAL,
                load_avg5           REAL,

                -- Hardware
                avg_temp            REAL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_blackbox_telemetry_timestamp "
            "ON blackbox_telemetry (timestamp)"
        )
        _prune_old_records(conn)
        conn.commit()

BLACKBOX_METRICS_KEYS: list[str] = [
    'timestamp',
    'cpu_usage_percent', 'cpu_ctx_switches', 'cpu_busy_time', 'cpu_iowait_time',
    'memory_percent', 'memory_used', 'swap_percent',
    'disk_read', 'disk_write',
    'net_rate_mb_s', 'net_bytes_sent', 'net_bytes_received',
    'total_processes', 'running_processes', 'zombie_processes',
    'load_avg1', 'load_avg5',
    'avg_temp',
]

class _noop_ctx:
    """Fallback context manager for connections created without a lock."""
    def __enter__(self): return self
    def __exit__(self, *_): pass


def write_telemetry(conn: sqlite3.Connection, metrics: dict) -> None:
    data: dict = {k: metrics.get(k) for k in BLACKBOX_METRICS_KEYS}
    # Always store a float timestamp for time-range queries
    if data.get('timestamp') is None or not isinstance(data['timestamp'], (int, float)):
        data['timestamp'] = time.time()

    cols         = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)

    # acquire lock before writing (shared connection across threads)
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        conn.execute(
            f"INSERT INTO blackbox_telemetry ({cols}) VALUES ({placeholders})",
            list(data.values())
        )
        _prune_old_records(conn)
        conn.commit()


def prune_old_records(conn: sqlite3.Connection) -> None:
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        _prune_old_records(conn)
        conn.commit()


def _prune_old_records(conn: sqlite3.Connection, now: float | None = None) -> None:
    # Delete expired telemetry while the caller holds the connection lock
    cutoff = (time.time() if now is None else now) - BLACKBOX_WINDOW_SEC
    conn.execute("DELETE FROM blackbox_telemetry WHERE timestamp < ?", (cutoff,))


def get_window_rows(conn: sqlite3.Connection,
                    start_time: float,
                    end_time: float) -> list[dict]:
    # Fetch telemetry in the requested inclusive time range
    lock = _get_lock(conn)
    with lock if lock else _noop_ctx():
        cursor = conn.execute("""
            SELECT * FROM blackbox_telemetry
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
        """, (start_time, end_time))
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


