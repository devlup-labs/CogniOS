#converts raw DB rows to statistical feature vector
import numpy as np
from config import BLACKBOX_WARMUP_SEC

FEATURE_NAMES = [
    "mean_cpu",
    "max_cpu",
    "cpu_growth_rate",     # positive = CPU badh raha hai
    "cpu_variance",
    "mean_ram",
    "memory_growth_rate",  # positive = memory leak sign
    "disk_spike_frequency",
    "context_switch_rate",
]


def extract_feature_vector(rows: list[dict]) -> list[float] | None:
    if len(rows) < BLACKBOX_WARMUP_SEC:
        return None 
        #not enough data yet

    # Safe extraction with None handling
    def safe_list(key):
        return [r[key] for r in rows if r.get(key) is not None]
    

    rows = list(reversed(rows))

    cpu    = safe_list("cpu_usage_percent")
    mem    = safe_list("memory_percent")
    disk = safe_list("disk_read")
    ctx    = safe_list("cpu_ctx_switches")

    if not cpu or not mem:
        return None
    
    # cpu features
    mean_cpu       = float(np.mean(cpu))   
    max_cpu        = float(np.max(cpu))    
    cpu_variance   = float(np.var(cpu))    
    cpu_growth_rate     = float(cpu[-1] - cpu[0]) # newest - oldest

    #mem features
    mean_ram       = float(np.mean(mem)) 
    memory_growth_rate     = float(mem[-1] - mem[0])

    #disk features
    disk_spike_freq = float(sum(1 for v in disk if v > 50)) if disk else 0.0

    # Context switch rate (scheduler congestion indicator)
    ctx_switch_rate = float(np.mean(ctx)) if ctx else 0.0

    return [
        mean_cpu,
        max_cpu,
        cpu_growth_rate,
        cpu_variance,
        mean_ram,
        memory_growth_rate,
        disk_spike_freq,
        ctx_switch_rate,
    ]