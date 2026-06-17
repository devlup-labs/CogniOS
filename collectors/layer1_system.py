import psutil
import time

class SystemCollector:
    def __init__(self):
        # 1. Establish stable baseline counters for CPU and Stats
        self.last_cpu_times = psutil.cpu_times(interval=None)
        self.last_cpu_stats = psutil.cpu_stats()
        
        # 2. Establish baseline counters for Double-Rate Disk metrics
        self.last_disk_io = psutil.disk_io_counters()
        self.last_disk_time = time.time()
        
        # 3. Establish baseline counters for Network Interface states
        self.last_net_io = psutil.net_io_counters()

    def collect_all(self, dt):
        """Computes high-fidelity unwarped system metrics across all domains."""
        current_time = time.time()
        
        # --- CPU MATH SEPARATION ---
        curr_cpu_times = psutil.cpu_times(interval=None)
        curr_cpu_stats = psutil.cpu_stats()
        
        prev_idle = self.last_cpu_times.idle + self.last_cpu_times.iowait
        curr_idle = curr_cpu_times.idle + curr_cpu_times.iowait
        
        prev_total = sum(self.last_cpu_times)
        curr_total = sum(curr_cpu_times)
        
        d_idle = curr_idle - prev_idle
        d_total = curr_total - prev_total
        
        cpu_aggregate = (1.0 - (d_idle / d_total)) * 100.0 if d_total > 0 else 0.0
        iowait_pct = ((curr_cpu_times.iowait - self.last_cpu_times.iowait) / d_total) * 100.0 if d_total > 0 else 0.0
        
        ctx_switches = (curr_cpu_stats.context_switches - self.last_cpu_stats.context_switches) / dt
        interrupts = (curr_cpu_stats.interrupts - self.last_cpu_stats.interrupts) / dt

        # --- MEMORY (SWAP RATE) MATH ---
        swap = psutil.swap_memory()
        # Note: True swap page in/out rates can be extracted from /proc/vmstat if deeper insight is needed later
        
        # --- DISK DOUBLE-RATE MATH (Throughput vs IOPS) ---
        curr_disk_io = psutil.disk_io_counters()
        disk_dt = current_time - self.last_disk_time
        
        read_bytes_sec = (curr_disk_io.read_bytes - self.last_disk_io.read_bytes) / disk_dt if disk_dt > 0 else 0.0
        write_bytes_sec = (curr_disk_io.write_bytes - self.last_disk_io.write_bytes) / disk_dt if disk_dt > 0 else 0.0
        iops = ((curr_disk_io.read_count - self.last_disk_io.read_count) + 
                (curr_disk_io.write_count - self.last_disk_io.write_count)) / disk_dt if disk_dt > 0 else 0.0

        # --- NETWORK INTERFACE COUNTS ---
        curr_net_io = psutil.net_io_counters()
        drop_rate = ((curr_net_io.dropin - self.last_net_io.dropin) + 
                     (curr_net_io.dropout - self.last_net_io.dropout)) / dt

        # Dynamic Per-Core Calculation for FocusOS CNN Matrix
        per_core_pcts = psutil.cpu_percentage(interval=None, percpu=True)

        # Rotate states safely
        self.last_cpu_times = curr_cpu_times
        self.last_cpu_stats = curr_cpu_stats
        self.last_disk_io = curr_disk_io
        self.last_disk_time = current_time
        self.last_net_io = curr_net_io

        # Package data cleanly for Table 1 insertion mapping
        metrics_payload = {
            "timestamp": current_time,
            "cpu_aggregate_pct": round(cpu_aggregate, 2),
            "cpu_iowait_pct": round(iowait_pct, 2),
            "ctx_switches_sec": round(ctx_switches, 1),
            "interrupts_sec": round(interrupts, 1),
            "swap_used_bytes": swap.used,
            "read_bytes_sec": round(read_bytes_sec, 1),
            "write_bytes_sec": round(write_bytes_sec, 1),
            "iops": round(iops, 1),
            "network_drops_sec": round(drop_rate, 1)
        }
        
        # Append dynamic per-core percentages matching CORE_COLUMNS
        for i, pct in enumerate(per_core_pcts):
            metrics_payload[f"core_{i}_pct"] = pct
            
        return metrics_payload