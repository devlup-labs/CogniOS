import sqlite3
import json 
import time

from config import ALERTS_DB_PATH, ALERTS_TABLE_NAME, DB_PATH

def _harden_connection(conn):
    """Best-effort per-connection pragmas. journal_mode is a one-time, whole-file
    switch — see ensure_wal_mode() for the race-free way to enable it up front."""
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def ensure_wal_mode(db_path=ALERTS_DB_PATH):
    """Switch the DB file to WAL mode once, via a single connection, before any
    concurrent writers open their own connections. Doing this per-connection from
    multiple threads/processes at once races on the initial (non-WAL -> WAL) file
    header rewrite and can raise 'database is locked' even with busy_timeout set."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.close()

def create_connection(db_path=ALERTS_DB_PATH):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    _harden_connection(conn)
    return conn

def init_alerts_db(conn=None):
    """
    Initializes alerts table matching OS Doctor specifications.
    """
    should_close = False
    if conn is None:
        conn = create_connection(ALERTS_DB_PATH)
        should_close = True

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS {ALERTS_TABLE_NAME} (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            metadata  TEXT NOT NULL,
            data      TEXT NOT NULL
        )
    ''')
    conn.commit()

def write_to_alerts_table(data, metadata):
    """
    Stores detected anomaly payload (raw + scaled) alongside metadata.
    data: Dictionary containing "raw" and "scaled" metrics
    metadata: Dictionary containing process/system metadata
    """
    conn = create_connection(ALERTS_DB_PATH)
    init_alerts_db(conn)
    conn.execute(
        f"INSERT INTO {ALERTS_TABLE_NAME} (timestamp, metadata, data) VALUES (?, ?, ?)",
        (
            time.time(),
            json.dumps(metadata, separators=(',', ':')),
            json.dumps(data, separators=(',', ':'))
        )
    )
    conn.commit()
    conn.close()

