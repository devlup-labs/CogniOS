"""
Groq LLM diagnosis layer for OS Doctor.

Calculates vector differences against workload baselines,
selects the best-fit baseline, queries Groq for the diagnosis,
caches repeated issues to save API calls, and logs the report.
"""

import json
import time
import os
import sqlite3
import joblib
from datetime import datetime

import requests

from os_doctor.alerts_db import (
    create_connection,
    ensure_wal_mode,
    init_alerts_db,
)
from os_doctor.featuring import ML_FEATURES
from config import ALERTS_DB_PATH, ALERTS_TABLE_NAME, GROQ_API_KEY, GROQ_MODEL, WORKLOADS

DIAGNOSES_TABLE_NAME = "diagnoses"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT_S = 30
MAX_RETRIES = 2
POLL_INTERVAL_S = 10
COOLDOWN_S = 60  # Minimum seconds between alerts of the same issue

# ---------------------------------------------------------------------------
# Feature metadata
# ---------------------------------------------------------------------------

FEATURE_META: dict[str, tuple[str, str]] = {
    "nr_running_per_core":             ("CPU",           "Processes waiting per CPU core"),
    "involuntary_context_switch_rate": ("CPU",           "Involuntary context switches/s"),
    "uninterruptible_d_state_count":   ("IO",            "Processes stuck in D-state (I/O wait)"),
    "cpu_usage_percent":               ("CPU",           "CPU usage (%)"),
    "cpu_usage_percent_gradient":      ("CPU",           "CPU usage rate of change (%/s)"),
    "cpu_iowait_time":                 ("IO",            "CPU time waiting for disk I/O (%)"),
    "cpu_psi_some_avg10":              ("CPU",           "CPU pressure stall — some (10s avg %)"),
    "memory_percent":                  ("MEMORY",        "RAM usage (%)"),
    "memory_percent_gradient":         ("MEMORY",        "RAM usage rate of change (%/s)"),
    "memory_psi_full_avg10":           ("MEMORY",        "Memory pressure stall — full (10s avg %)"),
    "direct_reclaim_rate":             ("MEMORY",        "Direct memory reclaim rate (pages/s)"),
    "major_page_fault_rate":           ("MEMORY",        "Major page faults/s (disk paging)"),
    "swap_out_rate":                   ("MEMORY",        "Swap write rate (pages/s)"),
    "disk_read_mb_s":                  ("IO",            "Disk read throughput (MB/s)"),
    "disk_write_mb_s":                 ("IO",            "Disk write throughput (MB/s)"),
    "io_latency":                      ("IO",            "Disk I/O latency"),
    "io_psi_some_avg10":               ("IO",            "I/O pressure stall — some (10s avg %)"),
    "io_psi_full_avg10":               ("IO",            "I/O pressure stall — full (10s avg %)"),
    "open_fds_gradient":               ("RESOURCE_LEAK", "Open file descriptor growth rate (fds/s)"),
    "thread_count_gradient":           ("RESOURCE_LEAK", "Thread count growth rate (threads/s)"),
    "zombie_process_count":            ("RESOURCE_LEAK", "Zombie process count"),
    "cpu_frequency_deviation":         ("THERMAL",       "CPU frequency deviation from baseline (MHz)"),
    "thermal_throttling_events":       ("THERMAL",       "Thermal throttling events"),
    "tcp_retrans_rate":                ("NETWORK",       "TCP retransmission rate (segments/s)"),
}

# ---------------------------------------------------------------------------
# Database Helpers
# ---------------------------------------------------------------------------

def init_diagnoses_table(conn: sqlite3.Connection) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {DIAGNOSES_TABLE_NAME} (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id           INTEGER NOT NULL UNIQUE,
            workload           TEXT,
            issue_key          TEXT,
            severity           TEXT,
            confidence_json    TEXT,
            root_cause         TEXT,
            explanation        TEXT,
            recommendations    TEXT,
            top_deviations     TEXT,
            top_procs          TEXT,
            created_at         TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (alert_id) REFERENCES {ALERTS_TABLE_NAME}(id)
        )
    """)
    conn.commit()


def write_diagnosis(conn: sqlite3.Connection, alert_id: int, diagnosis: dict) -> None:
    conn.execute(
        f"""
        INSERT OR IGNORE INTO {DIAGNOSES_TABLE_NAME}
            (alert_id, workload, issue_key, severity, confidence_json, root_cause,
             explanation, recommendations, top_deviations, top_procs)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            alert_id,
            diagnosis.get("workload"),
            diagnosis.get("issue_key", "unknown"),
            diagnosis.get("severity", "unknown"),
            json.dumps(diagnosis.get("confidence", {}),       separators=(",", ":")),
            diagnosis.get("root_cause", ""),
            diagnosis.get("explanation", ""),
            json.dumps(diagnosis.get("recommendations", []),  separators=(",", ":")),
            json.dumps(diagnosis.get("top_deviations", []),   separators=(",", ":")),
            json.dumps(diagnosis.get("top_procs", {}),        separators=(",", ":")),
        ),
    )
    conn.commit()


