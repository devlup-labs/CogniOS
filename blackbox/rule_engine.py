#deterministic threshold-based checks (backup)
from config import (
    BLACKBOX_CPU_CRITICAL,
    BLACKBOX_MEM_CRITICAL,
    BLACKBOX_ZOMBIE_LIMIT,
    BLACKBOX_TEMP_CRITICAL,
)


def check_rules(metrics: dict) -> list[dict]:
    """
    Input:  one Layer 1 metrics dict
    Output: list of alerts that fired (empty list = all clear)
    """
    alerts = []

    cpu = metrics.get("cpu_usage_percent")
    mem = metrics.get("memory_percent")
    zombies = metrics.get("zombie_processes")
    temp = metrics.get("max_temp")

    if cpu is not None and cpu > BLACKBOX_CPU_CRITICAL:
        alerts.append({
            "type": "cpu_critical",
            "severity": "high",
            "message": f"CPU usage at {cpu:.1f}% — above critical threshold of {BLACKBOX_CPU_CRITICAL}%"
        })

    if mem is not None and mem > BLACKBOX_MEM_CRITICAL:
        alerts.append({
            "type": "memory_critical",
            "severity": "high",
            "message": f"Memory usage at {mem:.1f}% — above critical threshold of {BLACKBOX_MEM_CRITICAL}%"
        })

    if zombies is not None and zombies > BLACKBOX_ZOMBIE_LIMIT:
        alerts.append({
            "type": "zombie_buildup",
            "severity": "medium",
            "message": f"{zombies} zombie processes detected — possible parent process failure"
        })

    if temp is not None and temp > BLACKBOX_TEMP_CRITICAL:
        alerts.append({
            "type": "temp_critical",
            "severity": "high",
            "message": f"System temperature at {temp:.1f}°C — above critical threshold of {BLACKBOX_TEMP_CRITICAL}°C"
        })

    return alerts