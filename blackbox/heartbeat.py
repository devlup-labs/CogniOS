#Crash/freeze detection via heartbeat timestamps

import sqlite3
import time
from blackbox.recorder import get_blackbox_conn

def create_heartbeat_table(conn: sqlite3.Connection) -> None:

    # Create a table to store the last heartbeat timestamp
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blackbox_heartbeat (
            id        INTEGER PRIMARY KEY CHECK (id = 1),
            last_beat REAL NOT NULL
        )
    """)
    # Insert an initial heartbeat record if it doesn't exist
    conn.execute("""
        INSERT OR IGNORE INTO blackbox_heartbeat (id, last_beat)
        VALUES (1, ?)
    """, (time.time(),))
    conn.commit()


def update_heartbeat(conn: sqlite3.Connection) -> None:
    # Update the last heartbeat timestamp
    conn.execute("""
        UPDATE blackbox_heartbeat
        SET last_beat = ?
        WHERE id = 1
    """, (time.time(),))
    conn.commit()

# def check_heartbeat(conn: sqlite3.Connection, threshold_seconds: float = 10.0) -> tuple[bool, float]:
#     # Check if the last heartbeat is within the threshold
#     cursor = conn.execute("""
#         SELECT last_beat FROM blackbox_heartbeat WHERE id = 1
#     """)
#     row = cursor.fetchone()
#     if row is None:
#         return False, 0.0  # No heartbeat record found
#     gap = time.time() - row[0]
#     return gap > 10.0, round(gap, 1) 