def fetch_undiagnosed_alerts(conn: sqlite3.Connection) -> list:
    cursor = conn.execute(f"""
        SELECT a.id, a.metadata, a.data
        FROM   {ALERTS_TABLE_NAME}  a
        LEFT JOIN {DIAGNOSES_TABLE_NAME} d ON d.alert_id = a.id
        WHERE  d.id IS NULL
        ORDER  BY a.id ASC
    """)
    return cursor.fetchall()

# ---------------------------------------------------------------------------
# Baseline loading & Hot reload
# ---------------------------------------------------------------------------

_BASELINES_CACHE = {}
_LAST_MTIMES = {}

def get_baselines() -> dict[int, dict]:
    """
    Loads or reloads scalers if they have been updated on disk.
    """
    global _BASELINES_CACHE, _LAST_MTIMES
    
    for wid, cfg in WORKLOADS.items():
        scaler_path = cfg["scaler_path"]
        model_path  = cfg["model_path"]

        if not os.path.exists(scaler_path) or not os.path.exists(model_path):
            continue

        try:
            mtime = max(os.path.getmtime(scaler_path), os.path.getmtime(model_path))
            
            # Skip if already loaded and mtime hasn't changed
            if wid in _BASELINES_CACHE and _LAST_MTIMES.get(wid) == mtime:
                continue
                
            scaler = joblib.load(scaler_path)
            model  = joblib.load(model_path)

            center = dict(zip(ML_FEATURES, scaler.center_.tolist()))
            scale  = dict(zip(ML_FEATURES, scaler.scale_.tolist()))
            
            # Filter out constant features from scaling (IQR < 1e-4) to prevent inf deviation
            for feat in scale:
                if scale[feat] < 1e-4:
                    scale[feat] = float('inf') # Effectively ignores this feature in deviation

            _BASELINES_CACHE[wid] = {
                "name":      cfg["name"],
                "center":    center,
                "scale":     scale,
                "threshold": float(model.threshold_),
            }
            _LAST_MTIMES[wid] = mtime
            print(f"[diagnosis] Loaded baseline for workload '{cfg['name']}'")
        except Exception as exc:
            print(f"[diagnosis] Could not load workload {cfg['name']}: {exc}")

    return _BASELINES_CACHE

# ---------------------------------------------------------------------------
# Engine Logic (Deviation, Top Processes, Best Baseline)
# ---------------------------------------------------------------------------

def compute_deviations(raw: dict, baseline: dict) -> list[dict]:
    results = []
    center = baseline["center"]
    scale  = baseline["scale"]

    for feat in ML_FEATURES:
        try:
            raw_val  = float(raw.get(feat, 0.0) or 0.0)
            center_v = float(center.get(feat, 0.0))
            scale_v  = float(scale.get(feat, 1.0))
        except (TypeError, ValueError):
            continue

        # If scale_v is inf, it was a constant feature; deviation is 0.
        if scale_v == float('inf'):
            dev = 0.0
        else:
            dev = abs(raw_val - center_v) / max(scale_v, 1e-9)
            
        direction = "above baseline" if raw_val >= center_v else "below baseline"
        cat, label = FEATURE_META.get(feat, ("OTHER", feat))
        
        results.append({
            "feature":   feat,
            "label":     label,
            "category":  cat,
            "raw_value": round(raw_val,  4),
            "baseline":  round(center_v, 4),
            "deviation": round(dev,      4),
            "direction": direction,
        })

    results.sort(key=lambda x: x["deviation"], reverse=True)
    return results


def select_best_baseline(raw: dict, baselines: dict) -> tuple[int, dict, float]:
    best_wid      : int   = -1
    best_baseline : dict  = {}
    best_mean_dev : float = float("inf")

    for wid, baseline in baselines.items():
        devs = compute_deviations(raw, baseline)
        if not devs:
            continue
        mean_dev = sum(d["deviation"] for d in devs) / len(devs)
        if mean_dev < best_mean_dev:
            best_mean_dev = mean_dev
            best_wid      = wid
            best_baseline = baseline

    return best_wid, best_baseline, round(best_mean_dev, 4)


