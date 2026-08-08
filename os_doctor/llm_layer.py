import json
import time
import sqlite3
import requests

from os_doctor.alerts_db import create_connection, ensure_wal_mode, init_alerts_db
from os_doctor.i_forest_train import expected_columns
from config import ALERTS_DB_PATH, ALERTS_TABLE_NAME


# Config
#http://localhost:11434

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma2:2b"          # swap to "gemma2:2b" on constrained hardware
REQUEST_TIMEOUT_S = 60
POLL_INTERVAL_S = 10
TOP_N_FEATURES = 6                # how many contributing features to hand the LLM

DIAGNOSES_TABLE_NAME = "diagnoses"

# Feature names as they appear in the alert `data` payload — same order
# i_forest_train.py trains on, minus the columns that never reach the model.
FEATURE_NAMES = [
    c for c in expected_columns if c not in ("id", "timestamp")
]

SYSTEM_PROMPT = """You are OSDoctor, a senior systems reliability engineer \
diagnosing anomalies detected by an Isolation Forest model monitoring CPU, \
memory, disk, network, and process-level telemetry.

You will be given:
1. The top statistically deviant metrics, in their real units (percent, \
MB/s, count, etc.), each annotated with how far it deviates from the \
learned normal baseline (positive = above normal, negative = below).
2. Process metadata (pid, ppid, name, status) for the processes that were \
consuming the most CPU/RAM at the time of the anomaly.

Respond with ONLY a JSON object, no markdown fences, no commentary, in \
exactly this shape:
{
  "root_cause": "<one sentence, most likely cause>",
  "explanation": "<2-4 sentences a non-expert sysadmin can follow>",
  "recommendations": ["<action 1>", "<action 2>", "..."],
  "severity": "low" | "medium" | "high" | "critical"
}

If the evidence is ambiguous, say so honestly in "explanation" rather than \
inventing a confident cause. Keep recommendations concrete and actionable \
(e.g. "restart process X (pid 1234)", not "monitor the system").
"""

# Feature attribution


def get_top_contributing_features(raw_row, scaled_row, top_n=TOP_N_FEATURES):
    """
    raw_row:    dict of {feature_name: raw_value}    — actual metric units.
    scaled_row: dict of {feature_name: scaled_value} — roughly zero-centered.

    Ranks by |scaled_value| (comparable across features with different
    units/ranges — you can't rank a CPU percent against a disk MB/s number
    directly, but their scaled versions are comparable), then returns the
    corresponding RAW value for each, since raw is what's actually
    human-readable ("94.2%" means something; "2.31" doesn't).

    Returns a list of (feature_name, raw_value, scaled_value).
    """
    numeric_items = []
    for name, scaled_value in scaled_row.items():
        try:
            scaled_f = float(scaled_value)
            raw_f = float(raw_row.get(name))
        except (TypeError, ValueError):
            continue  # skip anything non-numeric that slipped through
        numeric_items.append((name, raw_f, scaled_f))

    numeric_items.sort(key=lambda triple: abs(triple[2]), reverse=True)
    return numeric_items[:top_n]


def extract_process_metadata(metadata_row, top_n=3):
    """
    metadata_row: dict from the alert's 'metadata' JSON column, containing
    flattened cpu_N_/ram_N_ pid/ppid/name/status fields (see
    featuring.build_unified_vector). Groups them back into per-slot
    process records and returns the first `top_n`.
    """
    slots = {}
    for key, value in metadata_row.items():
        # keys look like "cpu_1_pid", "ram_3_name", etc.
        parts = key.split("_")
        if len(parts) < 3:
            continue
        prefix, idx, field = parts[0], parts[1], "_".join(parts[2:])
        slot_key = f"{prefix}_{idx}"
        slots.setdefault(slot_key, {})[field] = value

    processes = []
    for slot_key, fields in slots.items():
        if fields.get("name") in (None, "", 0, 0.0):
            continue
        processes.append({
            "slot": slot_key,
            "pid": fields.get("pid"),
            "ppid": fields.get("ppid"),
            "name": fields.get("name"),
            "status": fields.get("status"),
        })

    return processes[:top_n]



# Prompt construction


def build_prompt(metadata_row, raw_row, scaled_row):
    top_features = get_top_contributing_features(raw_row, scaled_row)
    processes = extract_process_metadata(metadata_row)

    # Show BOTH: raw value so the LLM can talk in real units, scaled
    # deviation so it understands how far from baseline that really is.
    feature_lines = "\n".join(
        f"  - {name}: {raw_value:.2f}  (deviation from baseline: {scaled_value:+.2f})"
        for name, raw_value, scaled_value in top_features
    ) or "  (no numeric features available)"

    if processes:
        process_lines = "\n".join(
            f"  - pid={p['pid']} ppid={p['ppid']} name={p['name']} status={p['status']}"
            for p in processes
        )
    else:
        process_lines = "  (no process metadata available)"

    user_prompt = f"""ANOMALY DETECTED

Top deviant metrics (actual values, sorted by how far from baseline):
{feature_lines}

Relevant processes at time of anomaly:
{process_lines}

Diagnose the likely root cause and respond with the JSON object described
in your instructions."""

    return user_prompt


