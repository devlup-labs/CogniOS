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
│── _init_.py             # Marks the directory as a Python package
│── featuring.py          # Feature engineering and preprocessing
│── i_forest.py           # Isolation Forest model implementation
│── groq_diagnosis.py     # LLM integration, baseline selection, and response generation
│── streamlit.py          # Streamlit web application
│── README.md             # Project overview and setup guide
```

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

- **Description:** Combines the three individual vectors recieved above and handles what to feed into i_forest.py and what to feed to groq_diagnosis.
- **Input:**
  - `sys_vec, ram_vec, cpu_vec` (pd.DataFrame): Raw process telemetry DataFrame containing compressed or stringified JSON arrays.
- **Output:**
  - `i_forest_features_df` (pd.DataFrame): Formatted DataFrame passed into Isolation Forest predictor.
  - `metadata_payload` (dict): Process metadata (`pid`, `name`, `ppid`, `user`).

---

### 4. `get_inference_payload`

- **Description:** It ties the entire file together, it handles safety buffer checks (ensuring we have enough database entries before calculating metrics) and orchestrates Functions 1, 2, and 3 in sequence.
- **Input:**
  - `DB_PATH` (str): Absolute path to the centralized SQLite database.
- **Output:**
  - `i_forest_features_df, metadata_payload`: smoothly executes featuring.py and outputs same as 'build_unified_vectors'

---


# `i_forest_train.py`

**Description:** Handles offline/batch training for OSDoctor's anomaly detection model. It queries historical telemetry datasets from SQLite, trains an unsupervised Isolation Forest model, and serializes the trained artifacts (scaler.joblib and iso_forest_model.joblib) for real-time inference.

## 1. `train_isolation_forest_model()`
**Description:** Connects to the local SQLite database to fetch the training telemetry dataset, preprocesses and scales feature vectors, fits an Isolation Forest model, and persists the model and scaler artifacts to disk.

- **Inputs:** None (reads directly from os_doctor_train table in os_doctor.db).
- **Outputs:** None (side-effect function: saves scaler.joblib and iso_forest_model.joblib files to disk).

**Workflow:**
- Establishes a database engine via sqlalchemy and loads os_doctor_train table into a Pandas DataFrame.
- Applies explicit column naming matching expected_columns and removes non-feature metadata (id, timestamp).
- Cleans missing values (dropna()).
- Standardizes feature vectors using StandardScaler to ensure uniform feature weight distribution.Configures and fits IsolationForest hyperparameters ($n\_estimators=100$, $contamination=0.01$, $max\_samples=256$, $max\_features=7$).
- Exports scaler.joblib and iso_forest_model.joblib using joblib.dump().

# `i_forest_predict.py`
**Description:** Implements the real-time inference loop for OSDoctor's anomaly detection engine. It continuously pulls engineered telemetry data from the database, applies feature scaling, evaluates system behavior using the pre-trained Isolation Forest model, and records detected performance anomalies for downstream diagnostic analysis.

## 1. `flag_anomaly()`
**Description:** Runs an active monitoring loop (pulling every 5 seconds) that loads the saved Isolation Forest model and feature scaler to evaluate system health.

- **Inputs:** None (fetches incoming inference payloads dynamically from the SQLite database via get_inference_payload_predict(DB_PATH)).

- **Outputs:** None (side-effect function: logs anomaly status to console and appends detected anomaly payloads to the database via write_to_alerts_table()).

**Workflow:**

- Loads iso_forest_model.joblib and scaler.joblib into memory.

- Fetches incoming raw telemetry feature vectors and process metadata.

- Preprocesses data and scales the feature set while preserving the original raw metrics.

- Computes decision scores and checks for anomaly classification (predict == -1).

Upon anomaly detection, packages both raw (human-readable) and scaled metric payloads into the alerts table for the LLM explanation layer and dashboard.

# `groq_diagnosis.py`