def extract_top_processes(metadata: dict, n: int = 3) -> dict:
    procs = {"cpu": [], "ram": []}
    
    for prefix in ["cpu", "ram"]:
        for i in range(1, 6):
            name = metadata.get(f"{prefix}_{i}_name")
            if not name or str(name).strip().lower() in ("0", "0.0", "", "nan", "none"):
                continue

            entry: dict = {
                "name":   str(name),
                "pid":    metadata.get(f"{prefix}_{i}_pid"),
                "ppid":   metadata.get(f"{prefix}_{i}_ppid"),
                "status": metadata.get(f"{prefix}_{i}_status"),
            }
            if prefix == "cpu":
                entry["cpu_peak_%"] = metadata.get(f"cpu_{i}_cpu_peak")
            else:
                entry["ram_peak_MB"]  = metadata.get(f"ram_{i}_peak")
                entry["open_fds"]     = metadata.get(f"ram_{i}_open_fds")

            procs[prefix].append(entry)
            if len(procs[prefix]) == n:
                break
    return procs


def _severity(max_deviation: float) -> str:
    if max_deviation >= 5.0:   return "critical"
    if max_deviation >= 3.0:   return "high"
    if max_deviation >= 1.5:   return "medium"
    return "low"

# ---------------------------------------------------------------------------
# Caching Logic
# ---------------------------------------------------------------------------

_DIAGNOSIS_CACHE = {} # (workload, severity, primary_feature) -> {diagnosis_dict, last_alert_time}

def _get_cached_diagnosis(issue_key: str) -> dict | None:
    if issue_key in _DIAGNOSIS_CACHE:
        cached = _DIAGNOSIS_CACHE[issue_key]
        if time.time() - cached['last_time'] < COOLDOWN_S:
            # Silently throttle identical alerts within cooldown
            return "THROTTLED" 
        return cached['diagnosis']
    return None

def _cache_diagnosis(issue_key: str, diagnosis: dict) -> None:
    _DIAGNOSIS_CACHE[issue_key] = {
        'diagnosis': diagnosis,
        'last_time': time.time()
    }

# ---------------------------------------------------------------------------
# Prompt Builder & Groq Caller
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are OSDoctor, a senior systems reliability engineer.
The system detected an anomaly. You must explain why the system is slow.

You will receive:
1. The inferred workload type.
2. The top deviant metrics (scaled IQR deviation from the normal baseline).
3. The top CPU and RAM consuming processes.

Respond with ONLY a valid JSON object. No markdown. No commentary. Exactly this shape:
{
  "root_cause": "<one sentence — most likely cause>",
  "explanation": "<2-3 sentences a non-expert user can understand>",
  "recommendations": ["<action 1>", "<action 2>", "<action 3>"]
}

