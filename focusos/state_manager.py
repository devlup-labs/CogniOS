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
            "target_pids": [],
            "ml_confidence": 0.0,
            "ml_workload": "IDLE",
            "ml_probabilities": {},
            "score_source": "RULE_ENGINE",
        }

    def update(self, evaluation_scores: dict, system_metrics: dict, ml_inference: dict = None) -> dict:
        """Updates temporal state with the latest rule engine and ML model evaluation snapshot."""
        now = time.time()
        system_cpu = float(system_metrics.get("cpu_usage_percent", 0.0))
        idle_threshold = getattr(config, "RULE_IDLE_CPU_THRESHOLD", 10.0)

        # Parse ML inference if provided
        ml_workload = None
        ml_conf = 0.0
        ml_valid = False
        if ml_inference and ml_inference.get("is_valid"):
            ml_workload = str(ml_inference.get("workload", "IDLE")).upper()
            ml_conf = float(ml_inference.get("confidence", 0.0))
            ml_valid = True
            self.latest_metrics["ml_confidence"] = ml_conf
            self.latest_metrics["ml_workload"] = ml_workload
            self.latest_metrics["ml_probabilities"] = ml_inference.get("probabilities", {})

        # Check system IDLE: only go IDLE if CPU is very low AND no workload process matches anything
        has_active_workload = any(
            res["process_count"] > 0 and res["score"] > 0.05
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
            
            idle_score = ml_conf if (ml_valid and ml_workload == "IDLE") else 0.0
            self.latest_metrics["score"] = idle_score
            self.latest_metrics["score_source"] = "XGBoost ML Model" if (ml_valid and ml_workload == "IDLE") else "Rule Engine"
            self.history.append({"workload": "IDLE", "score": idle_score})
            return self.get_current_state()

        # Determine highest scoring candidate bucket from rule engine
        candidate_workload = "UNKNOWN"
        top_res = None
        top_score = -1.0

        for bucket, data in evaluation_scores.items():
            if data["score"] > top_score and (data["process_count"] > 0 or data["score"] > 0.2):
                top_score = data["score"]
                candidate_workload = bucket
                top_res = data

        # ML-assisted candidate selection:
        # 1. If rule engine has no strong process match and ML is confident
        if (candidate_workload == "UNKNOWN" or top_score < 0.3) and ml_valid and ml_conf >= 0.60 and ml_workload != "IDLE":
            candidate_workload = ml_workload
            score_to_use = ml_conf
            score_source = "XGBoost ML Model"
        elif ml_valid and ml_workload == candidate_workload:
            # Both Rule Engine and ML agree on the exact same workload!
            score_to_use = max(top_score, ml_conf)
            score_source = "XGBoost ML Model" if ml_conf >= top_score else "Rule Engine"
        else:
            # Rule Engine has clear process evidence which defines the workload
            score_to_use = max(0.0, top_score)
            score_source = "Rule Engine"

        self.history.append({"workload": candidate_workload, "score": score_to_use})

        evidence_items = []
        if ml_valid and ml_conf > 0.0:
            if ml_workload == candidate_workload:
                evidence_items.append(
                    f"XGBoost Classifier: {ml_workload} ({ml_conf * 100:.1f}% confidence)"
                )
            else:
                evidence_items.append(
                    f"XGBoost Network Signature: {ml_workload} ({ml_conf * 100:.1f}%) — overridden by active {candidate_workload} process load"
                )

        if top_res:
            top_proc_name = top_res["matched_processes"][0]["name"] if top_res["matched_processes"] else "N/A"
            for p in top_res["matched_processes"][:5]:
                raw_cpu = float(p.get('cpu_percent', 0.0))
                num_cores = max(1, psutil.cpu_count() or 1)
                cpu_pct = round(raw_cpu / num_cores if raw_cpu > 100.0 else raw_cpu, 1)
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

            target_pids = [
                p["pid"] for p in top_res.get("matched_processes", [])
                if isinstance(p, dict) and p.get("pid") is not None
            ]
            self.latest_metrics = {
                "cpu_attribution": top_res["cpu_attribution"],
                "ram_attribution": top_res["ram_attribution"],
                "score": score_to_use,
                "score_source": score_source,
                "top_process": top_proc_name,
                "evidence": evidence_items,
                "target_pids": target_pids,
                "ml_confidence": ml_conf,
                "ml_workload": ml_workload or "IDLE",
                "ml_probabilities": ml_inference.get("probabilities", {}) if ml_inference else {},
            }
        else:
            self.latest_metrics = {
                "cpu_attribution": 0.0,
                "ram_attribution": 0.0,
                "score": score_to_use,
                "score_source": score_source,
                "top_process": "system",
                "evidence": evidence_items,
                "target_pids": [],
                "ml_confidence": ml_conf,
                "ml_workload": ml_workload or "IDLE",
                "ml_probabilities": ml_inference.get("probabilities", {}) if ml_inference else {},
            }

        # Track consecutive occurrences of the top workload
        if candidate_workload == self.current_workload:
            self.consecutive_count += 1
        else:
            prev_state = self.current_state
            self.current_workload = candidate_workload
            self.consecutive_count = 1
            if prev_state == WorkloadState.OPTIMIZED:
                self.current_state = WorkloadState.RESTORING
                self.last_state_change = now
            else:
                self.current_state = WorkloadState.OBSERVING

        # Evaluate state transitions
        if self.current_state == WorkloadState.RESTORING:
            if self.consecutive_count > 1:
                self.current_state = WorkloadState.OBSERVING
                self.last_state_change = now

        elif self.current_state == WorkloadState.OBSERVING:
            if self.consecutive_count >= self.persistence_count:
                self.current_state = WorkloadState.CONFIRMED
                self.last_state_change = now

        elif self.current_state == WorkloadState.OPTIMIZED:
            # Cooldown check: preserve optimization state unless cooldown expired or workload changed
            time_in_opt = now - self.last_optimized_time
            if time_in_opt >= self.cooldown_sec and self.consecutive_count >= self.persistence_count:
                pass
            elif self.consecutive_count == 1:
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
            "cpu_attribution": self.latest_metrics.get("cpu_attribution", 0.0),
            "ram_attribution": self.latest_metrics.get("ram_attribution", 0.0),
            "score": self.latest_metrics.get("score", 0.0),
            "score_source": self.latest_metrics.get("score_source", "Rule Engine"),
            "top_process": self.latest_metrics.get("top_process", "N/A"),
            "evidence": self.latest_metrics.get("evidence", []),
            "target_pids": self.latest_metrics.get("target_pids", []),
            "ml_confidence": self.latest_metrics.get("ml_confidence", 0.0),
            "ml_workload": self.latest_metrics.get("ml_workload", "IDLE"),
            "ml_probabilities": self.latest_metrics.get("ml_probabilities", {}),
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
