"""Shared database schema and read/write interface."""
import json
import sqlite3
import time
from config import DB_PATH

# layer 2 db code starts here

def init_layer2_db():
    """Initializes the unified layer2_proc table for Layer 2 telemetry."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS layer2_proc (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp           REAL    NOT NULL,
                top_cpu_json        TEXT    NOT NULL,
                top_ram_json        TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshot_ts
            ON layer2_proc (timestamp)
        """)
        conn.commit()


def write_layer2(top_cpu, top_ram):
    """Writes one unified row per 5-second poll — timestamp + two compact JSON arrays."""
    row = (
        time.time(),
        json.dumps(top_cpu, separators=(',', ':')),
        json.dumps(top_ram, separators=(',', ':'))
    )
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO layer2_proc (timestamp, top_cpu_json, top_ram_json) VALUES (?, ?, ?)",
            row
        )
        conn.commit()

# layer 2 db code ends here

# layer 1 db code starts here

db_path = DB_PATH

def create_connection(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS layer1_sys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,

            cpu_usage_percent REAL,
            cpu_freq REAL,
            cpu_user_time REAL,
            cpu_system_time REAL,
            cpu_idle_time REAL,
            cpu_iowait_time REAL,
            cpu_busy_time REAL,
            cpu_ctx_switches REAL,

            memory_percent REAL,
            memory_used INTEGER,
            memory_available INTEGER,
            memory_cached INTEGER,
            memory_buffers INTEGER,
            swap_percent REAL,
            swap_sin INTEGER,
            swap_sout INTEGER,

            disk_usage_percent REAL,
            disk_read_mb_s REAL,
            disk_write_mb_s REAL,
            disk_read_time INTEGER,
            disk_write_time INTEGER,

            net_rate_mb_s REAL,
            net_bytes_sent INTEGER,
            net_bytes_recv INTEGER,
            net_packets_sent INTEGER,
            net_packets_recv INTEGER,
            net_errs INTEGER,
            net_drops INTEGER,

            load_avg_1 REAL,
            load_avg_5 REAL,
            load_avg_15 REAL,
            total_processes INTEGER,
            running_processes INTEGER,
            sleeping_processes INTEGER,
            zombie_processes INTEGER,

            avg_temp REAL,
            max_temp REAL,
            battery_percent REAL,
            process_data TEXT
        )
    ''')

    conn.commit()
    return conn

def write_layer1(conn, timestamp, cpu_usage_percent, cpu_freq, cpu_user_time, cpu_system_time, cpu_idle_time, cpu_iowait_time, cpu_busy_time, cpu_ctx_switches, memory_percent, memory_used, memory_available, memory_cached, memory_buffers, swap_percent, swap_sin, swap_sout, disk_usage_percent, disk_read_mb_s, disk_write_mb_s, disk_read_time, disk_write_time, load_avg_1, load_avg_5, load_avg_15, total_processes, running_processes, sleeping_processes, zombie_processes, avg_temp, max_temp, battery_percent, net_rate_mb_s, net_bytes_sent, net_bytes_recv, net_packets_sent, net_packets_recv, net_errs, net_drops, process_data):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO layer1_sys (timestamp, cpu_usage_percent, cpu_freq, cpu_user_time, cpu_system_time, cpu_idle_time, cpu_iowait_time, cpu_busy_time, cpu_ctx_switches, memory_percent, memory_used, memory_available, memory_cached, memory_buffers, swap_percent, swap_sin, swap_sout, disk_usage_percent, disk_read_mb_s, disk_write_mb_s, disk_read_time, disk_write_time, net_rate_mb_s, net_bytes_sent, net_bytes_recv, net_packets_sent, net_packets_recv, net_errs, net_drops, load_avg_1, load_avg_5, load_avg_15, total_processes, running_processes, sleeping_processes, zombie_processes, avg_temp, max_temp, battery_percent, process_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, cpu_usage_percent, cpu_freq, cpu_user_time, cpu_system_time, cpu_idle_time, cpu_iowait_time, cpu_busy_time, cpu_ctx_switches, memory_percent, memory_used, memory_available, memory_cached, memory_buffers, swap_percent, swap_sin, swap_sout, disk_usage_percent, disk_read_mb_s, disk_write_mb_s, disk_read_time, disk_write_time, net_rate_mb_s, net_bytes_sent, net_bytes_recv, net_packets_sent, net_packets_recv, net_errs, net_drops, load_avg_1, load_avg_5, load_avg_15, total_processes, running_processes, sleeping_processes, zombie_processes, avg_temp, max_temp, battery_percent, process_data))
    conn.commit()