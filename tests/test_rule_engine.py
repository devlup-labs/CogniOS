"""Unit tests for CogniOS Deterministic Rule Engine."""

import unittest
import psutil

from focusos.rules.process_vocab import match_process_to_bucket, is_protected_process
from focusos.attribution import compute_cpu_attribution, compute_ram_attribution, compute_workload_score
from focusos.rules.rule_engine import evaluate
from focusos.state_manager import WorkloadStateManager, WorkloadState
from focusos.policy import get_policy
from focusos.process_state import save_original, restore_process, is_tracked, clear_registry


class TestRuleEngine(unittest.TestCase):

    def test_01_process_vocabulary(self):
        """Test vocabulary keyword matching, word boundary isolation, and protection rules."""
        self.assertEqual(match_process_to_bucket("gcc"), "COMPILATION")
        self.assertEqual(match_process_to_bucket("g++"), "COMPILATION")
        self.assertEqual(match_process_to_bucket("clang-14"), "COMPILATION")
        # Word boundary tests: google-chrome should match BROWSING, not COMPILATION (via 'go')
        self.assertEqual(match_process_to_bucket("google-chrome"), "BROWSING")
        self.assertEqual(match_process_to_bucket("chrome"), "BROWSING")
        # bash should NOT match COMPILATION (previously collided with GNU assembler 'as')
        self.assertIsNone(match_process_to_bucket("bash"))
        self.assertEqual(match_process_to_bucket("as"), "COMPILATION")
        self.assertEqual(match_process_to_bucket("code"), "CODING")
        self.assertEqual(match_process_to_bucket("zoom"), "VIDEO_CALL")
        self.assertEqual(match_process_to_bucket("steam"), "GAMING")
        self.assertIsNone(match_process_to_bucket("unknown_process_xyz"))

        self.assertTrue(is_protected_process("systemd"))
        self.assertTrue(is_protected_process("pipewire"))
        self.assertTrue(is_protected_process("gnome-shell"))
        self.assertTrue(is_protected_process("Xorg"))
        self.assertFalse(is_protected_process("gcc"))
        self.assertFalse(is_protected_process("chrome"))

    def test_02_attribution_math(self):
        """Test CPU and RAM attribution calculations."""
        self.assertEqual(compute_cpu_attribution(60.0, 80.0), 0.75)
        self.assertEqual(compute_cpu_attribution(0.0, 0.0), 0.0)
        self.assertEqual(compute_cpu_attribution(120.0, 80.0), 1.0)
        self.assertEqual(compute_ram_attribution(500.0, 1000.0), 0.5)

    def test_03_rule_engine_evaluation(self):
        """Test rule engine snapshot scoring."""
        procs = [
            {"pid": 100, "name": "gcc", "cpu_percent": 70.0, "memory_rss_mb": 200.0},
            {"pid": 101, "name": "cc1plus", "cpu_percent": 20.0, "memory_rss_mb": 150.0},
        ]
        sys_metrics = {"cpu_usage_percent": 90.0, "memory_used": 4000.0}

        scores = evaluate(procs, sys_metrics)
        self.assertIn("COMPILATION", scores)
        self.assertGreater(scores["COMPILATION"]["score"], 0.5)

    def test_04_state_manager_transitions(self):
        """Test temporal persistence gate (OBSERVING -> CONFIRMED) and target_pids tracking."""
        sm = WorkloadStateManager(persistence_count=3)
        eval_data = {
            "COMPILATION": {
                "cpu_attribution": 0.8,
                "ram_attribution": 0.2,
                "evidence_score": 1.5,
                "score": 0.7,
                "process_count": 2,
                "matched_processes": [{"pid": 101, "name": "gcc", "cpu_percent": 50.0, "memory_rss_mb": 100.0}]
            }
        }
        sys_metrics = {"cpu_usage_percent": 80.0}

        # Cycle 1
        st1 = sm.update(eval_data, sys_metrics)
        self.assertEqual(st1["state"], WorkloadState.OBSERVING)

        # Cycle 2
        st2 = sm.update(eval_data, sys_metrics)
        self.assertEqual(st2["state"], WorkloadState.OBSERVING)

        # Cycle 3 -> Persistent threshold reached
        st3 = sm.update(eval_data, sys_metrics)
        self.assertEqual(st3["state"], WorkloadState.CONFIRMED)
        self.assertIn(101, st3.get("target_pids", []))
        self.assertTrue(any("gcc" in item for item in st3.get("evidence", [])))

    def test_05_policy_mapping(self):
        """Test policy retrieval."""
        pol = get_policy("COMPILATION")
        self.assertEqual(pol["target_bucket_nice"], -10)
        self.assertEqual(pol["background_nice"], +7)

        pol_unk = get_policy("UNKNOWN_CATEGORY")
        self.assertEqual(pol_unk["workload"], "UNKNOWN")

    def test_06_process_state_rollback(self):
        """Test process state registry and rollback mechanism."""
        clear_registry()
        current_proc = psutil.Process()
        saved = save_original(current_proc, "TEST_POLICY")
        self.assertTrue(saved)
        self.assertTrue(is_tracked(current_proc.pid))

        restored = restore_process(current_proc.pid)
        self.assertTrue(restored)
        self.assertFalse(is_tracked(current_proc.pid))

    def test_07_apply_policy_prioritization(self):
        """Test apply_policy prioritizes target processes and depresses background processes."""
        from unittest.mock import patch
        from focusos.optimisation import apply_policy

        class MockProc:
            def __init__(self, pid, name, nice_val=0):
                self.pid = pid
                self.info = {"pid": pid, "name": name}
                self._nice = nice_val
                self.affinity = []
            def nice(self, val=None):
                if val is not None:
                    self._nice = val
                return self._nice
            def cpu_affinity(self, aff=None):
                if aff is not None:
                    self.affinity = aff
                return self.affinity
            def create_time(self):
                return 1000.0

        proc_target = MockProc(201, "gcc", 0)
        proc_bg = MockProc(202, "spotify", 0)

        with patch("psutil.process_iter", return_value=[proc_target, proc_bg]), \
             patch("focusos.optimisation.is_protected", return_value=False), \
             patch("focusos.optimisation.save_original", return_value=True):

            state = {"workload": "COMPILATION", "target_pids": [201]}
            policy = {
                "workload": "COMPILATION",
                "target_bucket_nice": -10,
                "background_nice": 7,
                "affinity_pin": True,
            }

            actions = apply_policy(policy, state, conn=None)
            self.assertEqual(proc_target.nice(), -10)
            self.assertEqual(proc_bg.nice(), 7)
            self.assertTrue(any(a["pid"] == 201 and "nice -> -10" in a["action"] for a in actions))
            self.assertTrue(any(a["pid"] == 202 and "depress_nice -> 7" in a["action"] for a in actions))

    def test_09_workload_switch_transition(self):
        """Test that switching workloads while in OPTIMIZED state triggers RESTORING before OBSERVING/CONFIRMED."""
        sm = WorkloadStateManager(persistence_count=2, cooldown_sec=1)
        eval_comp = {
            "COMPILATION": {
                "cpu_attribution": 0.8, "ram_attribution": 0.2, "evidence_score": 1.0,
                "score": 0.8, "process_count": 1, "matched_processes": [{"pid": 1, "name": "gcc", "cpu_percent": 50, "memory_rss_mb": 100}]
            }
        }
        eval_browse = {
            "BROWSING": {
                "cpu_attribution": 0.8, "ram_attribution": 0.2, "evidence_score": 1.0,
                "score": 0.8, "process_count": 1, "matched_processes": [{"pid": 2, "name": "chrome", "cpu_percent": 50, "memory_rss_mb": 100}]
            }
        }
        sys_metrics = {"cpu_usage_percent": 60.0}

        # 1. Establish and optimize COMPILATION
        sm.update(eval_comp, sys_metrics)
        st = sm.update(eval_comp, sys_metrics)
        self.assertEqual(st["state"], WorkloadState.CONFIRMED)
        sm.mark_optimized()
        self.assertEqual(sm.current_state, WorkloadState.OPTIMIZED)

        # 2. Switch to BROWSING -> cycle 1 must trigger RESTORING
        st1 = sm.update(eval_browse, sys_metrics)
        self.assertEqual(st1["state"], WorkloadState.RESTORING)
        self.assertEqual(st1["workload"], "BROWSING")

        # 3. Cycle 2 sustained BROWSING -> transitions to OBSERVING
        st2 = sm.update(eval_browse, sys_metrics)
        self.assertEqual(st2["state"], WorkloadState.OBSERVING)

        # 4. Cycle 3 sustained BROWSING -> transitions to CONFIRMED
        st3 = sm.update(eval_browse, sys_metrics)
        self.assertEqual(st3["state"], WorkloadState.CONFIRMED)


if __name__ == "__main__":
    unittest.main()

