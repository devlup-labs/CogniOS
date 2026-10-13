import subprocess
import threading
import time

from logging_utils import get_layer_logger

_latest = {}
_lock = threading.Lock()


def update_metrics(metrics):
    with _lock:
        _latest.clear()
        _latest.update(metrics)


def notify(title, msg, urgency="normal"):
    logger = get_layer_logger("notifier")
    try:
        result = subprocess.run(
            ["notify-send", "-a", "CogniOS", "-u", urgency, title, msg],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode:
            logger.warning("notify-send failed: %s", result.stderr.strip())
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("notify-send failed: %s", exc)


def notify_critical(msg):
    notify("CogniOS Critical", msg, urgency="critical")


def run_notifier(stop_event):
    thresholds = (
        ("cpu_usage_percent", "CPU", 90),
        ("memory_percent", "RAM", 90),
        ("disk_usage_percent", "Disk", 90),
        ("swap_percent", "Swap", 80),
        ("max_temp", "Temperature", 90),
    )
    last_alerts = {}
    last_summary = time.monotonic()

    def percent(key):
        value = metrics.get(key)
        return f"{value:.1f}%" if isinstance(value, (int, float)) else "N/A"

    while not stop_event.is_set():
        with _lock:
            metrics = _latest.copy()

        now = time.monotonic()
        for key, label, limit in thresholds:
            value = metrics.get(key)
            if isinstance(value, (int, float)) and value > limit:
                if now - last_alerts.get(key, now - 600) >= 600:
                    unit = "C" if key == "max_temp" else "%"
                    notify_critical(f"{label} is {value:.1f}{unit} (limit {limit}{unit}).")
                    last_alerts[key] = now

        if now - last_summary >= 7200:
            notify(
                "CogniOS Status",
                f"CPU: {percent('cpu_usage_percent')}, "
                f"RAM: {percent('memory_percent')}, "
                f"Disk: {percent('disk_usage_percent')}, "
                f"Battery: {percent('battery_percent')}",
            )
            last_summary = now

        stop_event.wait(10)
