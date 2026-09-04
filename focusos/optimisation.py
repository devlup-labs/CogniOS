"""Resource Optimization Engine for applying process scheduling policies based on deterministic workload attribution."""

import os
import sqlite3
import time
import sys
import json
import subprocess
import psutil

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH, RULE_SYSTEM_CPU_CONTENTION
from focusos.rules.process_vocab import is_protected_process
from focusos.process_state import save_original, restore_all, restore_process, is_tracked
import db


def is_protected(proc: psutil.Process) -> bool:
    """Returns True if process should never be modified (root, systemd, kernel threads, etc.)."""
    try:
        if proc.pid < 10:
            return True
        
        name = proc.name()
        if is_protected_process(name):
            return True

        # Protect processes owned by root unless explicitly configured otherwise
        try:
            if proc.username() == "root":
                return True
        except (psutil.AccessDenied, KeyError):
            pass

        return False
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return True


def get_cores():
    """Returns lists of P-cores and E-cores for hybrid architectures, or empty lists if non-hybrid."""
    p_cores = []
    e_cores = []
    
    if os.path.exists("/sys/devices/cpu_core/cpus") and os.path.exists("/sys/devices/cpu_atom/cpus"):
        try:
            with open("/sys/devices/cpu_core/cpus", "r") as f:
                for r in f.read().strip().split(','):
                    if '-' in r:
                        start, end = map(int, r.split('-'))
                        p_cores.extend(range(start, end + 1))
                    else:
                        p_cores.append(int(r))
            with open("/sys/devices/cpu_atom/cpus", "r") as f:
                for r in f.read().strip().split(','):
                    if '-' in r:
                        start, end = map(int, r.split('-'))
                        e_cores.extend(range(start, end + 1))
                    else:
                        e_cores.append(int(r))
            return p_cores, e_cores
        except Exception:
            pass

    base_path = "/sys/devices/system/cpu/"
    frequencies = {}
    
    try:
        if os.path.exists(os.path.join(base_path, "cpu0", "cpufreq")):
            for folder in os.listdir(base_path):
                if folder.startswith("cpu") and folder[3:].isdigit():
                    cpu_id = int(folder[3:])
                    freq_file = os.path.join(base_path, folder, "cpufreq/cpuinfo_max_freq")
                    if os.path.exists(freq_file):
                        with open(freq_file, "r") as f:
                            frequencies[cpu_id] = int(f.read().strip())
                            
            unique_speeds = sorted(list(set(frequencies.values())))
            if len(unique_speeds) > 1:
                p_cores = [cpu for cpu, freq in frequencies.items() if freq == max(unique_speeds)]
                e_cores = [cpu for cpu, freq in frequencies.items() if freq == min(unique_speeds)]
    except Exception:
        pass
                    
    return p_cores, e_cores


def get_active_network_interface() -> str:
    """Detects primary active network interface."""
    try:
        if os.path.exists("/proc/net/route"):
            with open("/proc/net/route") as f:
                for line in f:
                    fields = line.strip().split()
                    if len(fields) >= 4 and fields[1] == '00000000' and int(fields[3], 16) & 2:
                        return fields[0]
    except Exception:
        pass
    
    try:
        stats = psutil.net_if_stats()
        for iface, stat in stats.items():
            if stat.isup and iface != 'lo':
                return iface
    except Exception:
        pass
    return "eth0"


