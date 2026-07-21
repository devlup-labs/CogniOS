# deterministic threshold-based checks (backup)
from config import (
    BLACKBOX_CPU_CRITICAL,
    BLACKBOX_MEM_CRITICAL,
    BLACKBOX_ZOMBIE_LIMIT,
    BLACKBOX_TEMP_CRITICAL,
    BLACKBOX_SWAP_CRITICAL,   
)


def check_rules(metrics: dict) -> list[dict]:
    """
    Input:  one Layer 1 metrics dict
    Output: list of alerts that fired (empty list = all clear)
    """
    alerts = []

    # CPU pressure
    cpu = metrics.get("cpu_usage_percent")
    if cpu is not None and cpu > BLACKBOX_CPU_CRITICAL:
        alerts.append({
            "type":     "cpu_critical",
            "severity": "high",
            "value":    cpu, # CPU usage percentage
            "message":  f"CPU usage at {cpu:.1f}% — above critical threshold of {BLACKBOX_CPU_CRITICAL}%"
        })

    # Memory pressure
    mem = metrics.get("memory_percent")
    if mem is not None and mem > BLACKBOX_MEM_CRITICAL:
        alerts.append({
            "type":     "memory_critical",
            "severity": "high",
            "value":    mem, # Memory usage percentage
            "message":  f"Memory usage at {mem:.1f}% — above critical threshold of {BLACKBOX_MEM_CRITICAL}%"
        })

    # Zombie accumulation
    zombies = metrics.get("zombie_processes")
    if zombies is not None and zombies > BLACKBOX_ZOMBIE_LIMIT:
        alerts.append({
            "type":     "zombie_buildup",
            "severity": "medium",
            "value":    zombies, # Number of zombie processes
            "message":  f"{zombies} zombie processes detected — possible parent process failure"
        })

    # Thermal throttling (max_temp — worst core temperature)
    temp = metrics.get("max_temp")
    if temp is not None and temp > BLACKBOX_TEMP_CRITICAL:
        alerts.append({
            "type":     "temp_critical",
            "severity": "high",
            "value":    temp, # System temperature
            "message":  f"System temperature at {temp:.1f}°C — above critical threshold of {BLACKBOX_TEMP_CRITICAL}°C"
        })

    # Swap pressure — memory almost exhausted
    swap = metrics.get("swap_percent")
    if swap is not None and swap > BLACKBOX_SWAP_CRITICAL:
        alerts.append({
            "type":     "swap_pressure",
            "severity": "medium",
            "value":    swap, # Swap usage percentage
            "message":  f"Swap usage at {swap:.1f}% — system under severe memory pressure"
        })

    return alerts