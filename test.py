"""CogniOS Layer 2 telemetry daemon entry point."""
import time
from collectors.layer2_process import collect_process_telemetry
from db import init_db, insert_process_snapshot

if __name__ == "__main__":
    init_db()
    baselines = {}
    print("CogniOS Telemetry Daemon started. Press Ctrl+C to stop.")

    try:
        while True:
            top_cpu, top_mem, baselines = collect_process_telemetry(baselines)
            insert_process_snapshot(top_cpu, top_mem)
            print(
                f"Snapshot committed at t={time.time():.0f} | "
                f"top_cpu={top_cpu[0]['name']} score={top_cpu[0]['cpu_score']} | "
                f"top_ram={top_mem[0]['name']} score={top_mem[0]['ram_score']}"
            )
    except KeyboardInterrupt:
        print("\nDaemon safely terminated.")