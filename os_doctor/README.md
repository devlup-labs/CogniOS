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

# `featuring.py`

This module bridges the gap between transactional database storage and in-memory multi-dimensional math. It queries the running SQLite database in WAL mode, extracts the latest historical sliding window, standardizes missing rows, and computes derived statistical features for the anomaly detection pipeline.

---

### 1. `extract_and_engineer_system`

- **Description:** Queries the running SQLite database safely in WAL mode to extract the latest rolling historical sliding window of process telemetry rows.
- **Input:**
  - `DB_PATH` (str): Absolute path to the centralized SQLite database.
  - `window_size` (int): Number of historical rows to fetch (default: 120 samples / 2 minutes).
- **Output:**
  - `sys_vec`: One single-rowed vector containing feature-engineered data of rolling 2-min window with gradients and rolling averages of system telemetry collection.

  ---


### 2. `extract_and_engineer_processes`

- **Description:** Queries the running SQLite database safely in WAL mode to extract the latest rolling historical sliding window of process telemetry rows.
- **Input:**
  - `DB_PATH` (str): Absolute path to the centralized SQLite database.
  - `window_size` (int): Number of historical rows to fetch (default: 24 samples / 2 minutes).
- **Output:**
  - `cpu_vec and ram_vec`: Two single-rowed vectors containing feature-engineered data of rolling 2-min window with gradients and rolling averages.

---

### 3. `build_unified_vectors`

- **Description:** Combines the three individual vectors recieved above and handles what to feed into i_forest.py and what to feed to llm_layer.
- **Input:**
  - `sys_vec, ram_vec, cpu_vec` (pd.DataFrame): Raw process telemetry DataFrame containing compressed or stringified JSON arrays.
- **Output:**
  - `i_forest_features_df, metadata_payload`: i_forest_features_df is the pd DataFrame that goes into the i_forest model
  metadata_payload is the metadata of processes such as 'pid', 'name', 'ppid' etc
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

# `llm_layer.py`