import os
import json
import time
import hashlib
import sqlite3
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from os_doctor.alerts_db import create_connection, ensure_wal_mode, init_alerts_db
from config import ALERTS_DB_PATH, ALERTS_TABLE_NAME

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEMMA_API_KEY = (
    os.environ.get("GEMMA_API_KEY")
    or os.environ.get("GEMINI_API_KEY")
    or os.environ.get("gem_api_key")
)
GEMMA_MODEL = os.environ.get("GEMMA_MODEL", "gemma-4-26b-a4b-it")

REQUEST_TIMEOUT_MS = 15_000        # fail fast rather than block the daemon loop
POLL_INTERVAL_S = 10
TOP_N_METRICS = 4                  # extra deviant metrics given to Gemma for context
COOLDOWN_SECONDS = 300             # skip re-calling the API for a near-identical anomaly

DIAGNOSES_TABLE_NAME = "diagnoses"

SYSTEM_PROMPT = """You are OSDoctor, a systems reliability assistant. You \
will be given the single worst-offending process (name, pid, the metric \
that flagged it, and its exact value), plus a few other deviant system \
metrics for context.

Respond with ONLY a JSON object, no markdown fences, no commentary, in \
exactly this shape:
{
  "cause": "<one sentence stating what happened, using the EXACT numbers given to you>",
  "suggested_action": "<one concrete, actionable step>"
}

Do NOT invent numbers not given to you. Do NOT include severity or \
confidence — those are computed separately. If no single process stands \
out, base "cause" on the system-level metrics instead and say so plainly.
"""


# ---------------------------------------------------------------------------
# Process <-> metric correlation (unchanged from the Ollama version)
# ---------------------------------------------------------------------------

def build_process_table(metadata_row: dict, raw_row: dict) -> list:
    """
    metadata_row: {"cpu_1_pid": ..., "cpu_1_name": ..., "ram_2_status": ..., ...}
    raw_row:      {"cpu_1_cpu_peak": 91.2, "ram_2_peak": 512.0, ...}

    Both are flat dicts keyed by the same slot prefix (cpu_1, cpu_2, ...,
    ram_1, ram_2, ...). This re-groups them per slot AND attaches the real
    metric value for that slot, so each process record is self-contained:
    name + pid + the number that made it stand out.
    """
    slots = {}
    for key, value in metadata_row.items():
        parts = key.split("_")
        if len(parts) < 3:
            continue
        prefix, idx, field = parts[0], parts[1], "_".join(parts[2:])
        slot_key = f"{prefix}_{idx}"
        slots.setdefault(slot_key, {"slot": slot_key, "kind": prefix})[field] = value

    for slot_key, fields in slots.items():
        prefix, idx = slot_key.split("_")
        if prefix == "cpu":
            fields["metric_label"] = "CPU peak %"
            fields["metric_value"] = raw_row.get(f"cpu_{idx}_cpu_peak")
            fields["metric_gradient"] = raw_row.get(f"cpu_{idx}_cpu_peak_gradient")
        elif prefix == "ram":
            fields["metric_label"] = "RAM peak (MB)"
            fields["metric_value"] = raw_row.get(f"ram_{idx}_peak")
            fields["metric_gradient"] = raw_row.get(f"ram_{idx}_peak_gradient")
            fields["open_fds"] = raw_row.get(f"ram_{idx}_open_fds")

    return list(slots.values())


def get_top_process(process_table: list) -> Optional[dict]:
    """
    Picks the single worst offender by metric_value, skipping empty slots
    (name is blank/0 when fewer than 5 processes were captured that tick).
    Returns None if nothing usable was found — caller falls back to
    system-level metrics only.
    """
    candidates = []
    for record in process_table:
        name = record.get("name")
        if name in (None, "", 0, 0.0):
            continue
        try:
            value = float(record.get("metric_value"))
        except (TypeError, ValueError):
            continue
        candidates.append((value, record))

    if not candidates:
        return None

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


def get_top_system_metrics(raw_row: dict, scaled_row: dict, top_n: int = TOP_N_METRICS) -> list:
    """
    Ranks by |scaled value| (comparable across differently-scaled metrics),
    returns the RAW value for readability.
    """
    numeric_items = []
    for name, scaled_value in scaled_row.items():
        try:
            scaled_f = float(scaled_value)
            raw_f = float(raw_row.get(name))
        except (TypeError, ValueError):
            continue
        numeric_items.append((name, raw_f, scaled_f))

    numeric_items.sort(key=lambda triple: abs(triple[2]), reverse=True)
    return numeric_items[:top_n]


# ---------------------------------------------------------------------------
# Deterministic severity / confidence (unchanged — not left to the LLM)
# ---------------------------------------------------------------------------

