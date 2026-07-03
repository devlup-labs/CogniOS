"""Rolling 30-minute telemetry recorder."""
import time
import sqlite3
from utils.config import DB_PATH, BLACKBOX_WINDOW_SEC


def create_blackbox_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blackbox_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            cpu_usage_percent REAL,
            memory_percent REAL,
            disk_read REAL,
            disk_write REAL,
            net_rate_mb_s REAL,
            cpu_ctx_switches REAL,
            total_processes INTEGER,
            zombie_processes INTEGER,
            swap_percent REAL,
            load_avg1 REAL
        )
    """)
    conn.commit()


def write_telemetry(conn, metrics: dict) -> None:
    conn.execute("""
        INSERT INTO blackbox_telemetry (
            timestamp, cpu_usage_percent, memory_percent,
            disk_read, disk_write, net_rate_mb_s,
            cpu_ctx_switches, total_processes,
            zombie_processes, swap_percent, load_avg1
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        time.time(),
        metrics.get("cpu_usage_percent"),
        metrics.get("memory_percent"),
        metrics.get("disk_read"),
        metrics.get("disk_write"),
        metrics.get("net_rate_mb_s"),
        metrics.get("cpu_ctx_switches"),
        metrics.get("total_processes"),
        metrics.get("zombie_processes"),
        metrics.get("swap_percent"),
        metrics.get("load_avg1"),
    ))
    conn.commit()
    prune_old_records(conn)


def prune_old_records(conn) -> None:
    cutoff = time.time() - BLACKBOX_WINDOW_SEC
    conn.execute("DELETE FROM blackbox_telemetry WHERE timestamp < ?", (cutoff,))
    conn.commit()


def get_recent_rows(conn, n: int = 120) -> list[dict]:
    cursor = conn.execute("""
        SELECT * FROM blackbox_telemetry
        ORDER BY timestamp DESC
        LIMIT ?
    """, (n,))
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    create_blackbox_table(conn)
    