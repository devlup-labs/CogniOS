"""Measure CogniOS process-tree and system overhead in browser or desktop mode."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil


def summarize(samples: list[dict]) -> dict:
    fields = (
        "system_cpu_pct", "app_cpu_pct", "app_rss_mb", "app_processes",
        "memory_available_mb", "swap_used_mb", "disk_read_mb_s",
        "disk_write_mb_s", "network_recv_mb_s", "network_sent_mb_s",
    )
    if not samples:
        return {key: {"average": 0.0, "peak": 0.0, "minimum": 0.0} for key in fields}

    return {
        key: {
            "average": round(statistics.mean(sample[key] for sample in samples), 2),
            "peak": round(max(sample[key] for sample in samples), 2),
            "minimum": round(min(sample[key] for sample in samples), 2),
        }
        for key in fields
    }


def self_test() -> None:
    result = summarize([
        {"system_cpu_pct": 10, "app_cpu_pct": 20, "app_rss_mb": 100, "app_processes": 2,
         "memory_available_mb": 1000, "swap_used_mb": 0, "disk_read_mb_s": 1,
         "disk_write_mb_s": 2, "network_recv_mb_s": 3, "network_sent_mb_s": 4},
        {"system_cpu_pct": 30, "app_cpu_pct": 40, "app_rss_mb": 200, "app_processes": 4,
         "memory_available_mb": 800, "swap_used_mb": 1, "disk_read_mb_s": 3,
         "disk_write_mb_s": 4, "network_recv_mb_s": 5, "network_sent_mb_s": 6},
    ])
    assert result["system_cpu_pct"] == {"average": 20, "peak": 30, "minimum": 10}
    assert result["app_rss_mb"] == {"average": 150, "peak": 200, "minimum": 100}
    assert summarize([])["system_cpu_pct"] == {"average": 0.0, "peak": 0.0, "minimum": 0.0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("browser", "desktop"))
    parser.add_argument("--pid", type=int, help="PID of the CogniOS main.py process")
    parser.add_argument("--ui-pid", type=int, help="Optional browser PID; include its process tree")
    parser.add_argument("--duration", type=int, default=60, help="Sample duration in seconds")
    parser.add_argument("--interval", type=float, default=1, help="Sample interval in seconds")
    parser.add_argument("--output", type=Path, default=Path("ui-overhead-results"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("Benchmark summary check passed.")
        return
    if not args.mode or not args.pid or args.duration < 1 or args.interval <= 0:
        parser.error("--mode, --pid, positive --duration, and positive --interval are required")

    try:
        roots = [psutil.Process(args.pid)]
        if args.ui_pid:
            roots.append(psutil.Process(args.ui_pid))
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as exc:
        parser.error(f"Could not access process PID(s): {exc}")
    for proc in roots:
        proc.cpu_percent(None)
    psutil.cpu_percent(None)

    args.output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"ui-overhead-{args.mode}-{stamp}"
    csv_path = args.output / f"{stem}.csv"
    json_path = args.output / f"{stem}.json"
    columns = (
        "timestamp", "elapsed_s", "mode", "system_cpu_pct", "memory_used_mb",
        "memory_available_mb", "swap_used_mb", "disk_read_mb_s", "disk_write_mb_s",
        "network_recv_mb_s", "network_sent_mb_s", "app_cpu_pct", "app_rss_mb",
        "app_processes", "pid", "parent_pid", "process_name", "process_cpu_pct",
        "process_rss_mb", "threads", "read_mb", "write_mb",
    )
    totals = []
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    previous_elapsed = 0.0
    previous_disk = psutil.disk_io_counters()
    previous_network = psutil.net_io_counters()

    with csv_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        while time.monotonic() - started < args.duration:
            time.sleep(min(args.interval, max(0, args.duration - (time.monotonic() - started))))
            now = datetime.now(timezone.utc).isoformat()
            app_cpu = app_rss = process_count = 0
            rows = []
            seen = set()

            for root in roots:
                try:
                    processes = [root, *root.children(recursive=True)]
                except psutil.Error:
                    processes = []
                for proc in processes:
                    if proc.pid in seen:
                        continue
                    seen.add(proc.pid)
                    try:
                        info = proc.as_dict(attrs=["pid", "ppid", "name", "memory_info", "num_threads"])
                        cpu = proc.cpu_percent(None)
                        io = proc.io_counters()
                        rss = info["memory_info"].rss / (1024 * 1024)
                        app_cpu += cpu
                        app_rss += rss
                        process_count += 1
                        rows.append({
                            "pid": proc.pid, "parent_pid": info["ppid"], "process_name": info["name"],
                            "process_cpu_pct": round(cpu, 2), "process_rss_mb": round(rss, 2),
                            "threads": info["num_threads"],
                            "read_mb": round(io.read_bytes / (1024 * 1024), 2) if io else "",
                            "write_mb": round(io.write_bytes / (1024 * 1024), 2) if io else "",
                        })
                    except (psutil.Error, OSError):
                        continue

            memory = psutil.virtual_memory()
            system_cpu = psutil.cpu_percent(None)
            elapsed = time.monotonic() - started
            interval = max(elapsed - previous_elapsed, 0.001)
            disk = psutil.disk_io_counters()
            network = psutil.net_io_counters()
            disk_read = (
                max(0, disk.read_bytes - previous_disk.read_bytes) / 1048576 / interval
                if disk and previous_disk else 0
            )
            disk_write = (
                max(0, disk.write_bytes - previous_disk.write_bytes) / 1048576 / interval
                if disk and previous_disk else 0
            )
            network_recv = (
                max(0, network.bytes_recv - previous_network.bytes_recv) / 1048576 / interval
                if network and previous_network else 0
            )
            network_sent = (
                max(0, network.bytes_sent - previous_network.bytes_sent) / 1048576 / interval
                if network and previous_network else 0
            )
            previous_elapsed, previous_disk, previous_network = elapsed, disk, network
            sample = {
                "system_cpu_pct": system_cpu,
                "app_cpu_pct": app_cpu,
                "app_rss_mb": app_rss,
                "app_processes": process_count,
                "memory_available_mb": round(memory.available / (1024 * 1024), 2),
                "swap_used_mb": round(psutil.swap_memory().used / (1024 * 1024), 2),
                "disk_read_mb_s": round(disk_read, 3),
                "disk_write_mb_s": round(disk_write, 3),
                "network_recv_mb_s": round(network_recv, 3),
                "network_sent_mb_s": round(network_sent, 3),
            }
            totals.append(sample)
            shared = {
                "timestamp": now,
                "elapsed_s": round(elapsed, 2),
                "mode": args.mode,
                **sample,
                "memory_used_mb": round(memory.used / (1024 * 1024), 2),
            }
            for row in rows or [{}]:
                writer.writerow({**shared, **row})
            output.flush()

    report = {
        "mode": args.mode,
        "started_at": started_at.isoformat(),
        "duration_seconds": round(time.monotonic() - started, 2),
        "sample_interval_seconds": args.interval,
        "samples": len(totals),
        "process_roots": [proc.pid for proc in roots],
        "summary": summarize(totals),
        "rss_note": "Process-tree RSS is summed and can double-count shared memory.",
        "csv": str(csv_path),
    }
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
