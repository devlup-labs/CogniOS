"""Pure math functions for resource attribution and workload scoring."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def compute_cpu_attribution(bucket_cpu_sum: float, system_cpu_used: float) -> float:
    """Calculates CPU Resource Attribution Score.
    
    Attribution = CPU_bucket / max(System_CPU_in_use, 0.1)
    Clamped to [0.0, 1.0].
    """
    if system_cpu_used <= 0.1 or bucket_cpu_sum <= 0.0:
        return 0.0
    
    attr = bucket_cpu_sum / system_cpu_used
    return min(1.0, max(0.0, round(attr, 4)))


def compute_ram_attribution(bucket_rss_mb: float, system_rss_used_mb: float) -> float:
    """Calculates RAM Resource Attribution Score.
    
    Attribution = RAM_bucket / max(System_RAM_used_mb, 1.0)
    Clamped to [0.0, 1.0].
    """
    if system_rss_used_mb <= 1.0 or bucket_rss_mb <= 0.0:
        return 0.0

    attr = bucket_rss_mb / system_rss_used_mb
    return min(1.0, max(0.0, round(attr, 4)))


def compute_evidence_score(matched_proc_count: int, bucket: str) -> float:
    """Calculates process identity evidence score based on process count and bucket type."""
    if matched_proc_count <= 0:
        return 0.0

    # Compilers are unambiguous indicators
    weight = 1.0 if bucket == "COMPILATION" else (
        0.9 if bucket == "GAMING" else (
            0.7 if bucket in ("CODING", "BROWSING") else 0.6
        )
    )

    # Logarithmic scaling for multiple process instances
    score = matched_proc_count * weight
    return round(score, 2)


def compute_workload_score(
    cpu_attr: float,
    ram_attr: float,
    evidence_score: float,
    persistence_ratio: float = 1.0,
    weights: dict = None
) -> float:
    """Calculates multi-dimensional Workload Dominance Score.
    
    Score = w_c * CPU_attr + w_m * RAM_attr + w_e * Evidence + w_t * Persistence
    """
    if weights is None:
        weights = {
            "cpu": getattr(config, "RULE_SCORE_WEIGHT_CPU", 0.55),
            "ram": getattr(config, "RULE_SCORE_WEIGHT_RAM", 0.20),
            "evidence": getattr(config, "RULE_SCORE_WEIGHT_EVIDENCE", 0.15),
            "persistence": getattr(config, "RULE_SCORE_WEIGHT_PERSISTENCE", 0.10),
        }

    # Normalize evidence score to [0, 1] range (cap at 3.0 points = 1.0)
    norm_evidence = min(1.0, evidence_score / 3.0)

    score = (
        weights["cpu"] * cpu_attr +
        weights["ram"] * ram_attr +
        weights["evidence"] * norm_evidence +
        weights["persistence"] * min(1.0, max(0.0, persistence_ratio))
    )

    return round(score, 4)


if __name__ == "__main__":
    assert compute_cpu_attribution(60.0, 80.0) == 0.75
    assert compute_cpu_attribution(0.0, 0.0) == 0.0
    assert compute_cpu_attribution(100.0, 80.0) == 1.0
    assert compute_ram_attribution(2000.0, 8000.0) == 0.25
    assert compute_evidence_score(3, "COMPILATION") == 3.0
    score = compute_workload_score(0.75, 0.25, 3.0, 1.0)
    assert 0.0 <= score <= 1.0
    print(f"[✔] attribution math tests passed successfully (sample score: {score}).")
