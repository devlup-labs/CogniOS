# OSDoctor

**Real-Time Intelligent Operating System Monitoring & Anomaly Detection System**

## Project Documentation

## 1. Introduction

OSDoctor is an intelligent observability system that continuously monitors operating system telemetry, detects abnormal system behavior using machine learning (Isolation Forest), identifies the likely root cause using a local LLM engine (Ollama Gemma 2b), and explains issues in clear natural language. Its objective is to answer the question: *"Why is my laptop slow right now?"*

---

## 2. Objectives

- Monitor real-time system and process telemetry.
- Detect system anomalies automatically using Isolation Forest ML with an explicit decision threshold (`score <= -0.1`).
- Identify root causes of system performance degradation (CPU spikes, memory leaks, high swap, disk I/O bottlenecks).
- Explain technical system faults in simple, human-readable language.
- Provide dynamic AI confidence ratings (50% – 99%) and actionable remediation steps.
- Present live metrics and diagnostic feeds in a Streamlit dashboard.

---

## 3. System Architecture

```text
CogniOS Telemetry Collector
        │
        ▼
OSDoctor Data Extraction (featuring.py)
        │
        ▼
Feature Vector (System + Process Metrics)
        │
        ▼
Isolation Forest Predictor (i_forest_predict.py)
        │
        ├── Score > -0.1 (Normal System State)
        │      │
        │      ▼
        │   Continue Monitoring
        │
        └── Score <= -0.1 (Anomaly Detected)
               │
               ▼
         alerts.db (alerts table)
               │
               ▼
        LLM Explanation Layer (llm_layer.py)
        [Tier 1: Ollama gemma2:2b | Tier 2: Gemini API]
               │
               ▼
         alerts.db (diagnoses table)
               │
               ▼
      Streamlit Dashboard (os_doctor_view.py)
```

---

## 4. File Structure

```text
os_doctor/
├── __init__.py               # Marks directory as a Python package
├── alerts.db                 # SQLite database storing raw alerts and LLM diagnoses
├── alerts_db.py              # WAL-mode database interface & schema definitions
├── featuring.py              # Feature engineering, scaling, and rolling window extraction
├── i_forest_train.py         # Isolation Forest model training script
├── i_forest_predict.py       # Live anomaly detection execution loop (Threshold: -0.1)
├── iso_forest_model.joblib   # Persisted trained Isolation Forest model binary
├── llm_layer.py              # LLM daemon engine (Ollama gemma2:2b + Gemini fallback)
├── os_doctor_db.py         # Database query & helper functions
└── README.md                 # Project documentation and guide
```

---

# `featuring.py`

This module bridges transactional database storage and in-memory multi-dimensional feature calculations. It queries the running SQLite telemetry database in WAL mode, extracts historical sliding windows, standardizes missing rows, and computes derived statistical features for anomaly detection.

---

### 1. `extract_and_engineer_system`

- **Description:** Queries the SQLite database safely in WAL mode to extract the latest rolling historical sliding window of system telemetry rows.
- **Input:**
  - `DB_PATH` (str): Absolute path to the centralized SQLite database.
  - `window_size` (int): Number of historical rows to fetch (default: 120 samples / 2 minutes).
- **Output:** `sys_vec` (pd.DataFrame): Single-row vector containing rolling averages, gradients, and scaled system telemetry metrics.

---

### 2. `extract_and_engineer_processes`

- **Description:** Queries process telemetry to extract historical sliding windows of top process CPU and RAM metrics.
- **Input:**
  - `DB_PATH` (str): Absolute path to centralized SQLite database.
  - `window_size` (int): Number of historical process samples to fetch (default: 24 samples).
- **Output:** `cpu_vec, ram_vec` (pd.DataFrame): Process feature vectors with rolling averages and consumption rates.

---

### 3. `build_unified_vectors`

- **Description:** Combines system and process vectors into a single feature matrix formatted for the Isolation Forest model while preserving raw process metadata for the LLM layer.
- **Input:** `sys_vec, ram_vec, cpu_vec` (pd.DataFrame)
- **Output:**
  - `i_forest_features_df` (pd.DataFrame): Formatted DataFrame passed into Isolation Forest predictor.
  - `metadata_payload` (dict): Process metadata (`pid`, `name`, `ppid`, `user`).

---

### 4. `get_inference_payload`

- **Description:** Orchestrates extraction functions in sequence and enforces database buffer safety checks before feature calculation.
- **Input:** `DB_PATH` (str)
- **Output:** `i_forest_features_df, metadata_payload`

