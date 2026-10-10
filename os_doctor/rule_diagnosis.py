"""
Baseline-deviation diagnosis engine for OS Doctor.

Approach:
  1. At startup, load all 4 workload scalers.
     Extract scaler.center_ (median raw vector) as the baseline for each workload.
  2. On every anomaly alert:
     a. Compute deviation[i] = abs(raw[i] - baseline[i]) / scale_[i]  for all 24 features.
        This equals |scaled_value[i]| — normalized, cross-feature comparable.
     b. Sort by deviation descending.
     c. Top 3 features drive the category vote and diagnosis.
     d. Extract top 3 CPU and top 3 RAM processes from metadata.
  3. Confidence:
     - IF confidence  = how far the anomaly score falls below the model's threshold.
     - FocusOS confidence = workload classification probability from the alert data.
     - Combined = 0.65 * IF + 0.35 * FocusOS (both scaled 0–1).
"""

import json
import os
import time
import sqlite3

import joblib
import numpy as np

from os_doctor.alerts_db import (
    create_connection,
    ensure_wal_mode,
    init_alerts_db,
)
from config import ALERTS_DB_PATH, ALERTS_TABLE_NAME, WORKLOADS, OS_DOCTOR_MODELS_DIR
from os_doctor.featuring import ML_FEATURES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIAGNOSES_TABLE_NAME = "diagnoses"

# ---------------------------------------------------------------------------
# Feature metadata: category and human-readable label
# ---------------------------------------------------------------------------

# Each feature maps to (category, label).
# Category drives the "dominant failure domain" vote.
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
# Diagnosis templates per category.
# Placeholders: {workload}, {top_feature_label}, {top_feature_raw},
#               {top_cpu_proc}, {top_ram_proc}
# ---------------------------------------------------------------------------

CATEGORY_TEMPLATES: dict[str, dict] = {
    "CPU": {
        "root_cause_fmt": (
            "CPU contention — {top_feature_label} deviates most from the "
            "{workload} baseline (measured: {top_feature_raw})"
        ),
        "explanation_fmt": (
            "The CPU is under abnormal pressure for a {workload} session. "
            "{top_feature_label} is {top_feature_raw}, which is far above the learned normal. "
            "Process '{top_cpu_proc}' is the top CPU consumer at this moment."
        ),
        "recommendations_fmt": [
            "Open Activity Monitor → CPU tab. Sort by '% CPU'.",
            "Check if '{top_cpu_proc}' is the expected foreground process.",
            "Kill or lower the priority of any unexpected high-CPU process.",
            "Check for background compilers, indexers, or antivirus scans.",
        ],
    },
    "MEMORY": {
        "root_cause_fmt": (
            "Memory pressure — {top_feature_label} deviates most from the "
            "{workload} baseline (measured: {top_feature_raw})"
        ),
        "explanation_fmt": (
            "RAM usage during this {workload} session is abnormally high. "
            "{top_feature_label} is {top_feature_raw}, indicating the system strains to manage memory. "
            "Process '{top_ram_proc}' holds the most RAM."
        ),
        "recommendations_fmt": [
            "Open Activity Monitor → Memory tab. Sort by 'Memory'.",
            "Check if '{top_ram_proc}' has a memory leak (growing RSS over time).",
            "Close unused browser tabs, documents, or applications.",
            "Restart '{top_ram_proc}' if its memory use keeps growing.",
        ],
    },
    "IO": {
        "root_cause_fmt": (
            "Disk/I/O bottleneck — {top_feature_label} deviates most from the "
            "{workload} baseline (measured: {top_feature_raw})"
        ),
        "explanation_fmt": (
            "Disk activity during this {workload} session is unusually high. "
            "{top_feature_label} is {top_feature_raw}, which stalls processes waiting for storage. "
            "Process '{top_cpu_proc}' is the top CPU consumer; it may also drive the I/O."
        ),
        "recommendations_fmt": [
            "Open Activity Monitor → Disk tab. Sort by 'Bytes Written' or 'Bytes Read'.",
            "Check if a backup, sync, or index job (Time Machine, Spotlight) is running.",
            "Stop cloud sync (iCloud, Dropbox) temporarily during critical work.",
            "Run Disk Utility → First Aid to check disk health.",
        ],
    },
    "THERMAL": {
        "root_cause_fmt": (
            "Thermal throttling — {top_feature_label} deviates most from the "
            "{workload} baseline (measured: {top_feature_raw})"
        ),
        "explanation_fmt": (
            "The CPU is overheating during this {workload} session. "
            "{top_feature_label} is {top_feature_raw}. "
            "The system reduces CPU clock speed to prevent damage. "
            "Every task runs slower as a result."
        ),
        "recommendations_fmt": [
            "Place the laptop on a hard flat surface — never on a bed or lap.",
            "Clean dust from vents and fans.",
            "Stop any heavy background task to let the CPU cool.",
            "Check CPU temperature with a monitor tool (e.g. iStatMenus).",
        ],
    },
    "RESOURCE_LEAK": {
        "root_cause_fmt": (
            "Resource leak — {top_feature_label} deviates most from the "
            "{workload} baseline (measured: {top_feature_raw})"
        ),
        "explanation_fmt": (
            "A process opens resources faster than it releases them during this {workload} session. "
            "{top_feature_label} is {top_feature_raw}. "
            "Process '{top_cpu_proc}' is the top CPU consumer and may be the source."
        ),
        "recommendations_fmt": [
            "Monitor '{top_cpu_proc}' open file count over time.",
            "Restart '{top_cpu_proc}' if the metric keeps rising.",
            "Report a resource leak bug to the developer of '{top_cpu_proc}'.",
        ],
    },
    "NETWORK": {
        "root_cause_fmt": (
            "Network instability — {top_feature_label} deviates most from the "
            "{workload} baseline (measured: {top_feature_raw})"
        ),
        "explanation_fmt": (
            "TCP retransmissions are unusually high during this {workload} session. "
            "{top_feature_label} is {top_feature_raw}. "
            "Dropped packets force the OS to resend data, adding latency to every network call."
        ),
        "recommendations_fmt": [
            "Move closer to the Wi-Fi router or switch to a wired connection.",
            "Disconnect and reconnect the VPN if one is active.",
            "Restart the router if the problem persists.",
        ],
    },
}