def determine_issue_label(top_process: Optional[dict], top_metrics: list) -> str:
    """
    Short human-readable label for what KIND of anomaly this is — the
    "Detected Issue" line on the report card. Derived from whichever
    signal is strongest, same rule-based reasoning as severity: this
    needs to be consistent every time, not left to the LLM to phrase
    differently on each call.
    """
    if top_process and top_process.get("kind") == "cpu":
        return "High CPU utilization"
    if top_process and top_process.get("kind") == "ram":
        return "High memory utilization"

    # No single process stood out — fall back to whichever system metric
    # deviated most (top_metrics is already sorted by |deviation|).
    if top_metrics:
        worst_name = top_metrics[0][0]
        if "swap" in worst_name:
            return "Memory pressure (high swap usage)"
        if "disk" in worst_name:
            return "High disk I/O"
        if "net" in worst_name:
            return "Network anomaly"
        if "cpu" in worst_name:
            return "High CPU utilization"
        if "memory" in worst_name:
            return "High memory utilization"
        if "load_avg" in worst_name or "ctx_switches" in worst_name:
            return "Scheduler congestion"

    return "Unclassified anomaly"


def compute_severity_and_confidence(anomaly_score: Optional[float], top_process: Optional[dict]) -> tuple:
    """
    Rule-based on purpose: thresholds should fire the same way every time,
    which an LLM can't reliably guarantee. Tune these to your environment.
    """
    cpu_value = None
    if top_process and top_process.get("kind") == "cpu":
        try:
            cpu_value = float(top_process.get("metric_value"))
        except (TypeError, ValueError):
            cpu_value = None

    if cpu_value is not None and cpu_value >= 85:
        severity = "High"
    elif cpu_value is not None and cpu_value >= 60:
        severity = "Medium"
    elif anomaly_score is not None and anomaly_score <= -0.15:
        severity = "High"
    elif anomaly_score is not None and anomaly_score <= -0.05:
        severity = "Medium"
    else:
        severity = "Low"

    if anomaly_score is not None:
        confidence = round(min(99.0, max(50.0, abs(anomaly_score) * 400)), 1)
    else:
        confidence = 60.0

    return severity, confidence


# ---------------------------------------------------------------------------
# Cooldown / deduplication cache
# ---------------------------------------------------------------------------
# In-memory only — {fingerprint: (timestamp, llm_fields)}. Caches the actual
# explanation text too, not just the timestamp, so a cooldown "skip" reuses
# the real cause/suggested_action from the last live call instead of
# printing a misleading "no output" placeholder.
_recent_calls: Dict[str, tuple] = {}


def _fingerprint(top_process: Optional[dict], anomaly_score: Optional[float]) -> str:
    """Groups anomalies by offending process name + rounded score, so minor
    noise between ticks doesn't count as a brand-new anomaly."""
    name = top_process.get("name") if top_process else "system"
    rounded_score = round((anomaly_score or 0.0), 1)
    raw = f"{name}:{rounded_score}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_cached_explanation(fingerprint: str) -> Optional[dict]:
    """Returns the cached llm_fields dict if still within cooldown, else None."""
    entry = _recent_calls.get(fingerprint)
    if entry is None:
        return None
    cached_at, llm_fields = entry
    if time.time() - cached_at > COOLDOWN_SECONDS:
        return None
    return llm_fields


def _store_explanation(fingerprint: str, llm_fields: dict) -> None:
    _recent_calls[fingerprint] = (time.time(), llm_fields)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_prompt(top_process: Optional[dict], top_metrics: list) -> str:
    if top_process:
        process_block = (
            f"  name={top_process.get('name')} pid={top_process.get('pid')} "
            f"ppid={top_process.get('ppid')} status={top_process.get('status')}\n"
            f"  {top_process.get('metric_label')}: {float(top_process.get('metric_value')):.2f}"
        )
    else:
        process_block = "  (no single process stood out this tick)"

    metric_lines = "\n".join(
        f"  - {name}: {raw_value:.2f} (deviation from baseline: {scaled_value:+.2f})"
        for name, raw_value, scaled_value in top_metrics
    ) or "  (no additional metrics available)"

    return f"""ANOMALY DETECTED

Worst-offending process:
{process_block}

Other deviant system metrics:
{metric_lines}

Respond with the JSON object described in your instructions."""


# ---------------------------------------------------------------------------
# Gemma call (cloud, via Gemini API) — swapped from Ollama
# ---------------------------------------------------------------------------

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

