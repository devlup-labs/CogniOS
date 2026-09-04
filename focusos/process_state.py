"""Process State Registry for tracking original process scheduling parameters and performing rollbacks."""

import time
import psutil

# Global registry: pid -> original state dict
_registry = {}


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

        _registry[pid] = {
            "pid": pid,
            "name": name,
            "create_time": create_time,
            "original_nice": nice,
            "original_affinity": affinity,
            "original_ionice": ionice,
            "policy": policy_name,
            "timestamp": time.time(),
        }
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
            return False

        # Restore nice priority
        try:
            proc.nice(data["original_nice"])
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

        # Restore CPU affinity if it was recorded
        if data["original_affinity"]:
            try:
                proc.cpu_affinity(data["original_affinity"])
            except (psutil.AccessDenied, psutil.NoSuchProcess, ValueError):
                pass

        # Restore I/O priority
        if data["original_ionice"] is not None:
            try:
                io = data["original_ionice"]
                if hasattr(io, "ioclass") and hasattr(io, "value"):
                    proc.ionice(io.ioclass, io.value)
                else:
                    proc.ionice(io)
            except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError, TypeError, ValueError):
                pass

        del _registry[pid]
        return True

    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        del _registry[pid]
        return False


def restore_all() -> int:
    """Restores all tracked processes to their original scheduling parameters."""
    restored_count = 0
    pids = list(_registry.keys())

    for pid in pids:
        if restore_process(pid):
            restored_count += 1

    _registry.clear()
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


if __name__ == "__main__":
    current_proc = psutil.Process()
    saved = save_original(current_proc, "TEST")
    assert saved is True
    assert is_tracked(current_proc.pid) is True
    restored = restore_process(current_proc.pid)
    assert restored is True
    assert is_tracked(current_proc.pid) is False
    print("[✔] process_state registry and rollback tests passed successfully.")
