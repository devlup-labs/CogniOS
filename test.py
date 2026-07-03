"""CogniOS Layer 2 telemetry daemon entry point."""
import time
from collectors.layer2_process import collect_process_telemetry
from db import init_db, insert_process_snapshot
from config import DB_PATH
from os_doctor.featuring import get_inference_payload

def run_layer2_telemetry():
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

if __name__ == "__main__":

    i_forest_input, proc_metadata = get_inference_payload(DB_PATH)

    print(i_forest_input)
    print(proc_metadata)