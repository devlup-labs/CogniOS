import sqlite3
from config import DB_PATH

db_path = DB_PATH

# Creating table for all the metrics collected from the system

def create_connection(db_path):
    conn = sqlite3.connect(db_path)
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
            battery_percent REAL
        )
    ''')

    conn.commit()
    return conn

# Function to write the collected metrics into the database

def write_layer1(conn, timestamp, cpu_usage_percent, cpu_freq, cpu_user_time, cpu_system_time, cpu_idle_time, cpu_iowait_time, cpu_busy_time, cpu_ctx_switches, memory_percent, memory_used, memory_available, memory_cached, memory_buffers, swap_percent, swap_sin, swap_sout, disk_usage_percent, disk_read_mb_s, disk_write_mb_s, disk_read_time, disk_write_time, load_avg_1, load_avg_5, load_avg_15, total_processes, running_processes, sleeping_processes, zombie_processes, avg_temp, max_temp, battery_percent):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO layer1_sys (timestamp, cpu_usage_percent, cpu_freq, cpu_user_time, cpu_system_time, cpu_idle_time, cpu_iowait_time, cpu_busy_time, cpu_ctx_switches, memory_percent, memory_used, memory_available, memory_cached, memory_buffers, swap_percent, swap_sin, swap_sout, disk_usage_percent, disk_read_mb_s, disk_write_mb_s, disk_read_time, disk_write_time, load_avg_1, load_avg_5, load_avg_15, total_processes, running_processes, sleeping_processes, zombie_processes, avg_temp, max_temp, battery_percent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
          load_avg_1,
          load_avg_5,
          load_avg_15,
          total_processes,
          running_processes,
          sleeping_processes,
          zombie_processes,
          avg_temp,
          max_temp,
          battery_percent))
