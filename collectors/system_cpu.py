"""
FocusOS System CPU Monitoring Module
Provides high-precision, Linux-native host and per-core CPU telemetry directly
from /proc/stat, computing true deltas between successive counter readings.
"""

import os
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, NamedTuple


class CpuReading(NamedTuple):
    timestamp: float
    total: float
    idle: float
    busy: float
    user: float
    system: float
    iowait: float
    cores_total: List[float]
    cores_busy: List[float]


class SystemCpuMonitor:
    """
    Thread-safe Linux /proc/stat CPU telemetry collector.
    Computes exact utilization deltas over defined intervals.
    Never treats cumulative time as a percentage.
    """

    def __init__(self, stale_threshold_sec: float = 4.0):
        self._lock = threading.Lock()
        self._last_reading: Optional[CpuReading] = None
        self._stale_threshold = stale_threshold_sec
        self._last_result: Optional[dict] = None

    def _read_proc_stat(self) -> Optional[Tuple[List[float], List[List[float]]]]:
        """
        Reads /proc/stat and returns (host_counters, list_of_core_counters).
        Returns None if /proc/stat cannot be read.
        """
        if not os.path.exists("/proc/stat"):
            return None

        try:
            with open("/proc/stat", "r") as f:
                lines = f.readlines()

            host_counters: Optional[List[float]] = None
            core_counters: List[List[float]] = []

            for line in lines:
                parts = line.split()
                if not parts:
                    continue
                name = parts[0]
                if name == "cpu":
                    # cpu  user nice system idle iowait irq softirq steal guest guest_nice
                    host_counters = [float(x) for x in parts[1:11]]
                elif name.startswith("cpu") and name[3:].isdigit():
                    core_counters.append([float(x) for x in parts[1:11]])

            if host_counters is not None:
                return host_counters, core_counters
        except Exception:
            return None
        return None

    def _make_reading(self) -> Optional[CpuReading]:
        """Captures a snapshot of current CPU counters."""
        parsed = self._read_proc_stat()
        now = time.time()

        if parsed:
            host_raw, cores_raw = parsed
            # user(0), nice(1), system(2), idle(3), iowait(4), irq(5), softirq(6), steal(7)
            user = host_raw[0] + (host_raw[1] if len(host_raw) > 1 else 0.0)
            system = host_raw[2] + (host_raw[5] if len(host_raw) > 5 else 0.0) + (host_raw[6] if len(host_raw) > 6 else 0.0)
            idle = host_raw[3] if len(host_raw) > 3 else 0.0
            iowait = host_raw[4] if len(host_raw) > 4 else 0.0
            busy = user + system + (host_raw[7] if len(host_raw) > 7 else 0.0)
            total = idle + iowait + busy

            cores_total = []
            cores_busy = []
            for c in cores_raw:
                c_user = c[0] + (c[1] if len(c) > 1 else 0.0)
                c_sys = c[2] + (c[5] if len(c) > 5 else 0.0) + (c[6] if len(c) > 6 else 0.0)
                c_idle = (c[3] if len(c) > 3 else 0.0) + (c[4] if len(c) > 4 else 0.0)
                c_busy = c_user + c_sys + (c[7] if len(c) > 7 else 0.0)
                cores_total.append(c_idle + c_busy)
                cores_busy.append(c_busy)

            return CpuReading(
                timestamp=now,
                total=total,
                idle=idle + iowait,
                busy=busy,
                user=user,
                system=system,
                iowait=iowait,
                cores_total=cores_total,
                cores_busy=cores_busy
            )
        else:
            # Fallback to psutil if /proc/stat is unavailable
            try:
                import psutil
                times = psutil.cpu_times()
                user = times.user + getattr(times, "nice", 0.0)
                system = times.system + getattr(times, "irq", 0.0) + getattr(times, "softirq", 0.0)
                idle = times.idle
                iowait = getattr(times, "iowait", 0.0)
                busy = user + system + getattr(times, "steal", 0.0)
                total = idle + iowait + busy

                cores_total = []
                cores_busy = []
                for ct in psutil.cpu_times(percpu=True):
                    cu = ct.user + getattr(ct, "nice", 0.0)
                    cs = ct.system + getattr(ct, "irq", 0.0) + getattr(ct, "softirq", 0.0)
                    ci = ct.idle + getattr(ct, "iowait", 0.0)
                    cb = cu + cs + getattr(ct, "steal", 0.0)
                    cores_total.append(ci + cb)
                    cores_busy.append(cb)

                return CpuReading(
                    timestamp=now,
                    total=total,
                    idle=idle + iowait,
                    busy=busy,
                    user=user,
                    system=system,
                    iowait=iowait,
                    cores_total=cores_total,
                    cores_busy=cores_busy
                )
            except Exception:
                return None

    def sample(self, min_interval_sec: float = 0.05) -> dict:
        """
        Calculates live CPU metrics based on delta from previous sample.
        If no previous sample exists or sample is stale (> 4s old),
        performs a small prime sleep (min_interval_sec) to return an accurate
        first reading immediately.
        """
        with self._lock:
            now = time.time()
            iso_now = datetime.now(timezone.utc).isoformat()

            # Check if we need to prime
            needs_prime = (
                self._last_reading is None
                or (now - self._last_reading.timestamp) > self._stale_threshold
            )

            if needs_prime:
                r0 = self._make_reading()
                if r0 is None:
                    return self._fallback_result(iso_now, is_valid=False)
                # Sleep a short burst to establish initial delta
                time.sleep(min_interval_sec)
                r1 = self._make_reading()
                if r1 is None:
                    return self._fallback_result(iso_now, is_valid=False)
            else:
                r0 = self._last_reading
                r1 = self._make_reading()
                if r1 is None:
                    return self._fallback_result(iso_now, is_valid=False)

            self._last_reading = r1

            # Calculate total delta
            delta_total = r1.total - r0.total
            delta_busy = r1.busy - r0.busy
            delta_user = r1.user - r0.user
            delta_system = r1.system - r0.system
            delta_iowait = r1.iowait - r0.iowait
            dt = r1.timestamp - r0.timestamp

            # Safety check: counter reset / zero delta
            if delta_total <= 0 or dt <= 0:
                # Counter reset or zero elapsed ticks
                if self._last_result:
                    res = dict(self._last_result)
                    res["timestamp"] = iso_now
                    res["is_valid"] = False
                    res["is_stale"] = True
                    return res
                return self._fallback_result(iso_now, is_valid=False)

            cpu_pct = round(max(0.0, min(100.0, (delta_busy / delta_total) * 100.0)), 2)
            user_pct = round(max(0.0, min(100.0, (delta_user / delta_total) * 100.0)), 2)
            sys_pct = round(max(0.0, min(100.0, (delta_system / delta_total) * 100.0)), 2)
            iowait_pct = round(max(0.0, min(100.0, (delta_iowait / delta_total) * 100.0)), 2)
            idle_pct = round(max(0.0, min(100.0, 100.0 - cpu_pct)), 2)

            # Per-core utilization
            per_core: List[float] = []
            num_cores = min(len(r0.cores_total), len(r1.cores_total))
            for i in range(num_cores):
                c_dtotal = r1.cores_total[i] - r0.cores_total[i]
                c_dbusy = r1.cores_busy[i] - r0.cores_busy[i]
                if c_dtotal > 0:
                    cpct = round(max(0.0, min(100.0, (c_dbusy / c_dtotal) * 100.0)), 1)
                else:
                    cpct = 0.0
                per_core.append(cpct)

            result = {
                "timestamp": iso_now,
                "epoch_time": now,
                "sample_interval_sec": round(dt, 3),
                "is_valid": True,
                "is_stale": False,
                "metric_type": "host_total",
                "cpu_usage_percent": cpu_pct,
                "user_percent": user_pct,
                "system_percent": sys_pct,
                "idle_percent": idle_pct,
                "iowait_percent": iowait_pct,
                "per_core_percent": per_core,
                "core_count": len(per_core),
            }
            self._last_result = result
            return result

    def get_last_measurement(self) -> dict:
        """Returns the most recent measurement without taking a new sample."""
        with self._lock:
            if self._last_result is not None:
                # Check if stale
                stale = (time.time() - self._last_result.get("epoch_time", 0)) > self._stale_threshold
                res = dict(self._last_result)
                res["is_stale"] = stale
                return res
        return self.sample()

    def _fallback_result(self, timestamp: str, is_valid: bool = False) -> dict:
        import multiprocessing
        cores = multiprocessing.cpu_count() or 1
        return {
            "timestamp": timestamp,
            "epoch_time": time.time(),
            "sample_interval_sec": 0.0,
            "is_valid": is_valid,
            "is_stale": True,
            "metric_type": "host_total",
            "cpu_usage_percent": 0.0,
            "user_percent": 0.0,
            "system_percent": 0.0,
            "idle_percent": 100.0,
            "iowait_percent": 0.0,
            "per_core_percent": [0.0] * cores,
            "core_count": cores,
        }


# Module singleton
_GLOBAL_MONITOR = SystemCpuMonitor()


def get_cpu_monitor() -> SystemCpuMonitor:
    """Returns the singleton SystemCpuMonitor instance."""
    return _GLOBAL_MONITOR


def sample_system_cpu(min_interval_sec: float = 0.05) -> dict:
    """Convenience helper to sample system CPU utilization."""
    return _GLOBAL_MONITOR.sample(min_interval_sec)
