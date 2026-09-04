"""Deterministic rule engine for process-level resource attribution and evaluation."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import config
from focusos.rules.process_vocab import match_process_to_bucket, WORKLOAD_BUCKETS
from focusos.attribution import (
    compute_cpu_attribution,
    compute_ram_attribution,
    compute_evidence_score,
    compute_workload_score,
)


def evaluate(processes: list[dict], system_metrics: dict) -> dict:
    """Evaluates process snapshot and system metrics against deterministic rules.
    
    Args:
        processes: List of process dicts containing 'name', 'pid', 'cpu_percent', 'memory_rss_mb' (or 'memory_info').
        system_metrics: Dict with system-level metrics like 'cpu_usage_percent', 'memory_used'.
        
    Returns:
        Dict mapping workload bucket names to evaluation results:
        {
            "COMPILATION": {
                "cpu_attribution": float,
                "ram_attribution": float,
                "evidence_score": float,
                "score": float,
                "process_count": int,
                "matched_processes": list[dict]
            }, ...
        }
    """
    system_cpu = max(0.1, float(system_metrics.get("cpu_usage_percent", 0.0)))
    
    # System RAM used in MB
    system_ram_mb = float(system_metrics.get("memory_used", 0.0))
    if system_ram_mb <= 0.0 and "memory_percent" in system_metrics:
        # Fallback approximation if MB not present
        system_ram_mb = float(system_metrics.get("memory_percent", 0.0)) * 100.0

    system_ram_mb = max(1.0, system_ram_mb)

    # Initialize bucket metrics accumulator
    buckets = {
        b: {"cpu_sum": 0.0, "ram_sum": 0.0, "procs": []}
        for b in WORKLOAD_BUCKETS.keys()
    }
    
    unknown_procs = []

    cpu_threshold = getattr(config, "RULE_CPU_ACTIVE_THRESHOLD", 2.0)
    ram_threshold = getattr(config, "RULE_RAM_ACTIVE_THRESHOLD", 0.5)

    for proc in processes:
        if not isinstance(proc, dict):
            continue

        name = proc.get("name", "")
        cpu = float(proc.get("cpu_percent", 0.0) or 0.0)
        
        # Handle RAM info formats (MB float or psutil struct/dict)
        ram_mb = float(proc.get("memory_rss_mb", 0.0) or proc.get("memory_info", {}).get("rss", 0.0) / (1024 * 1024) if isinstance(proc.get("memory_info"), dict) else 0.0)
        
        matched_bucket = match_process_to_bucket(name)

        # Relevance filter: process must meet CPU/RAM threshold or be an explicit vocab match
        if cpu >= cpu_threshold or ram_mb >= ram_threshold or matched_bucket is not None:
            if matched_bucket:
                buckets[matched_bucket]["cpu_sum"] += cpu
                buckets[matched_bucket]["ram_sum"] += ram_mb
                buckets[matched_bucket]["procs"].append({
                    "pid": proc.get("pid"),
                    "name": name,
                    "cpu_percent": cpu,
                    "memory_rss_mb": ram_mb,
                })
            elif cpu >= cpu_threshold:
                unknown_procs.append({
                    "pid": proc.get("pid"),
                    "name": name,
                    "cpu_percent": cpu,
                    "memory_rss_mb": ram_mb,
                })

    results = {}

    for bucket, data in buckets.items():
        count = len(data["procs"])
        cpu_attr = compute_cpu_attribution(data["cpu_sum"], system_cpu)
        ram_attr = compute_ram_attribution(data["ram_sum"], system_ram_mb)
        evidence = compute_evidence_score(count, bucket)
        score = compute_workload_score(cpu_attr, ram_attr, evidence)

        results[bucket] = {
            "cpu_attribution": cpu_attr,
            "ram_attribution": ram_attr,
            "evidence_score": evidence,
            "score": score,
            "process_count": count,
            "matched_processes": data["procs"],
        }

    # Handle UNKNOWN workload category if unknown active processes exist
    if unknown_procs:
        unk_cpu_sum = sum(p["cpu_percent"] for p in unknown_procs)
        unk_ram_sum = sum(p["memory_rss_mb"] for p in unknown_procs)
        cpu_attr = compute_cpu_attribution(unk_cpu_sum, system_cpu)
        ram_attr = compute_ram_attribution(unk_ram_sum, system_ram_mb)
        evidence = compute_evidence_score(len(unknown_procs), "UNKNOWN")
        score = compute_workload_score(cpu_attr, ram_attr, evidence)

        results["UNKNOWN"] = {
            "cpu_attribution": cpu_attr,
            "ram_attribution": ram_attr,
            "evidence_score": evidence,
            "score": score,
            "process_count": len(unknown_procs),
            "matched_processes": unknown_procs,
        }

    return results


if __name__ == "__main__":
    sample_procs = [
        {"pid": 101, "name": "gcc", "cpu_percent": 45.0, "memory_rss_mb": 200.0},
        {"pid": 102, "name": "cc1plus", "cpu_percent": 30.0, "memory_rss_mb": 150.0},
        {"pid": 103, "name": "chrome", "cpu_percent": 5.0, "memory_rss_mb": 800.0},
    ]
    sample_sys = {"cpu_usage_percent": 85.0, "memory_used": 4000.0}

    eval_res = evaluate(sample_procs, sample_sys)
    assert "COMPILATION" in eval_res
    comp = eval_res["COMPILATION"]
    assert comp["process_count"] == 2
    assert comp["cpu_attribution"] == round(75.0 / 85.0, 4)
    print(f"[✔] rule_engine evaluation passed successfully. COMPILATION score: {comp['score']}")
