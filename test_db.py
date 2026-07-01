import sqlite3
from db import create_connection, write_layer1
from collectors.layer1_system import collect_layer1_metrics
from config import DB_PATH
import os

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = create_connection(DB_PATH)
metrics = collect_layer1_metrics()

try:
    write_layer1(
        conn, 
        metrics['timestamp'], 
        metrics['cpu_usage_percent'], 
        metrics['cpu_current_freq'], 
        metrics['cpu_user_time'], 
        metrics['cpu_system_time'], 
        metrics['cpu_idle_time'], 
        metrics['cpu_iowait_time'], 
        metrics['cpu_busy_time'], 
        metrics['cpu_ctx_switches'], 
        metrics['memory_percent'], 
        metrics['memory_used'], 
        metrics['memory_available'], 
        metrics['memory_cached'], 
        metrics['memory_buffers'], 
        metrics['swap_percent'], 
        metrics['swap_sin'], 
        metrics['swap_sout'], 
        metrics['disk_usage_percent'], 
        metrics['disk_read'], 
        metrics['disk_write'], 
        metrics['disk_read_time'], 
        metrics['disk_write_time'], 
        metrics['load_avg1'], 
        metrics['load_avg5'], 
        metrics['load_avg15'], 
        metrics['total_processes'], 
        metrics['running_processes'], 
        metrics['sleeping_processes'], 
        metrics['zombie_processes'], 
        metrics['avg_temp'], 
        metrics['max_temp'], 
        metrics['battery_percent']
    )
    print("Success!")
except Exception as e:
    print("Error:", e)

