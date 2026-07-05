"""Shared database schema and read/write interface."""
import sqlite3 # for both layers
import time # for layer 2
from config import DB_PATH 

# layer 1 db code starts here
db_path = DB_PATH


# Creating table for all the metrics collected from the system

def create_connection(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS layer1_sys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,

            cpu_usage_percent REAL,
            cpu_current_freq REAL,
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
            disk_read REAL,
            disk_write REAL,
            disk_read_time INTEGER,
            disk_write_time INTEGER,

            net_bytes_sent INTEGER,
            net_bytes_received INTEGER,
            net_packets_sent INTEGER,
            net_packets_received INTEGER,
            net_errs INTEGER,
            net_drops INTEGER,
            net_rate_mb_s REAL,

            load_avg1 REAL,
            load_avg5 REAL,
            load_avg15 REAL,
            total_processes INTEGER,
            running_processes INTEGER,
            sleeping_processes INTEGER,
            zombie_processes INTEGER,

            avg_temp REAL,
            max_temp REAL,
            battery_percent REAL
        )
    ''')

    conn.commit()
    return conn

# Function to write the collected metrics into the database
# removed hardcoded keys and added a skip_keys set to avoid storing unnecessary data in the database
def write_layer1(conn, data: dict):
    skip_keys = {'process_data'}  # DB mein store nahi karna
    data_to_store = {k: v for k, v in data.items() if k not in skip_keys}
    
    cols         = ", ".join(data_to_store.keys())
    placeholders = ", ".join("?" for _ in data_to_store)
    conn.execute(
        f"INSERT INTO layer1_sys ({cols}) VALUES ({placeholders})",
        list(data_to_store.values())
    )
    conn.commit()

# layer 2 db code starts here 


def init_db():
    """Initializes separate structural tables for CPU and Memory metrics."""
    with sqlite3.connect(DB_PATH) as conn:
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

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        if cpu_rows:
            cursor.executemany(insert_query.format("top_cpu_telemetry"), cpu_rows)
        
        if ram_rows:
            cursor.executemany(insert_query.format("top_ram_telemetry"), ram_rows)
            
        conn.commit()
        
# layer 2 db code ends here       

