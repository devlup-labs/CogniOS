"""Layer 4 diagnostics telemetry collection."""
import threading
import sqlite3
import psutil
from datetime import datetime

_layer4_running = False
_layer4_lock = threading.Lock()

class DiagnosticsCollector:
    def __init__(self, db_path="cognios_telemetry.db"):
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
            trigger_reason TEXT
        )
        """)
        self.conn.commit()

    def collect_and_save(self, pid, trigger_reason="anomaly"):
        try:
            p = psutil.Process(pid)
            timestamp = datetime.now().isoformat()

            try:
                files = p.open_files()
                open_files_count = len(files)
                open_files = ",".join(f.path for f in files[:20]) 
            except (psutil.AccessDenied, Exception):
                open_files_count = None
                open_files = None

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

            try:
                ctx = p.num_ctx_switches()
                vol_ctx = ctx.voluntary
                invol_ctx = ctx.involuntary
            except (psutil.AccessDenied, Exception):
                vol_ctx, invol_ctx = None, None

            try:
                affinity = ",".join(str(c) for c in p.cpu_affinity())
            except (psutil.AccessDenied, AttributeError, Exception):
                affinity = None

            try:
                ioprio = p.ionice().value
            except (psutil.AccessDenied, AttributeError, Exception):
                ioprio = None

            try:
                nice = p.nice()
            except (psutil.AccessDenied, Exception):
                nice = None

            self.cursor.execute("""
                INSERT INTO process_diagnostics (
                    pid, process_name, timestamp,
                    open_files_count, open_files,
                    thread_count, thread_details,
                    voluntary_ctx_switches, involuntary_ctx_switches,
                    cpu_affinity, io_priority, nice_value, trigger_reason
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                pid, p.name(), timestamp,
                open_files_count, open_files,
                thread_count, thread_details,
                vol_ctx, invol_ctx,
                affinity, ioprio, nice, trigger_reason
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

