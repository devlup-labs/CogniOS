"""Shared database schema and read/write interface."""
import json
import sqlite3
import time
from config import DB_PATH


def _harden_connection(conn):
    """Best-effort per-connection pragmas. journal_mode is a one-time, whole-file
    switch — see ensure_wal_mode() for the race-free way to enable it up front."""
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def ensure_wal_mode(db_path=DB_PATH):
    """Switch the DB file to WAL mode once, via a single connection, before any
    concurrent writers open their own connections. Doing this per-connection from
    multiple threads/processes at once races on the initial (non-WAL -> WAL) file
    header rewrite and can raise 'database is locked' even with busy_timeout set."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.close()

# layer 2 db code starts here

def create_layer2_connection(db_path=DB_PATH):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    _harden_connection(conn)
    return conn


def init_layer2_db(conn):
    """Initializes the unified layer2_proc table for Layer 2 telemetry."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS layer2_proc (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp           REAL    NOT NULL,

            cpu_1_pid           INTEGER,
            cpu_1_ppid          INTEGER,
            cpu_1_name          TEXT NOT NULL,
            cpu_1_status        TEXT NOT NULL,
            cpu_1_cpu_peak      REAL,

            cpu_2_pid           INTEGER,
            cpu_2_ppid          INTEGER,
            cpu_2_name          TEXT NOT NULL,
            cpu_2_status        TEXT NOT NULL,
            cpu_2_cpu_peak      REAL,

            cpu_3_pid           INTEGER,
            cpu_3_ppid          INTEGER,
            cpu_3_name          TEXT NOT NULL,
            cpu_3_status        TEXT NOT NULL,
            cpu_3_cpu_peak      REAL,

            cpu_4_pid           INTEGER,
            cpu_4_ppid          INTEGER,
            cpu_4_name          TEXT NOT NULL,
            cpu_4_status        TEXT NOT NULL,
            cpu_4_cpu_peak      REAL,

            cpu_5_pid           INTEGER,
            cpu_5_ppid          INTEGER,
            cpu_5_name          TEXT NOT NULL,
            cpu_5_status        TEXT NOT NULL,
            cpu_5_cpu_peak      REAL,

            ram_1_pid           INTEGER,
            ram_1_ppid          INTEGER,
            ram_1_name          TEXT NOT NULL,
            ram_1_status        TEXT_NOT_NULL,
            ram_1_peak          REAL,
            ram_1_open_fds      REAL,

            ram_2_pid           INTEGER,
            ram_2_ppid          INTEGER,
            ram_2_name          TEXT NOT NULL,
            ram_2_status        TEXT_NOT_NULL,
            ram_2_peak          REAL,
            ram_2_open_fds      REAL,

            ram_3_pid           INTEGER,
            ram_3_ppid          INTEGER,
            ram_3_name          TEXT NOT NULL,
            ram_3_status        TEXT_NOT_NULL,
            ram_3_peak          REAL,
            ram_3_open_fds      REAL,

            ram_4_pid           INTEGER,
            ram_4_ppid          INTEGER,
            ram_4_name          TEXT NOT NULL,
            ram_4_status        TEXT_NOT_NULL,
            ram_4_peak          REAL,
            ram_4_open_fds      REAL,

            ram_5_pid           INTEGER,
            ram_5_ppid          INTEGER,
            ram_5_name          TEXT NOT NULL,
            ram_5_status        TEXT_NOT_NULL,
            ram_5_peak          REAL,
            ram_5_open_fds      REAL
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_layer2
        ON layer2_proc (timestamp)
    """)
    conn.commit()


def write_layer2(conn, top_cpu, top_ram):
    """Writes one unified row per 5-second poll — timestamp + two compact JSON arrays."""

    conn.execute('''
        INSERT INTO layer2_proc (
        timestamp,
        cpu_1_pid, cpu_1_ppid, cpu_1_name, cpu_1_status, cpu_1_cpu_peak, 
        cpu_2_pid, cpu_2_ppid, cpu_2_name, cpu_2_status, cpu_2_cpu_peak,
        cpu_3_pid, cpu_3_ppid, cpu_3_name, cpu_3_status, cpu_3_cpu_peak,
        cpu_4_pid, cpu_4_ppid, cpu_4_name, cpu_4_status, cpu_4_cpu_peak,
        cpu_5_pid, cpu_5_ppid, cpu_5_name, cpu_5_status, cpu_5_cpu_peak,    
        ram_1_pid, ram_1_ppid, ram_1_name, ram_1_status, ram_1_peak, ram_1_open_fds,
        ram_2_pid, ram_2_ppid, ram_2_name, ram_2_status, ram_2_peak, ram_2_open_fds,
        ram_3_pid, ram_3_ppid, ram_3_name, ram_3_status, ram_3_peak, ram_3_open_fds,
        ram_4_pid, ram_4_ppid, ram_4_name, ram_4_status, ram_4_peak, ram_4_open_fds,
        ram_5_pid, ram_5_ppid, ram_5_name, ram_5_status, ram_5_peak, ram_5_open_fds
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (time.time(), 
          top_cpu[0]['pid'], top_cpu[0]['ppid'], top_cpu[0]['name'], top_cpu[0]['status'], top_cpu[0]['cpu_peak'],
          top_cpu[1]['pid'], top_cpu[1]['ppid'], top_cpu[1]['name'], top_cpu[1]['status'], top_cpu[1]['cpu_peak'],
          top_cpu[2]['pid'], top_cpu[2]['ppid'], top_cpu[2]['name'], top_cpu[2]['status'], top_cpu[2]['cpu_peak'],
          top_cpu[3]['pid'], top_cpu[3]['ppid'], top_cpu[3]['name'], top_cpu[3]['status'], top_cpu[3]['cpu_peak'],
          top_cpu[4]['pid'], top_cpu[4]['ppid'], top_cpu[4]['name'], top_cpu[4]['status'], top_cpu[4]['cpu_peak'],
          top_ram[0]['pid'], top_ram[0]['ppid'], top_ram[0]['name'], top_ram[0]['status'], top_ram[0]['ram_peak'], top_ram[0]['open_fds'],
          top_ram[1]['pid'], top_ram[1]['ppid'], top_ram[1]['name'], top_ram[1]['status'], top_ram[1]['ram_peak'], top_ram[1]['open_fds'],
          top_ram[2]['pid'], top_ram[2]['ppid'], top_ram[2]['name'], top_ram[2]['status'], top_ram[2]['ram_peak'], top_ram[2]['open_fds'],
          top_ram[3]['pid'], top_ram[3]['ppid'], top_ram[3]['name'], top_ram[3]['status'], top_ram[3]['ram_peak'], top_ram[3]['open_fds'],
          top_ram[4]['pid'], top_ram[4]['ppid'], top_ram[4]['name'], top_ram[4]['status'], top_ram[4]['ram_peak'], top_ram[4]['open_fds']
          )
    )
    conn.commit()

# layer 2 db code ends here

# layer 1 db code starts here

db_path = DB_PATH

def create_connection(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    _harden_connection(conn)
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