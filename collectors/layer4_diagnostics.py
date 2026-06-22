"""Layer 4 diagnostics telemetry collection."""
from datetime import datetime
from pathlib import Path
import socket
import sqlite3
import threading

import psutil

_layer4_running = False
_layer4_lock = threading.Lock()
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "cognios.db"

class DiagnosticsCollector:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS process_diagnostics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pid INTEGER,
            process_name TEXT,
            timestamp TEXT,
            open_files_count INTEGER,
            open_files TEXT,
            thread_count INTEGER,
            thread_details TEXT,
            voluntary_ctx_switches INTEGER,
            involuntary_ctx_switches INTEGER,
            cpu_affinity TEXT,
            io_priority INTEGER,
            nice_value INTEGER,
            trigger_reason TEXT,
            net_connections_count INTEGER,
            net_connections TEXT,       
            io_write_bytes INTEGER,
            io_read_bytes INTEGER                     
        )
        """)
        self._ensure_columns(
            {
                "io_write_bytes": "INTEGER",
                "io_read_bytes": "INTEGER",
            }
        )
        self.conn.commit()

    def _ensure_columns(self, columns):
        existing_columns = {
            row[1]
            for row in self.cursor.execute("PRAGMA table_info(process_diagnostics)")
        }

        for column_name, column_type in columns.items():
            if column_name not in existing_columns:
                self.cursor.execute(
                    f"ALTER TABLE process_diagnostics ADD COLUMN {column_name} {column_type}"
                )

    def collect_and_save(self, pid, trigger_reason="anomaly"):
        try:
            p = psutil.Process(pid)
            timestamp = datetime.now().isoformat()

            #open files

            try:
                files = p.open_files()
                open_files_count = len(files)
                open_files = ",".join(f.path for f in files[:20]) 
            except (psutil.AccessDenied, Exception):
                open_files_count = None
                open_files = None

            #threads
            try:
                threads = p.threads()
                thread_count = len(threads)
                thread_details = ",".join(
                    f"{t.id}(u={round(t.user_time,2)},s={round(t.system_time,2)})"
                    for t in threads
                )
            except (psutil.AccessDenied, Exception):
                thread_count = None
                thread_details = None

            #ctx switches

            try:
                ctx = p.num_ctx_switches()
                vol_ctx = ctx.voluntary
                invol_ctx = ctx.involuntary
            except (psutil.AccessDenied, Exception):
                vol_ctx, invol_ctx = None, None

            #Cpu affinity
            try:
                affinity = ",".join(str(c) for c in p.cpu_affinity())
            except (psutil.AccessDenied, AttributeError, Exception):
                affinity = None

            #I/O Priority
            try:
                ioprio = p.ionice().value
            except (psutil.AccessDenied, AttributeError, Exception):
                ioprio = None

            # Nice value
            try:
                nice = p.nice()
            except (psutil.AccessDenied, Exception):
                nice = None

            # Network Connections
            try:
                conns = p.net_connections(kind="all")
                net_connections_count = len(conns)
                
                conn_parts = []
                for c in conns[:30]:
                    if c.type == socket.SOCK_STREAM:
                        proto = "tcp"
                    elif c.type == socket.SOCK_DGRAM:
                        proto = "udp"
                    else:
                        proto = "other"
                    
                    local = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "-"
                    remote = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "-"
                    status = c.status if c.status else "-"

                    conn_parts.append(f"{proto}|{local}|{remote}|{status}")
            
                net_connections = ",".join(conn_parts)
            
            except (psutil.AccessDenied, AttributeError,Exception):
                net_connections_count = None
                net_connections = None
            
            # Per-process disk I/O bytes.
            try:
                io = p.io_counters()
                io_write_bytes = io.write_bytes
                io_read_bytes = io.read_bytes
            except (psutil.AccessDenied, AttributeError, Exception):
                io_write_bytes = None
                io_read_bytes = None


            self.cursor.execute("""
                INSERT INTO process_diagnostics (
                    pid, process_name, timestamp,
                    open_files_count, open_files,
                    thread_count, thread_details,
                    voluntary_ctx_switches, involuntary_ctx_switches,
                    cpu_affinity, io_priority, nice_value, trigger_reason,
                    net_connections_count, net_connections,
                    io_write_bytes, io_read_bytes

                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                pid, p.name(), timestamp,
                open_files_count, open_files,
                thread_count, thread_details,
                vol_ctx, invol_ctx,
                affinity, ioprio, nice, trigger_reason,
                net_connections_count, net_connections,
                io_write_bytes, io_read_bytes
            ))
            self.conn.commit()

        except (psutil.NoSuchProcess, psutil.ZombieProcess) as e:
            print(f"[LAYER4 ERROR] {e}")

    def close(self):
        self.conn.close()



def _run_diagnostics(pid_list, trigger_reason):
    global _layer4_running
    collector = DiagnosticsCollector()
    try:
        for pid in pid_list:
            collector.collect_and_save(pid, trigger_reason)
    finally:
        collector.close()
        with _layer4_lock:
            _layer4_running = False


def trigger_layer4(pid_list, trigger_reason="anomaly"):
    global _layer4_running
    with _layer4_lock:
        if _layer4_running:
            print("LAYER4 Already running, skipping trigger.")
            return
        _layer4_running = True

    t = threading.Thread(
        target=_run_diagnostics,
        args=(pid_list, trigger_reason),
        daemon=True
    )
    t.start()
