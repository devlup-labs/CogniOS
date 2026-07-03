"""Layer 2 process telemetry collection."""
import time
import psutil 


def collect_process_telemetry(prev_states=None):
    if prev_states is None:
        prev_states = {}

    # --- Phase 0: CPU prime pass (t=0) ---
    # First cpu_percent call per Process object always returns 0.0 or a stale
    # cumulative rate. Discarding it gives the 5 sampling passes a clean 1-second
    # baseline each.
    for proc in psutil.process_iter(['pid']):
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # --- Phase 1: 5 × 1-second CPU + RAM sampling ---
    cpu_samples = {}  # pid -> [cpu_percent, ...]
    ram_samples = {}  # pid -> [rss_mb, ...]
    for _ in range(5):
        time.sleep(1.0)
        for proc in psutil.process_iter(['pid']):
            try:
                pid = proc.pid
                cpu_samples.setdefault(pid, []).append(proc.cpu_percent(interval=None))
                try:
                    ram_samples.setdefault(pid, []).append(
                        round(proc.memory_info().rss / (1024 * 1024), 3)
                    )
                except (psutil.AccessDenied, AttributeError):
                    pass
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    # --- Phase 2: Full metadata pass + aggregation ---
    current_time = time.time()
    current_states = {}
    processed_snapshots = []

    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'num_threads', 'status', 'create_time']):
        try:
            info = proc.info
            pid = info['pid']

            if pid not in cpu_samples:
                continue

            mem_info = proc.memory_info()
            mem_percent = proc.memory_percent()

            try:
                io = proc.io_counters()
                read_bytes, write_bytes = io.read_bytes, io.write_bytes
            except (psutil.AccessDenied, AttributeError):
                read_bytes, write_bytes = 0, 0

            try:
                ctx = proc.num_ctx_switches()
                ctx_vol = ctx.voluntary
                ctx_invol = ctx.involuntary
            except (psutil.AccessDenied, AttributeError):
                ctx_vol, ctx_invol = 0, 0

            try:
                times = proc.cpu_times()
                user_time, system_time = times.user, times.system
            except (psutil.AccessDenied, AttributeError):
                user_time, system_time = 0.0, 0.0

            try:
                open_fds = proc.num_fds()
            except (psutil.AccessDenied, AttributeError):
                open_fds = 0

            try:
                net_conn_count = len(proc.net_connections())
            except (psutil.AccessDenied, AttributeError):
                net_conn_count = 0

            calc_read_rate = 0.0
            calc_write_rate = 0.0
            calc_ctx_vol_rate = 0.0
            calc_ctx_invol_rate = 0.0
            if pid in prev_states:
                prev = prev_states[pid]
                dt = current_time - prev['timestamp']
                if dt > 0:
                    calc_read_rate = max(0.0, (read_bytes - prev['read_bytes']) / dt)
                    calc_write_rate = max(0.0, (write_bytes - prev['write_bytes']) / dt)
                    calc_ctx_vol_rate = max(0.0, (ctx_vol - prev['ctx_vol']) / dt)
                    calc_ctx_invol_rate = max(0.0, (ctx_invol - prev['ctx_invol']) / dt)

            current_states[pid] = {
                'read_bytes': read_bytes,
                'write_bytes': write_bytes,
                'ctx_vol': ctx_vol,
                'ctx_invol': ctx_invol,
                'timestamp': current_time,
            }

            cpu_s = cpu_samples[pid]
            cpu_avg = round(sum(cpu_s) / len(cpu_s), 2)
            cpu_peak = round(max(cpu_s), 2)
            cpu_score = round(0.6 * cpu_peak + 0.4 * cpu_avg, 2)

            ram_s = ram_samples.get(pid, [])
            if ram_s:
                ram_avg = round(sum(ram_s) / len(ram_s), 3)
                ram_peak = round(max(ram_s), 3)
                ram_score = round(0.6 * ram_peak + 0.4 * ram_avg, 3)
                rss_mb_now = ram_s[-1]
            else:
                rss_mb_now = round(mem_info.rss / (1024 * 1024), 3)
                ram_avg = ram_peak = ram_score = rss_mb_now

            processed_snapshots.append({
                'pid': pid,
                'ppid': info['ppid'],
                'name': info['name'] or 'Unknown',
                'cpu_percent': round(cpu_s[-1], 2),
                'cpu_avg': cpu_avg,
                'cpu_peak': cpu_peak,
                'cpu_score': cpu_score,
                'memory_percent': round(mem_percent, 2),
                'rss_mb': rss_mb_now,
                'ram_avg': ram_avg,
                'ram_peak': ram_peak,
                'ram_score': ram_score,
                'vms_gb': round(mem_info.vms / (1024 * 1024 * 1024), 4),
                'thread_count': info['num_threads'] or 1,
                'user_time': round(user_time, 2),
                'system_time': round(system_time, 2),
                'read_bytes_rate': round(calc_read_rate, 2),
                'write_bytes_rate': round(calc_write_rate, 2),
                'status': info['status'] or 'unknown',
                'age_sec': round(current_time - (info['create_time'] or current_time), 1),
                'open_fds': open_fds,
                'ctx_vol_rate': round(calc_ctx_vol_rate, 2),
                'ctx_invol_rate': round(calc_ctx_invol_rate, 2),
                'net_conn_count': net_conn_count,
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    top_cpu = sorted(processed_snapshots, key=lambda x: x['cpu_score'], reverse=True)[:5]
    top_mem = sorted(processed_snapshots, key=lambda x: x['ram_score'], reverse=True)[:5]

    return top_cpu, top_mem, current_states
