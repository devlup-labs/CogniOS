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
        """Test vocabulary keyword matching and protection rules."""
        self.assertEqual(match_process_to_bucket("gcc"), "COMPILATION")
        self.assertEqual(match_process_to_bucket("g++"), "COMPILATION")
        self.assertEqual(match_process_to_bucket("chrome"), "BROWSING")
        self.assertEqual(match_process_to_bucket("code"), "CODING")
        self.assertEqual(match_process_to_bucket("zoom"), "VIDEO_CALL")
        self.assertEqual(match_process_to_bucket("steam"), "GAMING")
        self.assertIsNone(match_process_to_bucket("unknown_process_xyz"))

        self.assertTrue(is_protected_process("systemd"))
        self.assertTrue(is_protected_process("pipewire"))
        self.assertFalse(is_protected_process("gcc"))

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
        """Test temporal persistence gate (OBSERVING -> CONFIRMED)."""
        sm = WorkloadStateManager(persistence_count=3)
        eval_data = {
            "COMPILATION": {
                "cpu_attribution": 0.8,
                "ram_attribution": 0.2,
                "evidence_score": 1.5,
                "score": 0.7,
                "process_count": 2,
                "matched_processes": [{"pid": 10, "name": "gcc", "cpu_percent": 50.0, "memory_rss_mb": 100.0}]
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


if __name__ == "__main__":
    unittest.main()