Focus recommendations on what the user can do right now. Do not invent a confident cause if ambiguous.
"""

def _build_prompt(
    workload_name: str,
    top_deviations: list[dict],
    top_procs: dict,
    anomaly_score: float,
) -> str:
    cpu_lines = []
    for p in top_procs["cpu"]:
        cpu_lines.append(f"  {p['name']}  (PID: {p['pid']}, CPU Peak: {p.get('cpu_peak_%', '?')}%)")
        
    ram_lines = []
    for p in top_procs["ram"]:
        ram_lines.append(f"  {p['name']}  (PID: {p['pid']}, RAM Peak: {p.get('ram_peak_MB', '?')} MB)")

    prompt = f"Workload: {workload_name}\nAnomaly score: {anomaly_score}\n\nTop 5 Deviant Metrics:\n"
    for feat in top_deviations[:5]:
        prompt += f"- {feat['label']} (Category: {feat['category']}): measured {feat['raw_value']}, deviation {feat['deviation']} IQR {feat['direction']}\n"

    prompt += "\nTop CPU Processes:\n" + ("\n".join(cpu_lines) if cpu_lines else "  (no data)")
    prompt += "\nTop RAM Processes:\n" + ("\n".join(ram_lines) if ram_lines else "  (no data)")
    prompt += "\n\nDiagnose the root cause. Return JSON only."
    return prompt


def _call_groq(prompt: str) -> dict | None:
    if not GROQ_API_KEY:
        print("[groq_diagnosis] GROQ_API_KEY is not set. Check .env file.")
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":    GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens":  512,
        "response_format": {"type": "json_object"}
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_S)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            return json.loads(content)
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"[groq_diagnosis] Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"[groq_diagnosis] HTTP error: {exc}")
                return None
        except Exception as exc:
            print(f"[groq_diagnosis] Attempt {attempt + 1} failed: {exc}")
            time.sleep(2 * (attempt + 1))

    print(f"[groq_diagnosis] All {MAX_RETRIES + 1} attempts failed.")
    return None


def _fallback_diagnosis(workload: str, top_deviations: list[dict], top_procs: dict) -> dict:
    feat = top_deviations[0]['label'] if top_deviations else 'unknown metric'
    return {
        "root_cause": f"{feat} deviated significantly during {workload}.",
        "explanation": "Groq LLM was unavailable, but telemetry indicates an anomaly driven by this metric.",
        "recommendations": ["Check Activity Monitor for high resource consumers."],
    }

# ---------------------------------------------------------------------------
# Report Formatting
# ---------------------------------------------------------------------------

def format_report(alert_id: int, diagnosis: dict) -> str:
    wl = diagnosis.get("workload", "unknown")
    sev = diagnosis.get("severity", "UNKNOWN").upper()
    conf = diagnosis.get("confidence", {})
    
    lines = [
        f"{'═' * 66}",
        f"  OS Doctor  ·  Alert #{alert_id}  ·  Workload: {wl}  ·  Severity: {sev}",
        f"{'═' * 66}",
        f"",
        f"  Confidence : {conf.get('combined', '?')}%  "
        f"(deviation signal: {conf.get('deviation_component', '?')}%)",
        f"  Top deviation : {conf.get('top_deviation_iqr', '?')} IQR  "
        f"(cap: {conf.get('deviation_cap_iqr', '?')} IQR = 100%)",
        f"",
    ]
    
    if diagnosis.get("baseline_corrected"):
        lines += [
            f"  ⚡ Baseline auto-corrected (Mean deviation {diagnosis.get('baseline_mean_dev_iqr', '?')} IQR)",
            f"",
        ]
        
    if diagnosis.get("cached"):
        lines += [
            f"  ⚡ Served from Cache (Repeated Issue)",
            f"",
        ]

    lines += [
        f"  Root cause",
        f"  {'─' * 60}",
        f"  {diagnosis.get('root_cause', '')}",
        f"",
        f"  What happened",
        f"  {'─' * 60}",
        f"  {diagnosis.get('explanation', '')}",
    ]

    # Top 3 deviated features
    lines += [
        f"",
        f"  Top 3 deviated features (vs {wl} baseline)",
        f"  {'─' * 60}",
        f"  {'Feature':<44} {'Measured':>10}  {'Baseline':>10}  {'Deviation (IQR)':>15}  Direction",
        f"  {'─' * 95}",
    ]
    for feat in diagnosis.get("top_deviations", [])[:3]:
        lines.append(
            f"  [{feat['category']:<13}]  "
            f"{feat['label']:<44} "
            f"{str(feat['raw_value']):>10}  "
            f"{str(feat['baseline']):>10}  "
            f"{feat['deviation']:>15.4f}  "
            f"{feat['direction']}"
        )

    # Top CPU processes
    procs = diagnosis.get("top_procs", {})
    cpu_procs = procs.get("cpu", [])
    lines += [f"", f"  Top CPU processes at anomaly time"]
    if cpu_procs:
        lines.append(f"  {'Name':<22} {'PID':>7}  {'PPID':>7}  {'Status':<12}  {'CPU peak':>10}")
        lines.append(f"  {'─' * 65}")
        for p in cpu_procs:
            lines.append(
                f"  {str(p['name']):<22} {str(p.get('pid','?')):>7}  {str(p.get('ppid','?')):>7}  "
                f"{str(p.get('status','?')):<12}  {str(p.get('cpu_peak_%','?')):>9}%"
            )
    else:
        lines.append(f"  (no data)")

    # Top RAM processes
    ram_procs = procs.get("ram", [])
    lines += [f"", f"  Top RAM processes at anomaly time"]
    if ram_procs:
        lines.append(f"  {'Name':<22} {'PID':>7}  {'PPID':>7}  {'Status':<12}  {'RAM peak (MB)':>14}  {'Open FDs':>9}")
        lines.append(f"  {'─' * 80}")
        for p in ram_procs:
            lines.append(
                f"  {str(p['name']):<22} {str(p.get('pid','?')):>7}  {str(p.get('ppid','?')):>7}  "
                f"{str(p.get('status','?')):<12}  {str(p.get('ram_peak_MB','?')):>14}  "
                f"{str(p.get('open_fds','?')):>9}"
            )
    else:
        lines.append(f"  (no data)")

    lines += [f"", f"  Recommendations", f"  {'─' * 60}"]
    for i, rec in enumerate(diagnosis.get("recommendations", []), 1):
        lines.append(f"  {i}. {rec}")

    lines.append(f"{'═' * 66}")
    return "\n".join(lines)


def log_report_to_file(report: str) -> None:
    """Logs the final report to a text file for frontend/dashboard usage."""
    log_file = os.path.join(os.path.dirname(ALERTS_DB_PATH), "os_doctor_diagnoses.log")
    try:
        with open(log_file, "a") as f:
            f.write(f"\n[{datetime.now().isoformat()}]\n")
            f.write(report)
            f.write("\n")
    except Exception as e:
        print(f"[groq_diagnosis] Failed to write log: {e}")

# ---------------------------------------------------------------------------
# Alert Processor
# ---------------------------------------------------------------------------

def process_alert(conn: sqlite3.Connection, alert_id: int, metadata_json: str, data_json: str) -> None:
    try:
        metadata = json.loads(metadata_json)
        data     = json.loads(data_json)
        raw      = data.get("raw", {})
        wid      = data.get("workload_id")
        score    = data.get("anomaly_score", 0.0)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"[groq_diagnosis] alert {alert_id}: malformed JSON, skipping ({exc})")
        return

    baselines = get_baselines()
    if not baselines:
        print(f"[groq_diagnosis] alert {alert_id}: no baselines loaded, skipping.")
        return

    # 1. Best-fit baseline
    best_wid, best_baseline, mean_dev = select_best_baseline(raw, baselines)
    baseline_corrected = (best_wid != wid)
    workload_name = best_baseline["name"]

    # 2. Extract context
    all_devs  = compute_deviations(raw, best_baseline)
    top_procs = extract_top_processes(metadata, n=3)
    
    if not all_devs:
        return
        
    top_dev_val = all_devs[0]["deviation"]
    top_feature = all_devs[0]["feature"]
    severity = _severity(top_dev_val)
    
    # 3. Cache check (Cooldown + Deduplication)
    issue_key = f"{workload_name}_{top_feature}_{severity}"
    cached = _get_cached_diagnosis(issue_key)
    
    if cached == "THROTTLED":
        # Skip alerting altogether for this tick to prevent spam
        return
        
    diagnosis = None
    if cached:
        diagnosis = cached
        diagnosis["cached"] = True
    else:
        # 4. LLM Call
        prompt = _build_prompt(workload_name, all_devs, top_procs, score)
        parsed = _call_groq(prompt)
        
        if parsed:
            diagnosis = parsed
        else:
            diagnosis = _fallback_diagnosis(workload_name, all_devs, top_procs)
            
        diagnosis["cached"] = False

    # 5. Attach metrics to diagnosis
    diagnosis["workload"] = workload_name
    diagnosis["severity"] = severity
    diagnosis["issue_key"] = issue_key
    diagnosis["top_deviations"] = all_devs[:5]
    diagnosis["top_procs"] = top_procs
    diagnosis["baseline_corrected"] = baseline_corrected
    diagnosis["baseline_mean_dev_iqr"] = mean_dev
    
    dev_conf = min(1.0, max(0.0, top_dev_val / 5.0))
    diagnosis["confidence"] = {
        "combined": round(dev_conf * 100, 1),
        "deviation_component": round(dev_conf * 100, 1),
        "top_deviation_iqr": round(top_dev_val, 4),
        "deviation_cap_iqr": 5.0
    }
    
    # Update cache
    _cache_diagnosis(issue_key, diagnosis)

    # 6. Save and output
    write_diagnosis(conn, alert_id, diagnosis)
    report = format_report(alert_id, diagnosis)
    print(report)
    log_report_to_file(report)

# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------

def run_diagnosis_daemon() -> None:
    """
    LLM-powered daemon using Groq.
    Replaces rule_diagnosis.py
    """
    ensure_wal_mode(ALERTS_DB_PATH)
    conn = create_connection(ALERTS_DB_PATH)
    init_alerts_db(conn)
    init_diagnoses_table(conn)

    print(f"[groq_diagnosis] Listening for alerts (model: {GROQ_MODEL})...")
    get_baselines() # Initial load
    
    try:
        while True:
            try:
                for alert_id, meta_json, data_json in fetch_undiagnosed_alerts(conn):
                    process_alert(conn, alert_id, meta_json, data_json)
            except sqlite3.Error as exc:
                print(f"[groq_diagnosis] DB error: {exc}")
            time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        print("\n[groq_diagnosis] Stopped.")
    finally:
        conn.close()


if __name__ == "__main__":
    run_diagnosis_daemon()
