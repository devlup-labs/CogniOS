"""This file contains the code related to appending to 'Alerts' Database, if Anomaly is detected."""
import sqlite3
import json 
import time

from config import ALERTS_DB_PATH, ALERTS_TABLE_NAME, DB_PATH

def _harden_connection(conn):
    """Best-effort per-connection pragmas."""
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def ensure_wal_mode(db_path=ALERTS_DB_PATH):
    """Switch the DB file to WAL mode once before concurrent writers connect."""
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
    Initializes os_doctor_alerts table matching OS Doctor specifications.
    """
    should_close = False
    if conn is None:
        conn = create_connection(ALERTS_DB_PATH)
        should_close = True

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS {ALERTS_TABLE_NAME} (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        REAL NOT NULL,
            anomaly_type     TEXT NOT NULL,
            severity         TEXT NOT NULL,
            confidence       REAL NOT NULL,
            explanation      TEXT NOT NULL,
            suggested_action TEXT NOT NULL,
            raw_metadata     TEXT NOT NULL
        )
    ''')
    conn.commit()
    if should_close:
        conn.close()

def write_to_alerts_table(data, metadata):
    """
    Extracts LLM output fields and stores them alongside raw metadata.
    data: Dictionary returned by generate_llm_explanation()
    metadata: Dictionary containing raw system telemetry
    """
    conn = create_connection(ALERTS_DB_PATH)

    timestamp = time.time()
    anomaly_type = metadata.get("issue", "high_cpu")
    severity = data.get("severity", "Medium")
    confidence = float(data.get("confidence", 80.0))
    explanation = data.get("cause", "System anomaly detected.")
    suggested_action = data.get("suggested_action", "Check background tasks.")
    raw_metadata = json.dumps(metadata, separators=(',', ':'))

    conn.execute(
        f'''INSERT INTO {ALERTS_TABLE_NAME} 
           (timestamp, anomaly_type, severity, confidence, explanation, suggested_action, raw_metadata) 
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (timestamp, anomaly_type, severity, confidence, explanation, suggested_action, raw_metadata)
    )

    conn.commit()
    conn.close()
