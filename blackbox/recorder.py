"""Rolling 30-minute telemetry recorder."""
import time
import sqlite3
from config import BLACKBOX_DB_PATH, BLACKBOX_WINDOW_SEC
from pathlib import Path


def get_blackbox_conn() -> sqlite3.Connection:
    Path(BLACKBOX_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(BLACKBOX_DB_PATH, check_same_thread=False)

    # WAL mode: crash-safe writes — data survive karta hai daemon crash pe bhi
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def create_blackbox_table(conn):
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
    conn.commit()

BLACKBOX_METRICS_KEYS = {
    'timestamp', 'cpu_usage_percent', 'cpu_ctx_switches',
    'cpu_busy_time', 'cpu_iowait_time', 'memory_percent',
    'memory_used', 'swap_percent', 'disk_read', 'disk_write',
    'net_rate_mb_s', 'net_bytes_sent', 'net_bytes_received',
    'total_processes', 'running_processes', 'zombie_processes',
    'load_avg1', 'load_avg5', 'avg_temp',
}

def write_telemetry(conn: sqlite3.Connection, metrics: dict) -> None:

    data = {k: v for k, v in metrics.items() if k in BLACKBOX_METRICS_KEYS}
    # Ensure numeric timestamp
    data['timestamp'] = time.time()

    cols         = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    conn.execute(
        f"INSERT INTO blackbox_telemetry ({cols}) VALUES ({placeholders})",
        list(data.values())
    )
    conn.commit()
    prune_old_records(conn)


def prune_old_records(conn: sqlite3.Connection) -> None:
    cutoff = time.time() - BLACKBOX_WINDOW_SEC
    conn.execute(
        "DELETE FROM blackbox_telemetry WHERE timestamp < ?",
        (cutoff,)
    )
    conn.commit()


def get_recent_rows(conn: sqlite3.Connection, n: int = 120) -> list[dict]:

    """ useful for feture engineering or correlation analysis of telemetry data """
    cursor = conn.execute("""
        SELECT * FROM blackbox_telemetry
        ORDER BY timestamp DESC
        LIMIT ?
    """, (n,))
    cols = [d[0] for d in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    return list(reversed(rows))  # Return in chronological order


def get_window_rows(conn: sqlite3.Connection,
                    start_time: float,
                    end_time: float) -> list[dict]:
    """ fetch specific window of telemetry data for analysis """
    cursor = conn.execute("""
        SELECT * FROM blackbox_telemetry
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp ASC
    """, (start_time, end_time))
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def row_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM blackbox_telemetry"
    ).fetchone()[0]