# ---------------------------------------------------------------------------
# Baseline loader — extracts center_ and scale_ from each workload scaler
# ---------------------------------------------------------------------------

def load_all_baselines() -> dict[int, dict]:
    """
    Load the RobustScaler for each trained workload and extract:
      - center_  : median of each feature in raw units (the 'normal' vector)
      - scale_   : IQR of each feature in raw units   (the normalization divisor)
      - model    : the Isolation Forest (for threshold_)

    Returns a dict keyed by workload_id:
    {
        0: {"name": "idle",    "center": {...}, "scale": {...}, "threshold": float},
        1: {"name": "browsing", ...},
        ...
    }
    Missing workloads are silently skipped.
    """
    baselines: dict[int, dict] = {}
    for wid, cfg in WORKLOADS.items():
        scaler_path = cfg["scaler_path"]
        model_path  = cfg["model_path"]

        if not os.path.exists(scaler_path) or not os.path.exists(model_path):
            continue

        try:
            scaler = joblib.load(scaler_path)
            model  = joblib.load(model_path)

            center = dict(zip(ML_FEATURES, scaler.center_.tolist()))
            scale  = dict(zip(ML_FEATURES, scaler.scale_.tolist()))

            # model.threshold_ is set by contamination during fit().
            # Points below this are labeled -1 (anomaly).
            threshold = float(model.threshold_)

            baselines[wid] = {
                "name":      cfg["name"],
                "center":    center,
                "scale":     scale,
                "threshold": threshold,
            }
        except Exception as exc:
            print(f"[diagnosis] Could not load workload {cfg['name']}: {exc}")

    return baselines

# ---------------------------------------------------------------------------
# Deviation computation
# ---------------------------------------------------------------------------

def compute_deviations(raw: dict, baseline: dict) -> list[dict]:
    """
    Computes normalized absolute deviation for each of the 24 ML features.

    deviation[i] = abs(raw[i] - center[i]) / max(scale[i], 1e-9)
                 = |scaled_value[i]|

    Returns a list of dicts sorted by deviation descending.
    Each dict:
        feature    : str
        label      : str
        category   : str
        raw_value  : float
        baseline   : float  — the workload median for this feature
        deviation  : float  — normalized (IQR units), cross-feature comparable
        direction  : str    — "above baseline" | "below baseline"
    """
    results = []
    center = baseline["center"]
    scale  = baseline["scale"]

    for feat in ML_FEATURES:
        try:
            raw_val  = float(raw.get(feat, 0.0) or 0.0)
            center_v = float(center.get(feat, 0.0))
            scale_v  = max(float(scale.get(feat, 1.0)), 1e-9)
        except (TypeError, ValueError):
            continue

        dev = abs(raw_val - center_v) / scale_v
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