---

# `i_forest_predict.py`

This module executes real-time anomaly detection by applying the trained Isolation Forest model to incoming feature vectors.

---

### 1. `flag_anomaly(DB_PATH)`

- **Description:** Loads `iso_forest_model.joblib` and `scaler.joblib`, standardizes incoming telemetry vectors, evaluates model decision score, and flags anomalies against an explicit decision threshold (`score <= -0.1`).
- **Threshold Rule:**
  - `score > -0.1`: System operating normally (no alert).
  - `score <= -0.1`: Anomaly flagged and written to `alerts.db`.
- **Output:** Inserts JSON payload into `alerts` table containing:
  - `raw`: Unscaled human-readable metrics.
  - `scaled`: Scaled feature array.
  - `anomaly_score`: Float decision score.

---

# `alerts_db.py`

Manages database connections, table creation, and transactional writes for `os_doctor/alerts.db` operating in WAL (Write-Ahead Logging) mode for concurrent access.

---

### Database Schema

1. **`alerts` table**:
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `timestamp`: DATETIME DEFAULT CURRENT_TIMESTAMP
   - `metadata`: TEXT (JSON object with PID, process name, command)
   - `data`: TEXT (JSON object with `raw`, `scaled`, and `anomaly_score`)

2. **`diagnoses` table**:
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `alert_id`: INTEGER UNIQUE (Foreign Key -> `alerts.id`)
   - `issue`: TEXT (Summary heading, e.g. "Memory pressure")
   - `cause`: TEXT (Human-readable root cause explanation)
   - `severity`: TEXT ("Low", "Medium", "High", "Critical")
   - `suggested_action`: TEXT (Actionable remediation advice)
   - `confidence`: REAL (AI confidence rating, 50.0% – 99.0%)
   - `created_at`: DATETIME DEFAULT CURRENT_TIMESTAMP

---

# `llm_layer.py`

Integrates local Ollama (`gemma2:2b`) offline LLM inference with automatic fallback to Google Gemini Cloud API. Explains numerical anomaly alerts in human-understandable English.

---

### 1. `call_gemma(prompt, system)`

- **Description:** Tier-1 offline execution via local Ollama (`http://localhost:11434/api/generate` with model `gemma2:2b`). Automatically falls back to Google Gemini Cloud API if Ollama is unreachable.

---

### 2. `compute_severity_and_confidence(anomaly_score, data_raw)`

- **Description:** Computes dynamic AI confidence percentage (50% – 99%) based on Isolation Forest score magnitude:
  $$\text{Confidence} = 50\% + \min(49, \text{abs}(\text{anomaly\_score}) \times 300)$$
- **Output:** Returns severity string (`"Low"`, `"Medium"`, `"High"`, `"Critical"`) and confidence percentage.

---

### 3. `run_llm_daemon()`

- **Description:** Background daemon loop that continuously polls `alerts.db` for unanalyzed alerts, enforces a 5-minute explanation cooldown to prevent LLM spam, calls the LLM engine for structured root-cause explanations, and writes results into `diagnoses` table.

---

# Frontend Integration (`dashboard/views/os_doctor_view.py`)

The Streamlit dashboard view consumes `os_doctor` database tables via `dashboard/data_provider.py`.

---

### Key UI Components & Data Methods

1. **`get_os_doctor_anomaly_score()`**:
   Calculates dynamic 0–100 radial gauge score from Isolation Forest `anomaly_score` in `alerts.db`:
   $$\text{Score} = \min(99, \max(15, \text{int}(\text{abs}(\text{anomaly\_score}) \times 450)))$$

2. **Top Resource Hogs Process Table**:
   Renders a 5-column table (`PROCESS NAME`, `PID`, `CPU %`, `RAM %`, `STATUS`) sorting active processes by resource impact score (`cpu% + ram% * 1.5`).

3. **`get_os_doctor_diagnoses(limit, severity_filter, search_query)`**:
   Queries `diagnoses` table joined with `alerts` table to render human-readable LLM explanation cards, dynamic severity badges, confidence ratings, remediation pills, and expandable raw telemetry inspect accordions.

4. **`get_os_doctor_summary_stats()`**:
   Computes overall KPI stats (`TOTAL DIAGNOSES`, `HIGH / CRITICAL`, `AVG AI CONFIDENCE`, `LATEST ANOMALY`).

5. **Layer 4 Process Drill-Down Panel**:
   Queries `psutil.Process` for open file descriptors, context switches, CPU user/sys time, and active socket connections for deep kernel-level process inspection.