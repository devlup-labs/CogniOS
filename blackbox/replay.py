"""Unified replay and event building for BlackBox post-crash analysis."""
import time
import numpy as np
from datetime import datetime
from blackbox.recorder import get_window_rows

def _build_events(rows: list[dict]) -> list[dict]:
    
    # Scan rows and detect significant events using per-window baseline instead of hardcoded thresholds
    if len(rows) < 10:
        return []

    events = []

    # compute per-window baseline from first 20% of rows
    baseline_window = rows[:max(10, len(rows) // 5)]
    
    def baseline(key):
        vals = []
        for r in baseline_window:
            if r.get(key) is not None:
                vals.append(r[key])
        if not vals:
            return 0, 1
        return float(np.mean(vals)), float(np.std(vals)) + 0.001

    cpu_mean, cpu_std   = baseline("cpu_usage_percent")
    mem_mean, mem_std   = baseline("memory_percent")
    disk_mean, disk_std = baseline("disk_read")
    swap_mean, swap_std = baseline("swap_percent")

    for i in range(1, len(rows)):
        curr = rows[i]
        prev = rows[i - 1]

        ts = curr.get('timestamp', 0)
        t  = datetime.fromtimestamp(ts).strftime('%H:%M:%S') if ts else '??:??'

        def val(r, key):
            return r.get(key) or 0

        # CPU spike — Z-score > 2 from baseline
        c_cpu = val(curr, 'cpu_usage_percent')
        if (c_cpu - cpu_mean) / cpu_std > 2.0:
            events.append({
                'time': t, 'timestamp': ts, 'type': 'cpu_spike',
                'detail': f'CPU spike: {val(prev,"cpu_usage_percent"):.0f}% → {c_cpu:.0f}% (baseline {cpu_mean:.0f}%)',
                'severity': 'high' if c_cpu > cpu_mean + 3 * cpu_std else 'medium'
            })

        # Memory growth — Z-score > 2 from baseline
        c_mem = val(curr, 'memory_percent')
        if (c_mem - mem_mean) / mem_std > 2.0:
            events.append({
                'time': t, 'timestamp': ts, 'type': 'memory_growth',
                'detail': f'Memory spike: {val(prev,"memory_percent"):.0f}% → {c_mem:.0f}% (baseline {mem_mean:.0f}%)',
                'severity': 'high' if c_mem > 85 else 'medium'
            })

        # Memory leak — slow sustained climb over entire window
        if i == len(rows) - 1:
            mem_vals = [r.get('memory_percent') for r in rows if r.get('memory_percent')]
            if mem_vals:
                slope = float(np.polyfit(range(len(mem_vals)), mem_vals, 1)[0])
                if slope > 0.01:  # climbing more than 0.01% per second
                    events.append({
                        'time': t, 'timestamp': ts, 'type': 'memory_leak',
                        'detail': f'Memory slowly climbing at {slope:.4f}%/s over window — possible leak',
                        'severity': 'high'
                    })

        # Process explosion
        c_proc = val(curr, 'total_processes')
        p_proc = val(prev, 'total_processes')
        if c_proc - p_proc > 30:
            events.append({
                'time': t, 'timestamp': ts, 'type': 'process_explosion',
                'detail': f'Process count jumped: {p_proc} → {c_proc}',
                'severity': 'high'
            })

        # Zombie buildup
        zombie = val(curr, 'zombie_processes')
        if zombie > 5:
            events.append({
                'time': t, 'timestamp': ts, 'type': 'zombie_buildup',
                'detail': f'{zombie} zombie processes detected',
                'severity': 'medium'
            })

        # Disk I/O storm — Z-score based
        c_disk = val(curr, 'disk_read')
        if disk_std > 0 and (c_disk - disk_mean) / disk_std > 2.5:
            events.append({
                'time': t, 'timestamp': ts, 'type': 'io_storm',
                'detail': f'Disk read spike: {c_disk:.1f} MB/s (baseline {disk_mean:.1f} MB/s)',
                'severity': 'high'
            })

        # Swap spike — Z-score based
        c_swap = val(curr, 'swap_percent')
        if swap_std > 0 and (c_swap - swap_mean) / swap_std > 2.0:
            events.append({
                'time': t, 'timestamp': ts, 'type': 'swap_spike',
                'detail': f'Swap jumped: {val(prev,"swap_percent"):.0f}% → {c_swap:.0f}%',
                'severity': 'high' if c_swap > 80 else 'medium'
            })

    return events


def _build_chain(events: list[dict], min_gap_sec: float = 30.0) -> list[dict]:
    # Deduplicate events — same type can't repeat within min_gap_sec
    if not events:
        return []
    chain = []
    last_seen = {}
    for e in sorted(events, key=lambda x: x.get('timestamp', 0)):
        key = e['type']
        ts  = e.get('timestamp', 0)
        if key not in last_seen or ts - last_seen[key] >= min_gap_sec:
            chain.append(e)
            last_seen[key] = ts
    return chain


def _format_chain(chain: list[dict], max_events: int = 25) -> str:
    if not chain:
        return "No significant events detected in this window."
    # prioritize by severity, then keep chronological order among kept ones
    if len(chain) > max_events:
        high = [e for e in chain if e.get('severity') == 'high']
        rest = [e for e in chain if e.get('severity') != 'high']
        kept = (high + rest)[:max_events]
        chain = sorted(kept, key=lambda x: x.get('timestamp', 0))
    lines = []
    for i, e in enumerate(chain):
        arrow = "\n      ↓\n" if i < len(chain) - 1 else ""
        lines.append(f"[{e['time']}] {e['detail']}{arrow}")
    if len(chain) == max_events:
        lines.append(f"\n...(chain truncated to {max_events} most significant events)")
    return "\n".join(lines)


def _trend_summary(rows: list[dict]) -> str:
    # Summarize metric trends over the window for LLM context
    if not rows:
        return "No data."

    def trend(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        if len(vals) < 2:
            return "N/A"
        start, end = vals[0], vals[-1]
        direction = "↑" if end > start + 2 else "↓" if end < start - 2 else "→ stable"
        return f"{start:.1f}% → {end:.1f}% ({direction})"

    return (
        f"CPU: {trend('cpu_usage_percent')} | "
        f"Memory: {trend('memory_percent')} | "
        f"Swap: {trend('swap_percent')} | "
        f"Load avg: {rows[-1].get('load_avg1', 'N/A')}"
    )

def replay(conn, crash_time: float = None, window_minutes: int = 30) -> dict:
    if crash_time is None:
        crash_time = time.time()
    start_time = crash_time - (window_minutes * 60)
    rows = get_window_rows(conn, start_time, crash_time)

    events = _build_events(rows)
    chain  = _build_chain(events)

    return {
        'crash_time':    crash_time,
        'window_start':  start_time,
        'total_rows':    len(rows),
        'events':        events,
        'chain':         chain,
        'timeline_text': _format_chain(chain),
        'trend_summary': _trend_summary(rows),
    }

def build_llm_context(conn, crash_time: float = None,
                      heartbeat_gap: float = None,
                      systemd_crash: bool = None) -> str:
    
    # Builds rich context string to feed to LLaMA. Includes trend, event chain, crash signal info
    result = replay(conn, crash_time=crash_time)

    # crash signal section
    crash_signal = ""
    if heartbeat_gap is not None:
        crash_signal += f"Heartbeat gap: {heartbeat_gap:.1f}s (daemon stopped unexpectedly). "
    if systemd_crash is not None:
        crash_signal += f"Systemd journal: {'crash detected' if systemd_crash else 'clean shutdown'}."

    context = f"""=== CogniOS BlackBox Crash Report ===

Window: last {30} minutes | Total telemetry rows: {result['total_rows']}

--- Metric Trends ---
{result['trend_summary']}

--- Event Chain (what happened, in order) ---
{result['timeline_text']}

--- Crash Signal ---
{crash_signal if crash_signal else 'No crash signal info available.'}
"""
    return context