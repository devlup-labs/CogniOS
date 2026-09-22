"""Process State Registry for tracking original process scheduling parameters and performing rollbacks."""

import json
import sqlite3
import time
import psutil

try:
    from config import DB_PATH
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import DB_PATH

# Global in-memory cache: pid -> original state dict
_registry = {}


def _init_db(db_path=DB_PATH):
    """Initializes the process_state_registry table for crash-resilient rollback tracking."""
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS process_state_registry (
                pid INTEGER PRIMARY KEY,
                name TEXT,
                create_time REAL,
                original_nice INTEGER,
                original_affinity TEXT,
                original_ionice TEXT,
                policy TEXT,
                timestamp REAL
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


def _db_save(pid: int, data: dict, db_path=DB_PATH):
    try:
        _init_db(db_path)
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.execute("""
            INSERT OR REPLACE INTO process_state_registry
            (pid, name, create_time, original_nice, original_affinity, original_ionice, policy, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid,
            data.get("name", ""),
            data.get("create_time", 0.0),
            data.get("original_nice", 0),
            json.dumps(data.get("original_affinity") or []),
            str(data.get("original_ionice") or ""),
            data.get("policy", "DEFAULT"),
            data.get("timestamp", time.time()),
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _db_delete(pid: int, db_path=DB_PATH):
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.execute("DELETE FROM process_state_registry WHERE pid = ?", (pid,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _db_clear(db_path=DB_PATH):
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.execute("DELETE FROM process_state_registry")
        conn.commit()
        conn.close()
    except Exception:
        pass


def _db_load(db_path=DB_PATH):
    """Loads surviving tracked processes from SQLite into in-memory registry."""
    global _registry
    try:
        _init_db(db_path)
        conn = sqlite3.connect(db_path, timeout=5.0)
        rows = conn.execute("SELECT pid, name, create_time, original_nice, original_affinity, original_ionice, policy, timestamp FROM process_state_registry").fetchall()
        conn.close()
        for r in rows:
            pid = r[0]
            if pid not in _registry:
                try:
                    aff = json.loads(r[4]) if r[4] else []
                except Exception:
                    aff = []
                _registry[pid] = {
                    "pid": pid,
                    "name": r[1],
                    "create_time": r[2],
                    "original_nice": r[3],
                    "original_affinity": aff,
                    "original_ionice": r[5],
                    "policy": r[6],
                    "timestamp": r[7],
                }
    except Exception:
        pass


# Populate on startup
_db_load()


def save_original(proc_or_pid: int | psutil.Process, policy_name: str = "DEFAULT") -> bool:
    """Saves original process scheduling parameters before optimization.
    
    Prevents duplicate overwrites (preserves initial state before ANY optimization).
    Uses create_time to protect against PID reuse.
    """
    try:
        proc = proc_or_pid if isinstance(proc_or_pid, psutil.Process) else psutil.Process(proc_or_pid)
        pid = proc.pid

        # If already tracked, preserve original initial parameters
        if pid in _registry:
            return True

        create_time = proc.create_time()
        name = proc.name()

        # Capture original parameters safely
        nice = proc.nice()
        try:
            affinity = proc.cpu_affinity()
        except (psutil.AccessDenied, AttributeError):
            affinity = []

        try:
            ionice = proc.ionice()
        except (psutil.AccessDenied, AttributeError):
            ionice = None

        state_entry = {
            "pid": pid,
            "name": name,
            "create_time": create_time,
            "original_nice": nice,
            "original_affinity": affinity,
            "original_ionice": ionice,
            "policy": policy_name,
            "timestamp": time.time(),
        }
        _registry[pid] = state_entry
        _db_save(pid, state_entry)
        return True

    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def restore_process(pid: int) -> bool:
    """Restores saved scheduling parameters to a specific process."""
    if pid not in _registry:
        return False

    data = _registry[pid]
    try:
        proc = psutil.Process(pid)

        # Anti-PID reuse check: verify create_time matches
        if abs(proc.create_time() - data["create_time"]) > 1.0:
            del _registry[pid]
            _db_delete(pid)
            return False

        nice_restored = True
        # Restore nice priority
        try:
            if proc.nice() != data["original_nice"]:
                proc.nice(data["original_nice"])
        except psutil.AccessDenied:
            nice_restored = False
        except psutil.NoSuchProcess:
            del _registry[pid]
            _db_delete(pid)
            return False

        # Restore CPU affinity if it was recorded
        if data.get("original_affinity"):
            try:
                proc.cpu_affinity(data["original_affinity"])
            except (psutil.AccessDenied, psutil.NoSuchProcess, ValueError):
                pass

        # Restore I/O priority
        if data.get("original_ionice") is not None:
            try:
                io = data["original_ionice"]
                if hasattr(io, "ioclass") and hasattr(io, "value"):
                    proc.ionice(io.ioclass, io.value)
                elif hasattr(proc, "ionice"):
                    proc.ionice(io)
            except Exception:
                pass

        if nice_restored:
            del _registry[pid]
            _db_delete(pid)
            return True

        # If nice restoration was blocked by Linux privilege constraints, keep tracked
        return False

    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        del _registry[pid]
        _db_delete(pid)
        return False


def restore_all() -> int:
    """Restores all tracked processes to their original scheduling parameters."""
    restored_count = 0
    pids = list(_registry.keys())

    for pid in pids:
        if restore_process(pid):
            restored_count += 1

    return restored_count


def is_tracked(pid: int) -> bool:
    """Returns True if the PID is currently tracked in the state registry."""
    return pid in _registry


def get_tracked_pids() -> list[int]:
    """Returns a list of all currently tracked PIDs."""
    return list(_registry.keys())


def clear_registry():
    """Wipes the state registry (primarily for testing)."""
    _registry.clear()
    _db_clear()


if __name__ == "__main__":
    current_proc = psutil.Process()
    saved = save_original(current_proc, "TEST")
    assert saved is True
    assert is_tracked(current_proc.pid) is True
    restored = restore_process(current_proc.pid)
    assert restored is True
    assert is_tracked(current_proc.pid) is False
    print("[✔] process_state registry and rollback tests passed successfully.")
