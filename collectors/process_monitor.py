"""
FocusOS Process Telemetry Collection Module
Provides genuine, continuous per-process resource telemetry directly from Linux kernel
(/proc and psutil), calculating real deltas across sampling intervals, validating PID
lifecycle to prevent reuse corruption, and reporting complete process governance metrics.
"""

import os
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


def _format_bytes_human(num_bytes: int) -> str:
    """Formats bytes into human readable string (B, KB, MB, GB)."""
    val = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(val) < 1024.0 or unit == "TB":
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{num_bytes} B"


class ProcessTracker:
    def __init__(self, pid: int, proc, create_time: float, initial_cputime: float, sample_time: float):
        self.pid = pid
        self.proc = proc
        self.create_time = create_time
        self.last_cputime = initial_cputime
        self.last_time = sample_time
        self.last_cpu_percent = 0.0


class ProcessMonitor:
    """
    Thread-safe continuous process telemetry engine.
    Ensures accurate multicore process CPU reporting, memory RSS attribution,
    and kernel scheduling governance metadata.
    """

    def __init__(self, total_cores: Optional[int] = None):
        import multiprocessing
        self._lock = threading.Lock()
        self.total_cores = total_cores or multiprocessing.cpu_count() or 1
        self._tracked: Dict[Tuple[int, float], ProcessTracker] = {}
        self._last_sample_time: float = 0.0
        self._total_system_ram: int = 1

        try:
            import psutil
            self._total_system_ram = psutil.virtual_memory().total or 1
        except Exception:
            pass

    def sample(self, top_n: int = 25, min_interval_sec: float = 0.1) -> List[dict]:
        """
        Samples all active running processes, computing real CPU% deltas and
        collecting RSS memory, nice values, CPU affinity masks, and thread counts.
        """
        import psutil

        with self._lock:
            now = time.time()
            iso_now = datetime.now(timezone.utc).isoformat()
            dt_since_last = now - self._last_sample_time

            # If this is the very first sampling pass or the cache is cold (>10s gap),
            # prime the process trackers first
            if not self._tracked or dt_since_last > 10.0:
                self._prime_trackers(psutil)
                time.sleep(min_interval_sec)
                now = time.time()
                iso_now = datetime.now(timezone.utc).isoformat()

            self._last_sample_time = now
            current_pids_alive = set()
            results: List[dict] = []

            for (pid, ct), tracker in list(self._tracked.items()):
                try:
                    proc = tracker.proc
                    if not proc.is_running():
                        del self._tracked[(pid, ct)]
                        continue

                    # Verify create_time hasn't changed (PID reuse protection)
                    if proc.create_time() != ct:
                        del self._tracked[(pid, ct)]
                        continue

                    current_pids_alive.add((pid, ct))

                    # Sample CPU times
                    times = proc.cpu_times()
                    cur_cputime = times.user + times.system
                    dt = now - tracker.last_time

                    if dt > 0:
                        delta_cputime = cur_cputime - tracker.last_cputime
                        # Standard top-style CPU percent (100% = 1 full core)
                        cpu_pct = round(max(0.0, (delta_cputime / dt) * 100.0), 1)
                        # Core-normalized CPU percent (bounded by 100% total host capacity)
                        cpu_normalized = round(cpu_pct / max(1, self.total_cores), 2)
                    else:
                        cpu_pct = tracker.last_cpu_percent
                        cpu_normalized = round(cpu_pct / max(1, self.total_cores), 2)

                    tracker.last_cputime = cur_cputime
                    tracker.last_time = now
                    tracker.last_cpu_percent = cpu_pct

                    # Memory metrics
                    mem_info = proc.memory_info()
                    rss_bytes = mem_info.rss
                    rss_mb = round(rss_bytes / (1024.0 * 1024.0), 2)
                    mem_pct = round((rss_bytes / self._total_system_ram) * 100.0, 2)

                    # Process metadata & scheduling state
                    name = proc.name()
                    status = proc.status()
                    try:
                        nice = proc.nice()
                    except (psutil.AccessDenied, AttributeError):
                        nice = 0

                    try:
                        affinity = proc.cpu_affinity()
                    except (psutil.AccessDenied, AttributeError):
                        affinity = list(range(self.total_cores))

                    try:
                        num_threads = proc.num_threads()
                    except (psutil.AccessDenied, AttributeError):
                        num_threads = 1

                    results.append({
                        "pid": pid,
                        "name": name,
                        "cpu": cpu_normalized,
                        "cpu_percent": cpu_normalized,
                        "cpu_raw": cpu_pct,
                        "cpu_normalized": cpu_normalized,
                        "ram": mem_pct,
                        "memory_percent": mem_pct,
                        "rss_bytes": rss_bytes,
                        "rss_mb": rss_mb,
                        "memory_rss_mb": rss_mb,
                        "rss_human": _format_bytes_human(rss_bytes),
                        "status": status,
                        "nice": nice,
                        "affinity": affinity,
                        "num_threads": num_threads,
                        "create_time": ct,
                        "timestamp": iso_now,
                        "is_valid": True,
                    })

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    self._tracked.pop((pid, ct), None)
                    continue

            # Check for newly spawned processes that were not in _tracked
            try:
                for proc in psutil.process_iter(["pid", "create_time"]):
                    try:
                        pid = proc.pid
                        ct = proc.info.get("create_time") or proc.create_time()
                        if (pid, ct) not in self._tracked:
                            times = proc.cpu_times()
                            self._tracked[(pid, ct)] = ProcessTracker(
                                pid=pid,
                                proc=proc,
                                create_time=ct,
                                initial_cputime=times.user + times.system,
                                sample_time=now
                            )
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            except Exception:
                pass

            # Sort descending primarily by CPU usage, secondarily by RSS memory
            results.sort(key=lambda x: (x["cpu"], x["ram"]), reverse=True)
            return results[:top_n] if top_n else results

    def _prime_trackers(self, psutil):
        """Discovers current running processes and establishes initial CPU time baselines."""
        self._tracked.clear()
        now = time.time()
        for proc in psutil.process_iter(["pid", "create_time"]):
            try:
                pid = proc.pid
                ct = proc.info.get("create_time") or proc.create_time()
                times = proc.cpu_times()
                self._tracked[(pid, ct)] = ProcessTracker(
                    pid=pid,
                    proc=proc,
                    create_time=ct,
                    initial_cputime=times.user + times.system,
                    sample_time=now
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue


# Module singleton
_GLOBAL_PROCESS_MONITOR = ProcessMonitor()


def get_process_monitor() -> ProcessMonitor:
    """Returns the singleton ProcessMonitor instance."""
    return _GLOBAL_PROCESS_MONITOR


def sample_top_processes(top_n: int = 15) -> List[dict]:
    """Convenience helper to sample the top active system processes."""
    return _GLOBAL_PROCESS_MONITOR.sample(top_n=top_n)
