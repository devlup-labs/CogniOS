#builds cause-effect event chains

from datetime import datetime


def telemetry_to_events(rows: list[dict]) -> list[dict]:
    events = []

    for i in range(1, len(rows)):
        curr = rows[i]
        prev = rows[i - 1]

        ts = curr.get('timestamp', 0)
        t  = datetime.fromtimestamp(ts).strftime('%H:%M:%S') if ts else '??:??'

        # CPU spike (20% se zyada jump)
        c_cpu = curr.get('cpu_usage_percent') or 0
        p_cpu = prev.get('cpu_usage_percent') or 0
        if c_cpu - p_cpu > 20:
            events.append({'time': t, 'timestamp': ts, 'type': 'cpu_spike',
                'detail': f'CPU jumped {p_cpu:.0f}% -> {c_cpu:.0f}%',
                'severity': 'high' if c_cpu > 80 else 'medium'})

        # Memory growth (5% se zyada)
        c_mem = curr.get('memory_percent') or 0
        p_mem = prev.get('memory_percent') or 0
        if c_mem - p_mem > 5:
            events.append({'time': t, 'timestamp': ts, 'type': 'memory_growth',
                'detail': f'Memory grew {p_mem:.0f}% -> {c_mem:.0f}%',
                'severity': 'medium'})

        # Process spawn (50 se zyada ek saath)
        c_proc = curr.get('total_processes') or 0
        p_proc = prev.get('total_processes') or 0
        if c_proc - p_proc > 50:
            events.append({'time': t, 'timestamp': ts, 'type': 'process_explosion',
                'detail': f'Processes +{c_proc-p_proc} ({p_proc} -> {c_proc})',
                'severity': 'high'})

        # Zombie buildup
        zombie = curr.get('zombie_processes') or 0
        if zombie > 5:
            events.append({'time': t, 'timestamp': ts, 'type': 'zombie_buildup',
                'detail': f'{zombie} zombie processes detected',
                'severity': 'medium'})

        # Disk I/O storm
        disk = curr.get('disk_read') or 0
        if disk > 100:
            events.append({'time': t, 'timestamp': ts, 'type': 'io_storm',
                'detail': f'Disk read at {disk:.1f} MB/s',
                'severity': 'high'})

        # Swap spike (5% se zyada jump)
        c_swap = curr.get('swap_percent') or 0
        p_swap = prev.get('swap_percent') or 0
        if c_swap - p_swap > 5:
            events.append({'time': t, 'timestamp': ts, 'type': 'swap_spike',
                'detail': f'Swap usage jumped {p_swap:.0f}% -> {c_swap:.0f}%',
                'severity': 'high' if c_swap > 80 else 'medium'})

    return events

# Builds a chain of related events
def build_event_chain(events: list[dict]) -> list[dict]:
    if not events:
        return []

    sorted_events = sorted(events, key=lambda e: e.get('timestamp', 0))
    chain = []
    last_seen = {}

    for e in sorted_events:
        key = e['type']
        ts = e.get('timestamp', 0)
        if key not in last_seen or ts - last_seen[key] >= 5:
            chain.append(e)
            last_seen[key] = ts

    return chain

# Formats the event chain into a human-readable string
def format_chain_text(chain: list[dict]) -> str:
    if not chain:
        return "No significant events detected in this window."

    lines = []
    for i, e in enumerate(chain):
        arrow = "\n      ↓\n" if i < len(chain) - 1 else ""
        lines.append(f"[{e['time']}] {e['detail']}{arrow}")
    return "\n".join(lines)