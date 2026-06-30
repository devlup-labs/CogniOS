# OSDoctor

**Real-Time Intelligent Operating System Monitoring & Anomaly Detection System**

## Project Documentation

## 1. Introduction

OSDoctor is an intelligent observability system that continuously monitors operating system telemetry, detects abnormal system behavior using machine learning, identifies the likely root cause, and explains the issue in natural language. Its objective is to answer the question: “Why is my laptop slow right now?”

## 2. Objectives

- Monitor real-time system telemetry.
- Detect system anomalies automatically.
- Identify causes of performance issues.
- Detect CPU, memory, disk, and process-related faults.
- Explain issues in simple, human-readable language.
- Provide actionable alerts and recommendations.

## 3. System Architecture

```text
CogniOS Telemetry Collector
        │
        ▼
OSDoctor (Data Extraction)
        │
        ▼
System Metrics + Process Metrics
        │
        ▼
SQLite Database
        │
        ▼
Feature Engineering
        │
        ▼
Isolation Forest
        │
        ├── No Anomaly
        │      │
        │      ▼
        │   Continue Monitoring
        │
        └── Anomaly Detected
               │
               ▼
         Alerts Table
               │
               ▼
        LLM Explanation Layer
               │
               ▼
        Streamlit Dashboard
```

## 4. File Structure

```text
os_doctor/
│── _init_.py             # Marks the directory as a Python package
│── featuring.py          # Feature engineering and preprocessing
│── i_forest.py           # Isolation Forest model implementation
│── llm_layer.py          # LLM integration and response generation
│── streamlit.py          # Streamlit web application
│── README.md             # Project overview and setup guide
```

# `feature.py`

This module bridges the gap between transactional database storage and in-memory multi-dimensional math. It queries the running SQLite database in WAL mode, extracts the latest historical sliding window, standardizes missing rows, and computes derived statistical features for the anomaly detection pipeline.

---

### 1. `extract_telemetry_window`

- **Description:** Queries the running SQLite database safely in WAL mode to extract the latest rolling historical sliding window of system and process telemetry rows.
- **Input:**
  - `db_path` (str): Absolute path to the centralized SQLite database.
  - `window_size` (int): Number of historical rows to fetch (default: 120 samples / 2 minutes).
- **Output:**
  - `tuple[pd.DataFrame, pd.DataFrame]`: A tuple containing the raw system telemetry DataFrame and the process telemetry DataFrame.

---

### 2. `handle_cold_start`

- **Description:** Preprocesses raw process telemetry and backfills missing resource values for newly active or spiking processes to prevent mathematical anomalies or NaN breaks.
- **Input:**
  - `df_process` (pd.DataFrame): Raw process telemetry DataFrame containing compressed or stringified JSON arrays.
- **Output:**
  - `pd.DataFrame`: A standardized, chronologically aligned DataFrame with missing historical process values filled with baseline thresholds (0.0).

---

### 3. `compute_derived_features`

- **Description:** Transforms raw telemetry values into moving statistical fields, computing rolling averages to smooth noise and mathematical gradients (first derivatives) to capture exponential growth trends.
- **Input:**
  - `df_aligned` (pd.DataFrame): Aligned chronological dataframe of system and process metrics.
- **Output:**
  - `pd.DataFrame`: Feature-engineered DataFrame containing original metrics along with computed moving averages and velocity gradients.

---

### 4. `prepare_inference_matrix`

- **Description:** Flattens dimensional matrices and formats the engineered feature matrix into a structured in-memory array ready to be fed directly into the Isolation Forest algorithm.
- **Input:**
  - `df_engineered` (pd.DataFrame): The fully processed DataFrame containing all derived statistical features.
- **Output:**
  - `np.ndarray`: A stable 2D feature matrix of shape `(120, feature_count)` formatted for direct ingestion by `i_forest.py`.

# `i_forest.py`

## 1. `initialize_model()`

- **Input:** None (uses predefined strict configuration parameters: `n_estimators=100`, `max_samples=120`, `contamination='auto'`).
- **Output:** An initialized and configured `IsolationForest` model instance.

## 2. `evaluate_matrix(feature_matrix)`

- **Input:** The perfectly formatted, in-memory 120-sample feature matrix passed directly from the `feature.py` layer.
- **Output:** A numerical anomaly score (`-1` for anomalous, `1` for normal).

