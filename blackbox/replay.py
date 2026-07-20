"""Telemetry replay utilities."""

import time
from blackbox.recorder import get_window_rows
from blackbox.correlation import telemetry_to_events, build_event_chain, format_chain_text

# replay the telemetry data in the given time window and return a structured summary of events.
def replay(conn, crash_time: float = None,
           window_minutes: int = 30) -> dict:
    # If crash_time is not provided, use the current time as the crash time.
    if crash_time is None:
        crash_time = time.time()
    
    start_time = crash_time - (window_minutes * 60)
    rows = get_window_rows(conn, start_time, crash_time)

    # Convert the telemetry rows into structured events and build an event chain.
    events = telemetry_to_events(rows)
    chain  = build_event_chain(events)

    return {
        'crash_time':    crash_time,
        'window_start':  start_time,
        'total_rows':    len(rows),
        'events':        events,
        'chain':         chain,
        'timeline_text': format_chain_text(chain),
    }


