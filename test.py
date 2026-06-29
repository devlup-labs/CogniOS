"Testing Document"
import time
from collectors.layer2_process import collect_process_telemetry
from db import init_db, insert_separated_telemetry

def test_layer2_pipeline():
    print("Initializing CogniOS Test Database...")
    init_db()
    
    baselines = {}
    print("Running initial telemetry sweep (Baseline generation)...")
    top_cpu, top_mem, baselines = collect_process_telemetry(baselines)
    
    # Wait 5 seconds to simulate a real monitoring pulse
    print("Pacing for 5 seconds to calculate real delta rates...")
    time.sleep(5)
    
    print("Running second telemetry sweep...")
    top_cpu, top_mem, baselines = collect_process_telemetry(baselines)
    
    print(f"Top CPU Process Count: {len(top_cpu)}")
    print(f"Top RAM Process Count: {len(top_mem)}")
    
    print("Writing captured data to separate SQLite tables...")
    insert_separated_telemetry(top_cpu, top_mem)
    print("Success! Check your root directory for 'cognios_telemetry.db'.")

if __name__ == "__main__":
    test_layer2_pipeline()