## 3. `trigger_alert(anomaly_data)`

- **Input:** The current anomalous system and process metrics (the relevant matrix data packaged into a Python dictionary).
- **Output:** A database insertion (JSON payload) directly into the SQLite `alerts` table.

# `llm_layer.py`

## 1. `watch_alerts_table()`

- **Input:** None (Database connection context)
- **Output:** `anomaly_id` (Returns the ID of the new anomaly with `PENDING_LLM` status)

## 2. `extract_historical_context(anomaly_id)`

- **Input:** `anomaly_id`
- **Output:** `telemetry_data` (The historical 120-sample sliding window matrix of the exact process that broke the system)

## 3. `build_prompt_template(telemetry_data)`

- **Input:** `telemetry_data` (Engineered anomaly vectors and historical snapshots)
- **Output:** `prompt` (A structured JSON prompt template engineered for the LLM)

## 4. `execute_llm_call(prompt)`

- **Input:** `prompt`
- **Output:** `explanation_text` (A specific, actionable natural language breakdown returned by the LLM API)

## 5. `resolve_alert(anomaly_id, explanation_text)`

- **Input:** `anomaly_id`, `explanation_text`
- **Output:** Database Update (Updates SQLite row status to `RESOLVED` and appends the final explanation for the Streamlit dashboard)

# `streamlit.py`

## Streamlit Dashboard (`streamlit.py`) - Function Definitions

This document outlines the core functions required to build the `streamlit.py` presentation layer for DoctorOS. These functions follow the passive-observer pattern, smoothly bridging the Hot Path (live system telemetry) and the Cold Path (out-of-band LLM explanations) via the centralized SQLite database.

---

## 1. `fetch_latest_telemetry`

- **Input:**
  - `db_path` (string): The path to the centralized SQLite database.
  - `time_window_seconds` (int, default=120): The lookback window to fetch data for the graphs.
- **Output:**
  - `pandas.DataFrame`: A dataframe containing the historical time-series data for CPU, RAM, Disk I/O, and Network load over the requested window.

## 2. `fetch_summary_metrics`

- **Input:**
  - `db_path` (string): The path to the centralized SQLite database.
- **Output:**
  - `dict`: A dictionary containing the absolute latest single-point metrics from the `system_telemetry` table (e.g., `{"cpu": 85, "ram": 72, "disk": 45, "network": 12}`).

## 3. `fetch_alerts`

- **Input:**
  - `db_path` (string): The path to the centralized SQLite database.
  - `limit` (int, default=5): The maximum number of recent alerts to fetch from the `alerts` table.
- **Output:**
  - `pandas.DataFrame`: A dataframe of recent anomalies flagged by the Isolation Forest. Crucially, this includes `llm_status` (e.g., `PENDING_LLM` or `RESOLVED`) and `llm_explanation` (the generated text).

## 4. `render_summary_cards`

- **Input:**
  - `metrics_dict` (dict): The output from `fetch_summary_metrics`.
- **Output:**
  - `None`: (UI Side Effect) Uses `st.columns` and `st.metric` to render the high-level gauge cards at the very top of the dashboard.

## 5. `render_resource_graphs`

- **Input:**
  - `telemetry_df` (pandas.DataFrame): The time-series data output from `fetch_latest_telemetry`.
- **Output:**
  - `None`: (UI Side Effect) Renders live updating line charts (via `st.line_chart` or a Plotly equivalent) for system resources mapped to the FocusOS visual footprint.

## 6. `render_alerts_panel`

- **Input:**
  - `alerts_df` (pandas.DataFrame): The anomaly data output from `fetch_alerts`.
- **Output:**
  - `None`: (UI Side Effect) Iterates through the alerts.
    - If `llm_status == 'PENDING_LLM'`, it renders an `st.spinner` or loading state ("Analyzing anomaly...").
    - If `llm_status == 'RESOLVED'`, it renders an `st.expander` containing the LLM's natural language explanation and suggested actions.

## 7. `main`

- **Input:**
  - `None`
- **Output:**
  - `None`: (Execution) Acts as the entry point. Orchestrates the dashboard layout, manages the `st_autorefresh` (or polling loop), calls the fetching functions, and passes the retrieved data to the rendering functions.