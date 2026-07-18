"""Shared database schema and read/write interface."""
import json
import sqlite3
import time
from config import DB_PATH

# layer 2 db code starts here


def init_db():
    """Initializes the unified process_snapshot table for Layer 2 telemetry."""
    with sqlite3.connect(DB_PATH,timeout=10.0) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS process_snapshot (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp           REAL    NOT NULL,
                top_cpu_processes   TEXT    NOT NULL,
                top_ram_processes   TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshot_ts
            ON process_snapshot (timestamp)
        """)
        conn.commit()


def insert_process_snapshot(top_cpu, top_ram):
    """Writes one unified row per 5-second poll — timestamp + two compact JSON arrays."""
    row = (
        time.time(),
        json.dumps(top_cpu, separators=(',', ':')),
        json.dumps(top_ram, separators=(',', ':'))
    )
    with sqlite3.connect(DB_PATH,timeout=10.0) as conn:
        conn.execute(
            "INSERT INTO process_snapshot (timestamp, top_cpu_processes, top_ram_processes) VALUES (?, ?, ?)",
            row
        )
        conn.commit()

# layer 2 db code ends here

# layer 1 db code starts here


db_path = DB_PATH

# Creating table for all the metrics collected from the system

def create_connection(db_path):
    conn = sqlite3.connect(db_path,timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS layer1_sys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,

            --CPU Metrics
            cpu_usage_percent REAL,
            cpu_freq REAL,
            cpu_user_time REAL,
            cpu_system_time REAL,
            cpu_idle_time REAL,
            cpu_iowait_time REAL,
            cpu_busy_time REAL,
            cpu_ctx_switches REAL,   

            --Memory Metrics
            memory_percent REAL,
            memory_used INTEGER,     
            memory_available INTEGER,
            memory_cached INTEGER,
            memory_buffers INTEGER,
            swap_percent REAL,
            swap_sin INTEGER,
            swap_sout INTEGER,
                   
            --Disk Metrics
            disk_usage_percent REAL,
            disk_read_mb_s REAL,
            disk_write_mb_s REAL,
            disk_read_time INTEGER,
            disk_write_time INTEGER,
                   
            --Network Metrics
            net_rate_mb_s REAL,
            net_bytes_sent INTEGER,
            net_bytes_recv INTEGER,
            net_packets_sent INTEGER,
            net_packets_recv INTEGER,
            net_errs INTEGER,
            net_drops INTEGER,
                   
            --System Metrics
            load_avg_1 REAL,
            load_avg_5 REAL,
            load_avg_15 REAL,
            total_processes INTEGER,
            running_processes INTEGER,
            sleeping_processes INTEGER,
            zombie_processes INTEGER,
                   
            --Hardware Metrics
            avg_temp REAL,
            max_temp REAL,
            battery_percent REAL,
            process_data TEXT,
            num_threads INTEGER
        )
    ''')

    # Ensure num_threads column exists for older database instances
    cursor.execute("PRAGMA table_info(layer1_sys)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'num_threads' not in columns:
        cursor.execute("ALTER TABLE layer1_sys ADD COLUMN num_threads INTEGER")

    conn.commit()
    return conn

# Function to write the collected metrics into the database

def write_layer1(conn, timestamp, cpu_usage_percent, cpu_freq, cpu_user_time, cpu_system_time, cpu_idle_time, cpu_iowait_time, cpu_busy_time, cpu_ctx_switches, memory_percent, memory_used, memory_available, memory_cached, memory_buffers, swap_percent, swap_sin, swap_sout, disk_usage_percent, disk_read_mb_s, disk_write_mb_s, disk_read_time, disk_write_time, load_avg_1, load_avg_5, load_avg_15, total_processes, running_processes, sleeping_processes, zombie_processes, avg_temp, max_temp, battery_percent, net_rate_mb_s, net_bytes_sent, net_bytes_recv, net_packets_sent, net_packets_recv, net_errs, net_drops, process_data,num_threads):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO layer1_sys (timestamp, cpu_usage_percent, cpu_freq, cpu_user_time, cpu_system_time, cpu_idle_time, cpu_iowait_time, cpu_busy_time, cpu_ctx_switches, memory_percent, memory_used, memory_available, memory_cached, memory_buffers, swap_percent, swap_sin, swap_sout, disk_usage_percent, disk_read_mb_s, disk_write_mb_s, disk_read_time, disk_write_time, net_rate_mb_s, net_bytes_sent, net_bytes_recv, net_packets_sent, net_packets_recv, net_errs, net_drops, load_avg_1, load_avg_5, load_avg_15, total_processes, running_processes, sleeping_processes, zombie_processes, avg_temp, max_temp, battery_percent, process_data, num_threads)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, 
          cpu_usage_percent, 
          cpu_freq, cpu_user_time, 
          cpu_system_time, 
          cpu_idle_time, 
          cpu_iowait_time,
          cpu_busy_time, 
          cpu_ctx_switches, 
          memory_percent, 
          memory_used, 
          memory_available, 
          memory_cached, 
          memory_buffers, 
          swap_percent, 
          swap_sin, 
          swap_sout,
          disk_usage_percent,
          disk_read_mb_s,
          disk_write_mb_s,
          disk_read_time,
          disk_write_time,
          net_rate_mb_s,
          net_bytes_sent,
          net_bytes_recv,
          net_packets_sent,
          net_packets_recv,
          net_errs,
          net_drops,
          load_avg_1,
          load_avg_5,
          load_avg_15,
          total_processes,
          running_processes,
          sleeping_processes,
          zombie_processes,
          avg_temp,
          max_temp,
          battery_percent,
          process_data,
          num_threads))
    conn.commit()
