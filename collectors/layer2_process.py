"""Layer 2 process telemetry collection."""
import time
import psutil

def collect_process_telemetry(prev_states=None):
    if prev_states is None:
        prev_states = {}

    current_states = {}
    processed_snapshots = []
    current_time = time.time()

    for proc in psutil.process_iter(['pid', 'name', 'num_threads', 'status']):
        try:
            info = proc.info
            pid = info['pid']
            
            cpu_percent = proc.cpu_percent(interval=None)
            mem_info = proc.memory_info()
            mem_percent = proc.memory_percent()
            
            try:
                io_counters = proc.io_counters()
                read_bytes = io_counters.read_bytes
                write_bytes = io_counters.write_bytes
            except (psutil.AccessDenied, AttributeError):
                read_bytes, write_bytes = 0, 0

            current_states[pid] = {
                'read_bytes': read_bytes,
                'write_bytes': write_bytes,
                'timestamp': current_time
            }

            calc_read_rate = 0.0
            calc_write_rate = 0.0
            if pid in prev_states:
                prev = prev_states[pid]
                time_delta = current_time - prev['timestamp']
                if time_delta > 0:
                    calc_read_rate = max(0.0, (read_bytes - prev['read_bytes']) / time_delta)
                    calc_write_rate = max(0.0, (write_bytes - prev['write_bytes']) / time_delta)

            processed_snapshots.append({
                'pid': pid,
                'name': info['name'] or 'Unknown',
                'cpu_percent': round(cpu_percent, 2),
                'memory_percent': round(mem_percent, 2),
                'rss_memory': mem_info.rss / (1024 * 1024), # MB
                'vms_memory': mem_info.vms / (1024 * 1024 * 1024), # GB
                'thread_count': info['num_threads'] or 1,
                'read_bytes_sec': round(calc_read_rate, 2),
                'write_bytes_sec': round(calc_write_rate, 2),
                'status': info['status'] or 'unknown'
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Slice out the two lists independently
    top_cpu = sorted(processed_snapshots, key=lambda x: x['cpu_percent'], reverse=True)[:5]
    top_mem = sorted(processed_snapshots, key=lambda x: x['rss_memory'], reverse=True)[:5]

    # Return as a structured tuple
    return top_cpu, top_mem, current_states


if __name__ == '__main__':
    from db import init_db, insert_separated_telemetry
    
    init_db()
    baselines = {}
    print("CogniOS Separated Telemetry Daemon started...")
    
    try:
        while True:
            top_cpu, top_mem, baselines = collect_process_telemetry(baselines)
            
            # Pass both lists cleanly to our data layer
            insert_separated_telemetry(top_cpu, top_mem)
            
            print(f"Committed Top 5 CPU and Top 5 Memory snapshots.")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nDaemon safely terminated.")