# Gemma call (Ollama)


def call_gemma(user_prompt, model=MODEL_NAME, retries=2):
    """
    Calls a locally running Ollama server. Requires `ollama serve` running
    and the model pulled beforehand (`ollama pull gemma2:9b`).
    Returns the raw text response, or None on failure.
    """
    payload = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": user_prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }

    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT_S)
            resp.raise_for_status()
            return resp.json().get("response", "")
        except Exception as e:
            last_error = e
            time.sleep(1.5 * (attempt + 1))

    print(f"[llm_layer] Gemma call failed after {retries + 1} attempts: {last_error}")
    return None


def parse_llm_response(raw_text):
    """
    Best-effort JSON parse. Gemma sometimes wraps output in ```json fences
    even when told not to — strip those before parsing. Falls back to a
    structured 'unparsed' record so nothing is silently lost.
    """
    if not raw_text:
        return _fallback_diagnosis("Empty response from model.")

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).replace("json", "", 1)

    try:
        parsed = json.loads(cleaned)
        parsed.setdefault("root_cause", "unknown")
        parsed.setdefault("explanation", "")
        parsed.setdefault("recommendations", [])
        parsed.setdefault("severity", "medium")
        return parsed
    except json.JSONDecodeError:
        return _fallback_diagnosis(raw_text)


def _fallback_diagnosis(raw_text):
    return {
        "root_cause": "unparsed",
        "explanation": raw_text[:1000],
        "recommendations": [],
        "severity": "unknown",
    }

# Storage

def init_diagnoses_table(conn):
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS {DIAGNOSES_TABLE_NAME} (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id       INTEGER NOT NULL,
            root_cause     TEXT,
            explanation    TEXT,
            recommendations TEXT,
            severity       TEXT,
            created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (alert_id) REFERENCES {ALERTS_TABLE_NAME}(id)
        )
    ''')
    conn.commit()


def write_diagnosis(conn, alert_id, diagnosis):
    conn.execute(
        f"""INSERT INTO {DIAGNOSES_TABLE_NAME}
            (alert_id, root_cause, explanation, recommendations, severity)
            VALUES (?, ?, ?, ?, ?)""",
        (
            alert_id,
            diagnosis.get("root_cause"),
            diagnosis.get("explanation"),
            json.dumps(diagnosis.get("recommendations", []), separators=(',', ':')),
            diagnosis.get("severity"),
        ),
    )
    conn.commit()


def fetch_undiagnosed_alerts(conn):
    """
    Alerts that don't yet have a matching row in `diagnoses`. Cheap
    LEFT JOIN / IS NULL rather than tracking a separate cursor, so it's
    safe to run even if the daemon restarts.
    """
    cursor = conn.execute(f"""
        SELECT a.id, a.metadata, a.data
        FROM {ALERTS_TABLE_NAME} a
        LEFT JOIN {DIAGNOSES_TABLE_NAME} d ON d.alert_id = a.id
        WHERE d.id IS NULL
        ORDER BY a.id ASC
    """)
    return cursor.fetchall()



# Orchestration

def process_alert(conn, alert_id, metadata_json, data_json):
    try:
        metadata_row = json.loads(metadata_json)
        data_payload = json.loads(data_json)
        # i_forest_predict.py now writes {"raw": {...}, "scaled": {...}}.
        raw_row = data_payload["raw"]
        scaled_row = data_payload["scaled"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[llm_layer] alert {alert_id}: malformed row, skipping ({e})")
        return

    prompt = build_prompt(metadata_row, raw_row, scaled_row)
    raw_response = call_gemma(prompt)
    diagnosis = parse_llm_response(raw_response)

    write_diagnosis(conn, alert_id, diagnosis)
    print(f"[llm_layer] alert {alert_id} -> {diagnosis['severity']}: {diagnosis['root_cause']}")


def run_llm_daemon(poll_interval=POLL_INTERVAL_S):
    ensure_wal_mode(ALERTS_DB_PATH)
    conn = create_connection(ALERTS_DB_PATH)
    init_alerts_db(conn)      # CHANGED: guarantees `alerts` exists before we JOIN against it
    init_diagnoses_table(conn)

    print("[llm_layer] Listening for new alerts...")
    try:
        while True:
            try:
                for alert_id, metadata_json, data_json in fetch_undiagnosed_alerts(conn):
                    process_alert(conn, alert_id, metadata_json, data_json)
            except sqlite3.Error as e:
                print(f"[llm_layer] DB error: {e}")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[llm_layer] Stopped.")
    finally:
        conn.close()


if __name__ == "__main__":
    run_llm_daemon()