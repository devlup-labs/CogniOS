#converts raw DB rows to statistical feature vector
import numpy as np
from utils.config import BLACKBOX_WARMUP_SEC


def extract_feature_vector(rows: list[dict]) -> list[float] | None:
    if len(rows) < BLACKBOX_WARMUP_SEC:
        return None 
        #not enough data yet

    rows = list(reversed(rows))

    cpu    = [r["cpu_usage_percent"] for r in rows if r["cpu_usage_percent"] is not None]
    mem    = [r["memory_percent"]    for r in rows if r["memory_percent"]    is not None]
    disk_r = [r["disk_read"]         for r in rows if r["disk_read"]         is not None]
    disk_w = [r["disk_write"]        for r in rows if r["disk_write"]        is not None]
    ctx    = [r["cpu_ctx_switches"]  for r in rows if r["cpu_ctx_switches"]  is not None]

    mean_cpu       = float(np.mean(cpu))   if cpu else 0.0
    max_cpu        = float(np.max(cpu))    if cpu else 0.0
    cpu_variance   = float(np.var(cpu))    if cpu else 0.0
    cpu_growth     = float(cpu[-1] - cpu[0]) / len(cpu) if len(cpu) > 1 else 0.0

    mean_ram       = float(np.mean(mem))             if mem else 0.0
    mem_growth     = float(mem[-1] - mem[0]) / len(mem) if len(mem) > 1 else 0.0

    disk_combined  = [r + w for r, w in zip(disk_r, disk_w)]
    if disk_combined:
        disk_threshold     = float(np.mean(disk_combined)) + float(np.std(disk_combined))
        disk_spike_freq    = sum(1 for d in disk_combined if d > disk_threshold) / len(disk_combined)
    else:
        disk_spike_freq    = 0.0

    ctx_rate = float(np.mean(np.diff(ctx))) if len(ctx) > 1 else 0.0

    return [
        mean_cpu,
        max_cpu,
        cpu_growth,
        cpu_variance,
        mean_ram,
        mem_growth,
        disk_spike_freq,
        ctx_rate,
    ]