def select_best_baseline(
    raw: dict,
    baselines: dict,
) -> tuple[int, dict, float]:
    """
    Choose the baseline whose normal behavior best fits the current machine state.
    Ignores the workload_id label from FocusOS entirely.

    Method:
      For each trained baseline, compute the mean deviation across ALL 24 features.
      Mean deviation = average of |raw[i] - center[i]| / scale[i] for all i.

      The baseline with the LOWEST mean deviation is the most compatible workload.
      If FocusOS classified correctly, this agrees with the alert's workload_id.
      If FocusOS classified wrongly, this silently corrects the selection.

    Why mean of ALL 24 (not just top-3):
      An anomalous gaming session has 4-5 features far from the gaming baseline
      but the other 19-20 features are still close to it.
      Against the browsing baseline ALL 24 features deviate.
      Mean deviation over all features captures overall fit, not just the worst.

    Parameters
    ----------
    raw       : dict  — raw metric values from the alert
    baselines : dict  — all loaded baselines, keyed by workload_id

    Returns
    -------
    (best_wid, best_baseline, mean_deviation)
    """
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


# ---------------------------------------------------------------------------
# Category vote
# ---------------------------------------------------------------------------

def _dominant_categories(top3: list[dict]) -> list[tuple[str, float]]:
    """
    Each of the top-3 features votes for its category.
    Vote weight = deviation magnitude.
    Returns categories sorted by total vote score, descending.
    """
    scores: dict[str, float] = {}
    for feat in top3:
        cat = feat["category"]
        scores[cat] = scores.get(cat, 0.0) + feat["deviation"]
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

# ---------------------------------------------------------------------------
# Process extraction
# ---------------------------------------------------------------------------

def _extract_proc_group(metadata: dict, prefix: str, n: int = 3) -> list[dict]:
    """
    Extracts up to n process records for prefix='cpu' or 'ram' from metadata.
    Returns only non-empty records.
    """
    procs = []
    for i in range(1, 6):
        name = metadata.get(f"{prefix}_{i}_name")
        if not name or str(name) in ("0", "0.0", "", "nan"):
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

        procs.append(entry)
        if len(procs) == n:
            break
    return procs


def extract_top_processes(metadata: dict, n: int = 3) -> dict:
    return {
        "cpu": _extract_proc_group(metadata, "cpu", n),
        "ram": _extract_proc_group(metadata, "ram", n),
    }

# ---------------------------------------------------------------------------
# Confidence score
# ---------------------------------------------------------------------------

def compute_confidence(
    top_deviation: float,
    focusos_confidence: float,      # 0–100 from WorkloadPredictor
    *,
    deviation_cap: float = 5.0,
) -> dict:
    """
    Two-signal confidence score using simpler, model-internal-free inputs.

    Signal 1 — Top deviation score (already computed, no model internals needed):
      How far the worst metric sits from the workload baseline in IQR units.
      deviation_conf = min(1.0, top_deviation / deviation_cap)
      deviation_cap  = 5.0 IQR → 100%.  Tunable.

      | top_deviation | deviation_conf |
      |     1.5 IQR   |     30 %       |
      |     3.0 IQR   |     60 %       |
      |     5.0 IQR   |    100 %       |

    Signal 2 — FocusOS workload confidence (0–100 → 0–1):
      How sure FocusOS is that the right baseline was used.

    Combined = 0.65 * deviation_conf + 0.35 * focusos_conf
    Returned as 0–100, rounded to 1 decimal.

    Parameters
    ----------
    top_deviation     : float — largest |raw − center| / scale across 24 features.
    focusos_confidence: float — workload classification probability, 0–100.
    deviation_cap     : float — deviation value that maps to 100% (default 5.0 IQR).
    """
    dev_conf      = min(1.0, max(0.0, top_deviation / deviation_cap))
    focusos_conf  = min(1.0, max(0.0, focusos_confidence / 100.0))
    combined      = (0.65 * dev_conf + 0.35 * focusos_conf) * 100

    return {
        "combined":             round(combined, 1),
        "deviation_component":  round(dev_conf * 100, 1),
        "focusos_component":    round(focusos_conf * 100, 1),
        "top_deviation_iqr":    round(top_deviation, 4),
        "deviation_cap_iqr":    deviation_cap,
    }


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

