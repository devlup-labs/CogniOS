"""Optimization policy mappings for confirmed workload states."""

POLICIES = {
    "COMPILATION": {
        "workload": "COMPILATION",
        "target_bucket_nice": -10,
        "secondary_bucket_nice": -3,
        "background_nice": +7,
        "io_priority": "high",
        "affinity_pin": True,
        "description": "Protect active build tools (nice -10) and deprioritize background tasks (nice +7)",
        "rationale": "High CPU utilization by compiler threads requires low latency scheduling and uninterrupted core allocation.",
    },
    "GAMING": {
        "workload": "GAMING",
        "target_bucket_nice": -10,
        "secondary_bucket_nice": 0,
        "background_nice": +7,
        "io_priority": "high",
        "affinity_pin": True,
        "description": "Prioritize gaming binaries and depress background resource contention",
        "rationale": "Real-time rendering requires maximum CPU frequency and minimal thread switching delay.",
    },
    "CODING": {
        "workload": "CODING",
        "target_bucket_nice": -5,
        "secondary_bucket_nice": 0,
        "background_nice": +3,
        "io_priority": "normal",
        "affinity_pin": False,
        "description": "Prioritize IDE responsiveness (nice -5) and smooth UI interaction",
        "rationale": "Prevents editor lag during indexing or language server evaluation.",
    },
    "VIDEO_CALL": {
        "workload": "VIDEO_CALL",
        "target_bucket_nice": -5,
        "secondary_bucket_nice": 0,
        "background_nice": +5,
        "io_priority": "high",
        "affinity_pin": False,
        "description": "Prioritize audio/video conferencing processes (nice -5)",
        "rationale": "Audio buffer underruns cause noticeable voice glitches during video calls.",
    },
    "BROWSING": {
        "workload": "BROWSING",
        "target_bucket_nice": 0,
        "secondary_bucket_nice": 0,
        "background_nice": +2,
        "io_priority": "normal",
        "affinity_pin": False,
        "description": "Balanced scheduling for web browser process trees",
        "rationale": "Ensures active tab responsiveness while preventing idle tabs from hogging resources.",
    },
    "MEDIA_PROCESSING": {
        "workload": "MEDIA_PROCESSING",
        "target_bucket_nice": -8,
        "secondary_bucket_nice": 0,
        "background_nice": +5,
        "io_priority": "high",
        "affinity_pin": True,
        "description": "Prioritize video encoding/rendering threads (nice -8)",
        "rationale": "Heavy CPU/IO media encoding benefits from dedicated cores and higher queue priority.",
    },
    "IDLE": {
        "workload": "IDLE",
        "target_bucket_nice": 0,
        "secondary_bucket_nice": 0,
        "background_nice": 0,
        "io_priority": "normal",
        "affinity_pin": False,
        "description": "System idle state — restore standard process priorities",
        "rationale": "No active workload contention detected.",
    },
    "UNKNOWN": {
        "workload": "UNKNOWN",
        "target_bucket_nice": 0,
        "secondary_bucket_nice": 0,
        "background_nice": 0,
        "io_priority": "normal",
        "affinity_pin": False,
        "description": "Observe-only mode — no aggressive priority shifts applied",
        "rationale": "Unmapped workload process; observing to prevent unsafe optimization.",
    },
}


def get_policy(workload: str) -> dict:
    """Returns the optimization policy for a given workload category."""
    if not workload or not isinstance(workload, str):
        return POLICIES["UNKNOWN"]
    
    return POLICIES.get(workload.strip().upper(), POLICIES["UNKNOWN"])


if __name__ == "__main__":
    pol = get_policy("COMPILATION")
    assert pol["target_bucket_nice"] == -10
    assert get_policy("NON_EXISTENT")["workload"] == "UNKNOWN"
    print(f"[✔] policy module tests passed successfully. Policy: {pol['description']}")
