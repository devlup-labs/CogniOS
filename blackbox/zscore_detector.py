import numpy as np
from collections import deque
from config import (
    BLACKBOX_WINDOW_SEC,
    BLACKBOX_Z_THRESHOLD,
    BLACKBOX_WARMUP_SEC,
)


class ZScoreDetector:

    def __init__(self):
        # Initializes the ZScoreDetector with a deque for historical values, a Z-score threshold, and a warmup period.
        self.zscore_hist = deque(maxlen=BLACKBOX_WINDOW_SEC)
        self.z_threshold = BLACKBOX_Z_THRESHOLD
        self.warmup_sec  = BLACKBOX_WARMUP_SEC

    # Appends the given metric value
    def update(self, val):
        self.zscore_hist.append(val)

    # Returns the current warmup progress as a percentage of the warmup threshold.
    def warmup_pct(self):
        return min(100, int(len(self.zscore_hist) / self.warmup_sec * 100))

    # Returns True if the warmup period has been completed, otherwise False.
    def _history_with_current(self, hist, val):
        if len(hist) == 0:
            return [val]
        if hist[-1] == val:
            return list(hist)
        hist_vals = list(hist)
        hist_vals.append(val)
        if hist.maxlen is not None and len(hist_vals) > hist.maxlen:
            hist_vals.pop(0)
        return hist_vals

    # Calculates the Z-score, mean, and standard deviation for the given value against the historical window. Returns None if there are fewer than 30 samples.
    def _zscore(self, val):
        hist = self._history_with_current(self.zscore_hist, val)
        if len(hist) < 30:
            return None
        mean = np.mean(hist)
        std  = np.std(hist) + 0.001
        return (val - mean) / std, mean, std

    # Checks the given value against the historical window and returns a list of issues if the Z-score exceeds the threshold. Each issue includes severity, metric name, current value, mean, standard deviation, Z-score, and a message.
    def check(self, val, metric_name="metric", unit="%"):
        issues = []

        result = self._zscore(val)
        if result is not None:
            z, mean, std = result
            if abs(z) > self.z_threshold:
                severity = "CRITICAL" if abs(z) > 5 else "HIGH" if abs(z) > 4 else "MEDIUM"
                issues.append({
                    "check":    "sudden_spike",
                    "severity": severity,
                    "metric":   metric_name,
                    "current":  round(val, 2),
                    "mean":     round(mean, 2),
                    "std":      round(std, 2),
                    "z_score":  round(z, 2),
                    "msg": (
                        f"{metric_name} spike | "
                        f"current={val:.1f}{unit} "
                        f"baseline={mean:.1f}±{std:.1f}{unit} "
                        f"Z={z:.1f}"
                    )
                })

        return issues