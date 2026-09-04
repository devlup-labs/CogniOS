"""Workload State Manager implementing state machine, temporal persistence, and cooldown hysteresis."""

import time
from collections import deque
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class WorkloadState:
    IDLE = "IDLE"
    OBSERVING = "OBSERVING"
    CONFIRMED = "CONFIRMED"
    OPTIMIZED = "OPTIMIZED"
    RESTORING = "RESTORING"


class WorkloadStateManager:
    """Manages workload transitions using temporal history, hysteresis, and cooldown rules."""

    def __init__(self, history_len: int = None, persistence_count: int = None, cooldown_sec: int = None):
        self.history_len = history_len or getattr(config, "RULE_HISTORY_LEN", 8)
        self.persistence_count = persistence_count or getattr(config, "RULE_PERSISTENCE_COUNT", 3)
        self.cooldown_sec = cooldown_sec or getattr(config, "RULE_COOLDOWN_SEC", 45)

        self.history = deque(maxlen=self.history_len)
        self.current_state = WorkloadState.IDLE
        self.current_workload = "IDLE"
        self.consecutive_count = 0
        self.last_state_change = time.time()
        self.last_optimized_time = 0.0
        
        # Last confirmed workload snapshot details
        self.latest_metrics = {
            "cpu_attribution": 0.0,
            "ram_attribution": 0.0,
            "score": 0.0,
            "top_process": "N/A",
            "evidence": [],
        }

    def update(self, evaluation_scores: dict, system_metrics: dict) -> dict:
        """Updates temporal state with the latest rule engine evaluation snapshot."""
        now = time.time()
        system_cpu = float(system_metrics.get("cpu_usage_percent", 0.0))
        idle_threshold = getattr(config, "RULE_IDLE_CPU_THRESHOLD", 10.0)

        # Check system IDLE: only go IDLE if CPU is very low AND no workload process matches anything
        has_active_workload = any(
            res["process_count"] > 0 and res["score"] > 0.12
            for res in evaluation_scores.values()
        )

        if system_cpu < idle_threshold and not has_active_workload:
            if self.current_workload != "IDLE":
                self.current_state = WorkloadState.RESTORING
                self.current_workload = "IDLE"
                self.consecutive_count = 0
                self.last_state_change = now
            else:
                self.current_state = WorkloadState.IDLE
            
            self.history.append({"workload": "IDLE", "score": 0.0})
            return self.get_current_state()

        # Determine highest scoring candidate bucket
        candidate_workload = "UNKNOWN"
        top_res = None
        top_score = -1.0

        for bucket, data in evaluation_scores.items():
            if data["score"] > top_score and (data["process_count"] > 0 or data["score"] > 0.2):
                top_score = data["score"]
                candidate_workload = bucket
                top_res = data

        self.history.append({"workload": candidate_workload, "score": top_score})

        if top_res:
            top_proc_name = top_res["matched_processes"][0]["name"] if top_res["matched_processes"] else "N/A"
            evidence_items = []
            for p in top_res["matched_processes"][:5]:
                cpu_pct = p.get('cpu_percent', 0.0)
                ram_mb = p.get('memory_rss_mb', 0.0)
                evidence_items.append(
                    f"{p['name']} (PID {p['pid']}) — CPU: {cpu_pct:.1f}%, RAM: {ram_mb:.0f} MB"
                )
            # Add aggregate evidence lines
            evidence_items.append(
                f"{top_res['process_count']} {candidate_workload} process(es) attributed — "
                f"CPU: {top_res['cpu_attribution']:.0%}, RAM: {top_res['ram_attribution']:.0%}"
            )
            if self.consecutive_count >= 1:
                evidence_items.append(f"Sustained for {self.consecutive_count} consecutive cycles")
            if system_cpu >= getattr(config, "RULE_SYSTEM_CPU_CONTENTION", 35.0):
                evidence_items.append(f"System CPU contention active: {system_cpu:.1f}%")

            self.latest_metrics = {
                "cpu_attribution": top_res["cpu_attribution"],
                "ram_attribution": top_res["ram_attribution"],
                "score": top_res["score"],
                "top_process": top_proc_name,
                "evidence": evidence_items,
            }

        # Track consecutive occurrences of the top workload
        if candidate_workload == self.current_workload:
            self.consecutive_count += 1
        else:
            self.current_workload = candidate_workload
            self.consecutive_count = 1
            if self.current_state != WorkloadState.OPTIMIZED:
                self.current_state = WorkloadState.OBSERVING

        # Evaluate state transitions
        if self.current_state == WorkloadState.OBSERVING:
            if self.consecutive_count >= self.persistence_count:
                self.current_state = WorkloadState.CONFIRMED
                self.last_state_change = now

        elif self.current_state == WorkloadState.OPTIMIZED:
            # Cooldown check: preserve optimization state unless cooldown expired or workload changed cleanly
            time_in_opt = now - self.last_optimized_time
            if time_in_opt >= self.cooldown_sec and self.consecutive_count >= self.persistence_count:
                # Cooldown expired and workload is confirmed persistent
                pass
            elif self.consecutive_count == 1 and time_in_opt < self.cooldown_sec:
                # Still within cooldown window; transition back to observing candidate
                self.current_state = WorkloadState.OBSERVING

        return self.get_current_state()

    def mark_optimized(self):
        """Called when optimization policies have been successfully applied."""
        self.current_state = WorkloadState.OPTIMIZED
        self.last_optimized_time = time.time()

    def get_current_state(self) -> dict:
        """Returns clean representation of current state."""
        return {
            "workload": self.current_workload,
            "state": self.current_state,
            "consecutive_cycles": self.consecutive_count,
            "cpu_attribution": self.latest_metrics["cpu_attribution"],
            "ram_attribution": self.latest_metrics["ram_attribution"],
            "score": self.latest_metrics["score"],
            "top_process": self.latest_metrics["top_process"],
            "evidence": self.latest_metrics["evidence"],
        }


if __name__ == "__main__":
    sm = WorkloadStateManager(persistence_count=3)
    dummy_eval = {
        "COMPILATION": {
            "cpu_attribution": 0.8,
            "ram_attribution": 0.3,
            "evidence_score": 2.0,
            "score": 0.75,
            "process_count": 2,
            "matched_processes": [{"pid": 123, "name": "gcc", "cpu_percent": 60.0, "memory_rss_mb": 100.0}]
        }
    }
    dummy_sys = {"cpu_usage_percent": 85.0}

    # Cycle 1 -> OBSERVING
    st1 = sm.update(dummy_eval, dummy_sys)
    assert st1["state"] == WorkloadState.OBSERVING
    assert st1["consecutive_cycles"] == 1

    # Cycle 2 -> OBSERVING
    st2 = sm.update(dummy_eval, dummy_sys)
    assert st2["state"] == WorkloadState.OBSERVING
    assert st2["consecutive_cycles"] == 2

    # Cycle 3 -> CONFIRMED
    st3 = sm.update(dummy_eval, dummy_sys)
    assert st3["state"] == WorkloadState.CONFIRMED
    assert st3["consecutive_cycles"] == 3

    print(f"[✔] state_manager tests passed successfully. State: {st3['state']}, Workload: {st3['workload']}")
