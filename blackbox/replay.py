"""Telemetry replay utilities."""

import time
from recorder import get_window_rows
from correlation import telemetry_to_events, build_event_chain, format_chain_text

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

# Generate a context dictionary for LLM input based on the replay result and anomaly type.
def generate_llm_context(replay_result: dict,
                         anomaly_type: str = "unknown") -> dict:
    chain      = replay_result.get('chain', [])
    top_events = [f"{e['time']}: {e['detail']}" for e in chain[:5]]

    # Create a prompt for the LLM that summarizes the anomaly and recent events.
    prompt = (
        f"A system experienced a '{anomaly_type}' event. "
        f"In the 30 minutes before the event, the following occurred: "
        f"{'; '.join(top_events) if top_events else 'No significant events detected'}. "
        f"Explain in simple language: "
        f"1. Root cause  2. Severity  3. Suggested action."
    )
    return {
        "anomaly_type": anomaly_type,
        "total_events": len(chain),
        "timeline":     top_events,
        "prompt":       prompt,
    }