def _severity(max_deviation: float) -> str:
    if max_deviation >= 5.0:   return "critical"
    if max_deviation >= 3.0:   return "high"
    if max_deviation >= 1.5:   return "medium"
    return "low"

# ---------------------------------------------------------------------------
# Build diagnosis
# ---------------------------------------------------------------------------

def diagnose(
    raw: dict,
    baseline: dict,
    metadata: dict,
    workload_name: str,
    focusos_confidence: float,
) -> dict:
    """
    Full diagnosis from one anomaly alert.

    Returns
    -------
    dict with keys:
        workload, severity, confidence, root_cause, explanation,
        recommendations, primary_category, secondary_category,
        top_deviations (top 3 feature dicts),
        top_procs (cpu: list[3], ram: list[3])
    """
    all_devs     = compute_deviations(raw, baseline)
    top3         = all_devs[:3]
    top_procs    = extract_top_processes(metadata, n=3)
    top_dev_val  = top3[0]["deviation"] if top3 else 0.0
    confidence   = compute_confidence(top_dev_val, focusos_confidence)

    # Category vote
    ranked_cats = _dominant_categories(top3)
    primary_cat = ranked_cats[0][0] if ranked_cats else "CPU"

    # Secondary category — only if its score is within 20% of the primary
    secondary_cat = None
    if len(ranked_cats) >= 2:
        p_score = ranked_cats[0][1]
        s_score = ranked_cats[1][1]
        if p_score > 0 and (s_score / p_score) >= 0.80:
            secondary_cat = ranked_cats[1][0]

    # Fill template
    top_cpu_proc = top_procs["cpu"][0]["name"] if top_procs["cpu"] else "unknown"
    top_ram_proc = top_procs["ram"][0]["name"] if top_procs["ram"] else "unknown"
    top_feat     = top3[0] if top3 else {}

    fmt_vars = {
        "workload":          workload_name,
        "top_feature_label": top_feat.get("label", "unknown metric"),
        "top_feature_raw":   top_feat.get("raw_value", 0),
        "top_cpu_proc":      top_cpu_proc,
        "top_ram_proc":      top_ram_proc,
    }

    tmpl = CATEGORY_TEMPLATES.get(primary_cat, CATEGORY_TEMPLATES["CPU"])

    root_cause    = tmpl["root_cause_fmt"].format(**fmt_vars)
    explanation   = tmpl["explanation_fmt"].format(**fmt_vars)
    recommendations = [r.format(**fmt_vars) for r in tmpl["recommendations_fmt"]]

    if secondary_cat:
        recommendations.append(
            f"Also investigate {secondary_cat.lower().replace('_', ' ')} — "
            f"it shows elevated deviation alongside the primary cause."
        )

    return {
        "workload":           workload_name,
        "severity":           _severity(top3[0]["deviation"] if top3 else 0),
        "confidence":         confidence,
        "root_cause":         root_cause,
        "explanation":        explanation,
        "recommendations":    recommendations,
        "primary_category":   primary_cat,
        "secondary_category": secondary_cat,
        "top_deviations":     top3,
        "top_procs":          top_procs,
    }

# ---------------------------------------------------------------------------
# Format report
# ---------------------------------------------------------------------------

