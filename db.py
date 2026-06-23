"""Shared database schema and read/write interface."""
import sqlite3
import time

DB_NAME = "cognios_telemetry.db"

def init_db():
    """Initializes separate structural tables for CPU and Memory metrics."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Table 1: Dedicated CPU telemetry
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS top_cpu_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                pid INTEGER NOT NULL,
                name TEXT NOT NULL,
                cpu_percent REAL NOT NULL,
                memory_percent REAL NOT NULL,
                rss_memory INTEGER NOT NULL,
                vms_memory INTEGER NOT NULL,
                thread_count INTEGER NOT NULL,
                read_bytes_sec REAL NOT NULL,
                write_bytes_sec REAL NOT NULL,
                status TEXT NOT NULL
            )
        """)
        
        # Table 2: Dedicated RAM telemetry
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS top_ram_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                pid INTEGER NOT NULL,
                name TEXT NOT NULL,
                cpu_percent REAL NOT NULL,
                memory_percent REAL NOT NULL,
                rss_memory INTEGER NOT NULL,
                vms_memory INTEGER NOT NULL,
                thread_count INTEGER NOT NULL,
                read_bytes_sec REAL NOT NULL,
                write_bytes_sec REAL NOT NULL,
                status TEXT NOT NULL
            )
        """)
        conn.commit()


def _map_to_rows(process_list, current_timestamp):
    """Helper function to transform list of dicts to flat tuples for SQLite."""
    return [
        (
            current_timestamp,
            p['pid'],
            p['name'],
            p['cpu_percent'],
            p['memory_percent'],
            p['rss_memory'],
            p['vms_memory'],
            p['thread_count'],
            p['read_bytes_sec'],
            p['write_bytes_sec'],
            p['status']
        )
        for p in process_list
    ]


def insert_separated_telemetry(top_cpu, top_mem):
    """
    Inserts data cleanly into their respective tables.
    Even if a process exists in both lists, it is safely recorded 
    in both metrics tables under the same time block window.
    """
    current_timestamp = time.time()
    
    # Map the dictionaries into raw tuple rows
    cpu_rows = _map_to_rows(top_cpu, current_timestamp)
    ram_rows = _map_to_rows(top_mem, current_timestamp)

    insert_query = """
        INSERT INTO {} (
            timestamp, pid, name, cpu_percent, memory_percent, 
            rss_memory, vms_memory, thread_count, read_bytes_sec, 
            write_bytes_sec, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        

        if cpu_rows:
            cursor.executemany(insert_query.format("top_cpu_telemetry"), cpu_rows)
        
        if ram_rows:
            cursor.executemany(insert_query.format("top_ram_telemetry"), ram_rows)
            
        conn.commit()