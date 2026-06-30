OSDoctor
Real-Time Intelligent Operating System Monitoring & Anomaly Detection System

Project Documentation

1. Introduction

OSDoctor is an intelligent observability system that continuously monitors operating system telemetry, detects abnormal system behavior using machine learning, identifies the likely root cause, and explains the issue in natural language. Its objective is to answer the question: “Why is my laptop slow right now?”

2. Objectives

- Monitor real-time system telemetry.
- Detect system anomalies automatically.
- Identify causes of performance issues.
- Detect CPU, memory, disk, and process-related faults.
- Explain issues in simple, human-readable language.
- Provide actionable alerts and recommendations.


3. System Architecture

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

4. File Structure

```text
os_doctor/
│── _init_.py             # Marks the directory as a Python package
│── featuring.py           # Feature engineering and preprocessing
│── i_forest.py             # Isolation Forest model implementation
│── llm_layer.py           # LLM integration and response generation
│── streamlit.py           # Streamlit web application
│── README.md          # Project overview and setup guide
```


5. Function Documentation
6. Feature Engineering

## Module Overview
The `feature.py` script serves as the core mathematical transformation layer for the **OS Doctor Anomaly Engine**. Its primary responsibility is to bridge the gap between low-frequency/high-frequency transactional data stored in the local SQLite database and the high-dimensional, uniform matrices required by the **Isolation Forest** machine learning pipeline.

The module continuously processes a rolling **2-minute sliding window** of system and process performance telemetry, cleans missing data, applies advanced statistical transformations (rolling averages, gradients, and rates of change), and generates a unified vector payload for real-time anomaly detection.

---

## Libraries Used

### 1 pandas
We use pandas for faster vector calculations leveraging it's built in functions like rolling(), shift() and many more.

### 2 sqlite3
We use sqlite3 library to handle the telemetry database created prior.

### 3 json
We use json library to parse the json object created in layer2.

## Core Telemetry Pipeline Alignment Matrix

Because our telemetry collection infrastructure drops metrics down at asynchronous cadences, this script enforces chronological structure across distinct dimensional boundaries:

| Data Layer | Source Table | DB CADENCE | Target Window Scope | Base Matrix Shape |
| :--- | :--- | :--- | :--- | :--- |
| **Layer 1: System-Wide** | `system_telemetry` | Every 1 Second | Last 120 Seconds | $120 \times \text{metrics}$ |
| **Layer 2: Top Processes**| `process_telemetry`| Every 5 Seconds | Last 120 Seconds | $24 \times \text{metrics}$ |

---

## Detailed Function Breakdown

The feature engineering layer executes its operations deterministically through four functions:

### 1. `extract_and_engineer_system(db_path)`
* **Intent:** Pulls the high-frequency global system indicators (Layer 1) and translates flat numbers into directional trends.
* **Mechanism:** * Queries the last **120 rows** from the `system_telemetry` table ordered by timestamp, reversing them in memory to form a clean chronological left-to-right timeline.
  * Utilizes `pandas` to calculate moving windows (e.g., 30-second rolling averages for CPU consumption) to smooth out short-term spikes.
  * Calculates **I/O Storm Rates** and **Scheduler Context Switch Acceleration** by taking the difference between the most current metric entry and past rows (`df['metric'] - df['metric'].shift(1)`).
* **Output Shape:** A flat, single-row pandas DataFrame: `[1 × num_system_features]`.

### 2. `extract_and_engineer_processes(db_path)`
* **Intent:** Unpacks the denormalized JSON arrays for the Top 5 CPU and Top 5 RAM consumers, correcting the shape mismatch and handling the "cold start" baseline issue.
* **Mechanism:**
  * Queries the last **24 rows** (representing 120 seconds of 5-second steps) from the `process_telemetry` table.
  * **The Chronological Upsampling Transform:** Because the database contains 24 rows but the final matrix requires a 1-second grid alignment, it upsamples the process rows into a 120-second array using forward-filling (`.ffill()`). This ensures data points match at every single second ticker.
  * **Zero-Imputation (Cold Start Fix):** If a rogue process bursts into the Top 5 list halfway through the window, its missing history blocks are auto-populated with `0.0` instead of letting `NaN` values break the mathematical tracking loops.
  * Computes process acceleration curves and resource gradients ($\Delta \text{Metric} / \Delta t$).
* **Output Shape:** Two independent flat, single-row arrays: `[1 × num_cpu_features]` and `[1 × num_ram_features]`.

### 3. `build_unified_vector(sys_vec, cpu_vec, ram_vec)`
* **Intent:** Combines separate feature spaces into a single high-dimensional coordinate vector.
* **Mechanism:**
  * Takes the horizontal outputs generated by the system and process computation layers.
  * Executes an optimized columnar concatenation step (`pandas.concat(axis=1)`) to stitch the arrays together.
  * Enforces a rigid, static schema definition so that column indexes never drift, ensuring the input dimensions exactly match what the downstream Isolation Forest expects.
* **Output Shape:** A single, high-dimensional flat vector row: `[1 × total_combined_features]`.

### 4. `get_inference_payload(db_path)`
* **Intent:** Serves as the centralized public orchestrator function called directly by the core daemon script loop.
* **Mechanism:**
  * Acts as a non-blocking execution gatekeeper.
  * First runs a safety health check on the database capacity. If the background collectors haven't yet logged the baseline buffer of 120 system records, this function gracefully exits returning `None`, preventing the ML models from calculating false positives on partial windows.
  * Executes functions 1, 2, and 3 sequentially completely in-memory, then passes the finalized ready vector row directly down to the machine learning execution loop (`i_forest.py`).
* **Output:** An inference-ready `pandas.DataFrame` row or `None`.

7. Machine Learning Model
8. LLM Explanation Layer
9. Dashboard
10. Installation
11. Future Scope