def call_gemma(user_prompt: str, model: str = GEMMA_MODEL, retries: int = 2) -> Optional[str]:
    """
    Calls local Ollama (gemma2:2b) first, falling back to hosted Gemini API if needed.
    """
    # 1. Try local Ollama server (no API key required)
    try:
        payload = {
            "model": "gemma2:2b",
            "system": SYSTEM_PROMPT,
            "prompt": user_prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        resp = requests.post(OLLAMA_URL, json=payload, timeout=15)
        if resp.status_code == 200:
            text = resp.json().get("response", "")
            if text:
                return text
    except Exception:
        pass

    # 2. Fallback to Gemini API if GEMMA_API_KEY is configured
    if not GEMMA_API_KEY:
        print("[llm_layer] Local Ollama call failed and GEMMA_API_KEY is not set.")
        return None

    last_error = None
    for attempt in range(retries + 1):
        try:
            client = genai.Client(
                api_key=GEMMA_API_KEY,
                http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
            )
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.2,
                    max_output_tokens=200,
                ),
            )
            return getattr(response, "text", None)
        except Exception as e:
            last_error = e
            time.sleep(1.5 * (attempt + 1))

    print(f"[llm_layer] Gemma call failed after {retries + 1} attempts: {last_error}")
    return None


def parse_llm_response(raw_text: Optional[str]) -> dict:
    if not raw_text or not raw_text.strip():
        return {"cause": "Anomaly detected, but the explanation model returned no output.",
                "suggested_action": "Check your GEMMA_API_KEY and network connection."}

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).replace("json", "", 1)

    try:
        parsed = json.loads(cleaned)
        parsed.setdefault("cause", "unknown")
        parsed.setdefault("suggested_action", "")
        return parsed
    except json.JSONDecodeError:
        return {"cause": cleaned[:500], "suggested_action": ""}


# ---------------------------------------------------------------------------
# Storage (unchanged)
# ---------------------------------------------------------------------------

def init_diagnoses_table(conn):
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS {DIAGNOSES_TABLE_NAME} (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id          INTEGER NOT NULL,
            issue             TEXT,
            cause             TEXT,
            severity          TEXT,
            suggested_action  TEXT,
            confidence        REAL,
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (alert_id) REFERENCES {ALERTS_TABLE_NAME}(id)
        )
    ''')
    conn.commit()


def write_diagnosis(conn, alert_id, diagnosis):
    conn.execute(
        f"""INSERT INTO {DIAGNOSES_TABLE_NAME}
            (alert_id, issue, cause, severity, suggested_action, confidence)
            VALUES (?, ?, ?, ?, ?, ?)""",
        (
            alert_id,
            diagnosis.get("issue"),
            diagnosis.get("cause"),
            diagnosis.get("severity"),
            diagnosis.get("suggested_action"),
            diagnosis.get("confidence"),
        ),
    )
    conn.commit()


def fetch_undiagnosed_alerts(conn):
    cursor = conn.execute(f"""
        SELECT a.id, a.metadata, a.data
        FROM {ALERTS_TABLE_NAME} a
        LEFT JOIN {DIAGNOSES_TABLE_NAME} d ON d.alert_id = a.id
        WHERE d.id IS NULL
        ORDER BY a.id ASC
    """)
    return cursor.fetchall()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def process_alert(conn, alert_id, metadata_json, data_json):
    try:
        metadata_row = json.loads(metadata_json)
        data_payload = json.loads(data_json)
        raw_row = data_payload["raw"]
        scaled_row = data_payload["scaled"]
        anomaly_score = data_payload.get("anomaly_score")
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[llm_layer] alert {alert_id}: malformed row, skipping ({e})")
        return

    process_table = build_process_table(metadata_row, raw_row)
    top_process = get_top_process(process_table)
    top_metrics = get_top_system_metrics(raw_row, scaled_row)

    severity, confidence = compute_severity_and_confidence(anomaly_score, top_process)
    issue = determine_issue_label(top_process, top_metrics)

    fingerprint = _fingerprint(top_process, anomaly_score)
    cached_fields = _get_cached_explanation(fingerprint)

    if cached_fields is not None:
        print(f"[llm_layer] alert {alert_id}: reusing recent explanation (cooldown active)")
        llm_fields = cached_fields
    else:
        prompt = build_prompt(top_process, top_metrics)
        raw_response = call_gemma(prompt)
        llm_fields = parse_llm_response(raw_response)
        if raw_response is not None:
            # Only cache genuine successes — a failed call shouldn't be
            # "remembered" as the explanation for the whole cooldown window;
            # let the next alert retry instead.
            _store_explanation(fingerprint, llm_fields)

    diagnosis = {
        "issue": issue,
        "cause": llm_fields.get("cause"),
        "severity": severity,
        "suggested_action": llm_fields.get("suggested_action"),
        "confidence": confidence,
    }

    write_diagnosis(conn, alert_id, diagnosis)
    print(f"[llm_layer] alert {alert_id} -> {issue} | {severity} ({confidence}%): {diagnosis['cause']}")


def run_llm_daemon(poll_interval=POLL_INTERVAL_S):
    ensure_wal_mode(ALERTS_DB_PATH)
    conn = create_connection(ALERTS_DB_PATH)
    init_alerts_db(conn)
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
