import psutil
import time
from datetime import datetime,timezone

def collect_layer1_metrics():
    timestamp = datetime.now(timezone.utc).isoformat()

    cpu_usage_percent = psutil.cpu_percent(interval=None)
    cpu_times = psutil.cpu_times()
    cpu_user_time = cpu_times.user
    cpu_system_time = cpu_times.system
    cpu_idle_time = cpu_times.idle
    cpu_iowait_time = getattr(cpu_times, 'iowait', None)  # iowait for Linux only
    cpu_busy_time = 100.0 - cpu_usage_percent if cpu_usage_percent is not None else None

    try:
        freq = psutil.cpu_freq()
        cpu_current_freq = freq.current if freq else None
    except Exception:
        cpu_current_freq = None
    
    try:
        cpu_ctx_switches = psutil.cpu_stats().ctx_switches
    except Exception:
        cpu_ctx_switches = None

    return {
        "timestamp": timestamp,
        "cpu_usage_percent": cpu_usage_percent,
        "cpu_current_freq": cpu_current_freq,
        "cpu_user_time": cpu_user_time,
        "cpu_system_time": cpu_system_time,
        "cpu_idle_time": cpu_idle_time,
        "cpu_iowait_time": cpu_iowait_time,
        "cpu_busy_time": cpu_busy_time,
        "cpu_ctx_switches": cpu_ctx_switches
    }