def set_network_fair_queuing(enable: bool) -> bool:
    """Configures tc fq_codel fair queuing for network latency optimization."""
    try:
        interface = get_active_network_interface()
        cmd = f"sudo tc qdisc add dev {interface} root fq_codel" if enable else f"sudo tc qdisc del dev {interface} root"
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def apply_policy(policy_dict: dict, state: dict, conn=None) -> list[dict]:
    """Applies optimization policy based on rule engine evidence and process state registry.
    
    Args:
        policy_dict: Dict containing policy parameters (target_bucket_nice, background_nice, etc.)
        state: Dict containing current workload state and evidence
        conn: Optional SQLite connection for writing optimization_events
    """
    workload = policy_dict.get("workload", "UNKNOWN")
    if workload in ("IDLE", "UNKNOWN"):
        if workload == "IDLE":
            restore_workload_state(conn)
        return []

    target_nice = policy_dict.get("target_bucket_nice", 0)
    bg_nice = policy_dict.get("background_nice", 0)
    
    actions_log = []
    now = time.time()

    # Hardware core assignment
    total_cores = os.cpu_count() or 4
    p_cores, e_cores = get_cores()
    fg_cores = p_cores if p_cores else [c for c in range(total_cores) if c % 2 == 0] or [0]
    bg_cores = e_cores if e_cores else [c for c in range(total_cores) if c % 2 != 0] or [total_cores - 1]

    # Iterate active processes
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        try:
            pid = proc.info['pid']
            p_name = proc.info['name'] or ""

            if is_protected(proc):
                continue

            # Save initial scheduling state before modification
            save_original(proc, workload)

            old_nice = proc.nice()
            new_nice = old_nice

            # Check if this process belongs to the active workload evidence
            is_target = any(
                isinstance(item, dict) and item.get("pid") == pid
                for item in state.get("evidence", [])
            ) or (p_name.lower() in workload.lower())

            if is_target and target_nice != 0:
                new_nice = target_nice
                try:
                    proc.nice(target_nice)
                    if policy_dict.get("affinity_pin") and fg_cores:
                        proc.cpu_affinity(fg_cores)
                    
                    action_record = {
                        "pid": pid,
                        "process_name": p_name,
                        "workload": workload,
                        "action": f"nice -> {target_nice}",
                        "old_value": str(old_nice),
                        "new_value": str(target_nice),
                        "reason": f"Target process for {workload}",
                        "success": True,
                    }
                    actions_log.append(action_record)
                    if conn:
                        db.write_optimization_event(
                            conn, now, pid, p_name, workload,
                            "nice", str(old_nice), str(target_nice),
                            action_record["reason"], 1
                        )
                except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                    actions_log.append({
                        "pid": pid, "process_name": p_name, "workload": workload,
                        "action": "nice_failed", "old_value": str(old_nice), "new_value": str(target_nice),
                        "reason": str(e), "success": False
                    })

            elif not is_target and bg_nice != 0 and old_nice < bg_nice:
                new_nice = bg_nice
                try:
                    proc.nice(bg_nice)
                    if bg_cores:
                        proc.cpu_affinity(bg_cores)
                    
                    action_record = {
                        "pid": pid,
                        "process_name": p_name,
                        "workload": workload,
                        "action": f"depress_nice -> {bg_nice}",
                        "old_value": str(old_nice),
                        "new_value": str(bg_nice),
                        "reason": f"Background process during {workload}",
                        "success": True,
                    }
                    actions_log.append(action_record)
                    if conn:
                        db.write_optimization_event(
                            conn, now, pid, p_name, workload,
                            "nice", str(old_nice), str(bg_nice),
                            action_record["reason"], 1
                        )
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass

        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            continue

    # Toggle fair queuing if video call
    if workload == "VIDEO_CALL":
        set_network_fair_queuing(True)

    return actions_log


def restore_workload_state(conn=None) -> int:
    """Restores all tracked processes to original scheduling state and logs restoration."""
    now = time.time()
    restored_count = restore_all()
    
    if conn and restored_count > 0:
        db.write_optimization_event(
            conn, now, 0, "SYSTEM", "RESTORE_ALL",
            "MODIFIED", "ORIGINAL",
            f"Restored {restored_count} process priorities to initial values", 1
        )
    return restored_count


if __name__ == "__main__":
    current = psutil.Process()
    assert is_protected(current) is False or current.pid < 10 or current.username() == "root"
    print("[✔] optimisation module basic checks passed.")