def format_report(alert_id: int, diagnosis: dict) -> str:
    conf   = diagnosis["confidence"]
    sev    = diagnosis["severity"].upper()
    wl     = diagnosis.get("workload", "unknown")
    sec    = diagnosis.get("secondary_category")
    procs  = diagnosis.get("top_procs", {})

    lines = [
        f"{'═' * 66}",
        f"  OS Doctor  ·  Alert #{alert_id}  ·  Workload: {wl}  ·  Severity: {sev}",
        f"{'═' * 66}",
        f"",
        f"  Confidence : {conf['combined']}%  "
        f"(deviation signal: {conf['deviation_component']}%  |  "
        f"workload match: {conf['focusos_component']}%)",
        f"  Top deviation : {conf['top_deviation_iqr']} IQR  "
        f"(cap: {conf['deviation_cap_iqr']} IQR = 100%)",
    ]

    # Show correction notice when the engine overrides the FocusOS workload label.
    if diagnosis.get("baseline_corrected"):
        focusos_wl = diagnosis.get("focusos_predicted_workload", "unknown")
        lines += [
            f"",
            f"  ⚡ Baseline auto-corrected",
            f"  FocusOS predicted workload  : {focusos_wl}",
            f"  Best-fit workload selected  : {wl}  "
            f"(mean deviation {diagnosis.get('baseline_mean_dev_iqr', '?')} IQR across 24 features)",
            f"  Diagnosis uses the '{wl}' baseline.",
        ]

    lines += [
        f"",
        f"  Root cause",
        f"  {'─' * 60}",
        f"  {diagnosis['root_cause']}",
        f"",
        f"  What happened",
        f"  {'─' * 60}",
        f"  {diagnosis['explanation']}",
    ]

    if sec:
        lines += [
            f"",
            f"  ⚠ Secondary cause: {sec.lower().replace('_', ' ')} metrics also deviate.",
        ]

    # Top 3 deviated features
    lines += [
        f"",
        f"  Top 3 deviated features (vs {wl} baseline)",
        f"  {'─' * 60}",
        f"  {'Feature':<44} {'Measured':>10}  {'Baseline':>10}  {'Deviation (IQR)':>15}  Direction",
        f"  {'─' * 95}",
    ]
    for feat in diagnosis.get("top_deviations", []):
        lines.append(
            f"  [{feat['category']:<13}]  "
            f"{feat['label']:<44} "
            f"{str(feat['raw_value']):>10}  "
            f"{str(feat['baseline']):>10}  "
            f"{feat['deviation']:>15.4f}  "
            f"{feat['direction']}"
        )

    # Top 3 CPU processes
    cpu_procs = procs.get("cpu", [])
    lines += [f"", f"  Top CPU processes at anomaly time"]
    if cpu_procs:
        lines.append(f"  {'Name':<22} {'PID':>7}  {'PPID':>7}  {'Status':<12}  {'CPU peak':>10}")
        lines.append(f"  {'─' * 65}")
        for p in cpu_procs:
            lines.append(
                f"  {str(p['name']):<22} "
                f"{str(p.get('pid','?')):>7}  "
                f"{str(p.get('ppid','?')):>7}  "
                f"{str(p.get('status','?')):<12}  "
                f"{str(p.get('cpu_peak_%','?')):>9}%"
            )
    else:
        lines.append(f"  (no data)")

    # Top 3 RAM processes
    ram_procs = procs.get("ram", [])
    lines += [f"", f"  Top RAM processes at anomaly time"]
    if ram_procs:
        lines.append(f"  {'Name':<22} {'PID':>7}  {'PPID':>7}  {'Status':<12}  {'RAM peak (MB)':>14}  {'Open FDs':>9}")
        lines.append(f"  {'─' * 80}")
        for p in ram_procs:
            lines.append(
                f"  {str(p['name']):<22} "
                f"{str(p.get('pid','?')):>7}  "
                f"{str(p.get('ppid','?')):>7}  "
                f"{str(p.get('status','?')):<12}  "
                f"{str(p.get('ram_peak_MB','?')):>14}  "
                f"{str(p.get('open_fds','?')):>9}"
            )
    else:
        lines.append(f"  (no data)")

    # Recommendations
    lines += [f"", f"  Recommendations", f"  {'─' * 60}"]
    for i, rec in enumerate(diagnosis.get("recommendations", []), 1):
        lines.append(f"  {i}. {rec}")

    lines.append(f"{'═' * 66}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def init_diagnoses_table(conn: sqlite3.Connection) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {DIAGNOSES_TABLE_NAME} (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id           INTEGER NOT NULL UNIQUE,
            workload           TEXT,
            severity           TEXT,
            confidence_json    TEXT,
            root_cause         TEXT,
            explanation        TEXT,
            recommendations    TEXT,
            primary_category   TEXT,
            secondary_category TEXT,
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
            (alert_id, workload, severity, confidence_json, root_cause,
             explanation, recommendations, primary_category, secondary_category,
             top_deviations, top_procs)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            alert_id,
            diagnosis.get("workload"),
            diagnosis.get("severity"),
            json.dumps(diagnosis.get("confidence", {}),       separators=(",", ":")),
            diagnosis.get("root_cause"),
            diagnosis.get("explanation"),
            json.dumps(diagnosis.get("recommendations", []),  separators=(",", ":")),
            diagnosis.get("primary_category"),
            diagnosis.get("secondary_category"),
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
# Alert processor
# ---------------------------------------------------------------------------

def process_alert(
    conn: sqlite3.Connection,
    alert_id: int,
    metadata_json: str,
    data_json: str,
    baselines: dict[int, dict],
) -> None:
    try:
        metadata = json.loads(metadata_json)
        data     = json.loads(data_json)
        raw      = data.get("raw", {})
        wid      = data.get("workload_id")
        workload = data.get("workload_name", "unknown")
        score    = float(data.get("anomaly_score", 0.0))
        # FocusOS confidence is stored alongside workload info.
        # If not present yet, default to 80 (reasonable assumption when workload
        # was determined correctly enough to trigger the right baseline).
        focusos_conf = float(data.get("focusos_confidence", 80.0))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"[diagnosis] alert {alert_id}: malformed JSON, skipping ({exc})")
        return

    baseline = baselines.get(wid)
    if baseline is None and not baselines:
        print(f"[diagnosis] alert {alert_id}: no baselines loaded, skipping.")
        return

    # Select the best-fit baseline regardless of the FocusOS workload label.
    # This corrects wrong workload classifications automatically.
    best_wid, best_baseline, mean_dev = select_best_baseline(raw, baselines)

    # Detect and report a mismatch between FocusOS prediction and best-fit baseline.
    focusos_workload_name = baselines.get(wid, {}).get("name", "unknown")
    best_workload_name    = best_baseline.get("name", "unknown")
    baseline_corrected    = (best_wid != wid)

    if baseline_corrected:
        print(
            f"[diagnosis] alert {alert_id}: FocusOS predicted workload '{focusos_workload_name}' "
            f"but best-fit baseline is '{best_workload_name}' "
            f"(mean deviation {mean_dev:.3f} IQR). Using '{best_workload_name}'."
        )

    diagnosis = diagnose(
        raw=raw,
        baseline=best_baseline,
        metadata=metadata,
        workload_name=best_workload_name,
        focusos_confidence=focusos_conf,
    )

    # Attach correction metadata for the report and DB.
    diagnosis["focusos_predicted_workload"] = focusos_workload_name
    diagnosis["baseline_corrected"]         = baseline_corrected
    diagnosis["baseline_mean_dev_iqr"]      = mean_dev

    write_diagnosis(conn, alert_id, diagnosis)
    print(format_report(alert_id, diagnosis))

# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------

POLL_INTERVAL_S = 10


def run_diagnosis_daemon(poll_interval: int = POLL_INTERVAL_S) -> None:
    """
    Drop-in for the old run_llm_daemon().

    Usage (test.py):
        from os_doctor.rule_diagnosis import run_diagnosis_daemon
        threading.Thread(target=run_diagnosis_daemon, daemon=True).start()
    """
    baselines = load_all_baselines()
    if not baselines:
        print("[diagnosis] No trained baselines found. Run training first.")
        return

    for wid, b in baselines.items():
        print(f"[diagnosis] Loaded baseline for workload '{b['name']}' "
              f"(IF threshold={b['threshold']:.4f})")

    ensure_wal_mode(ALERTS_DB_PATH)
    conn = create_connection(ALERTS_DB_PATH)
    init_alerts_db(conn)
    init_diagnoses_table(conn)

    print("[diagnosis] Listening for alerts (baseline-deviation engine)...")
    try:
        while True:
            try:
                for alert_id, meta_json, data_json in fetch_undiagnosed_alerts(conn):
                    process_alert(conn, alert_id, meta_json, data_json, baselines)
            except sqlite3.Error as exc:
                print(f"[diagnosis] DB error: {exc}")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[diagnosis] Stopped.")
    finally:
        conn.close()


if __name__ == "__main__":
    run_diagnosis_daemon()
