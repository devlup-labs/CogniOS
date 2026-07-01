# FocusOS — Module Documentation

**Part of CogniOS | Adaptive Workload Understanding and System Optimization Engine**

---

## Table of Contents

1. [Module Overview](#1-module-overview)
2. [Workflow](#2-workflow)
3. [File Structure](#3-file-structure)
4. [Function Definitions](#4-function-definitions)
5. [Useful Telemetry Data](#5-useful-telemetry-data)
6. [Additional Information](#6-additional-information)

---

## 1. Module Overview

### What is FocusOS?

FocusOS is the **adaptive optimization layer** of CogniOS. Its core responsibility is to understand *what kind of work the user is currently doing* — not just which app is open — and dynamically tune the operating system's resource allocation to make that work feel faster and smoother.

Traditional OS schedulers are workload-agnostic. They don't know if the user is in a deep coding session, compiling a project, gaming, or on a video call. FocusOS bridges this gap by continuously inferring workload context from system telemetry and applying intelligent, context-aware optimizations.

> Instead of: *"What app is open?"*
> FocusOS asks: *"What kind of workload is happening right now?"*

### Workload Categories Detected

| Workload | Description |
|----------|-------------|
| `Coding` | IDE active, moderate CPU, low network, Python/Node processes |
| `Compiling` | Compiler active, high CPU, high disk I/O |
| `Gaming` | Game process dominant, high GPU/CPU, low network variance |
| `Video Call` | Zoom/Meet active, high network, moderate CPU |
| `Browsing` | Browser dominant, variable network, moderate CPU |
| `Idle` | Low CPU/RAM/disk, no dominant foreground process |

---

## 2. Workflow

### Training Phase

**Step 1 — Collect telemetry every second**

- **Metric Sourcing:** Relevant metrics are collected from Layer 1 and Layer 2.
- **In-Memory Buffer Storage:** A buffer may be implemented to eliminate the overhead of writing directly to the database tables every second.
- **Feature Classification:**
  - System features
  - Process features — a dedicated function is defined to fetch process metrics. To accurately compute the process creation rate, `asyncio` is used. This function accepts the local database path as its primary input argument.
  - Context features

**Step 2 — Generation of time-averaged statistics and final feature vector**

- **Sliding window execution:** A dedicated function is defined to calculate rolling statistical metrics.
- **Execution Interval:** This function is triggered strictly every 30 seconds utilizing `asyncio`.
- **Dataset Creation:** A 2D array encompassing all compiled feature vectors is generated to assemble the training dataset for the clustering model.
- **Feature Scaling:** Prior to passing the dataset to KMeans, the data is normalized using `StandardScaler` from `sklearn.preprocessing`. This ensures that all metrics carry a mathematically similar weightage during distance calculations.
- **Unsupervised Clustering:** The output of this training phase is a tracking array (`trained_array`) that assigns a definitive cluster integer to every input feature vector row.
- **Pseudo-Labeling:** To perform pseudo-labeling, the centroid of each individual cluster is evaluated. This is achieved by calculating the mathematical mean of every feature vector that has been mapped to that same cluster number within the `trained_array`.
- **Supervised Mapping Database:** A "trained database" is then constructed to store the original structural feature vectors, along with a column storing their corresponding mapped workload labels.
- **XGBoost Dataset Formulation:** For training the supervised XGBoost model, `x_train` is designated as the initial 2D telemetry array, while `y_train` is fed the calculated `trained_array` labels from KMeans.

### Testing with Actual Data

- On live telemetry data, the module evaluates the system state using `model.predict_proba()` to compute a probability distribution across the different workload categories.
- **Label Dictionary Mapping:** The mapping from cluster number to workload category is done via a predefined dictionary mapping.
- **Threshold:** If the prediction confidence score for any individual workload category exceeds **80%**, the optimization layer triggers to actively prioritize that specific process.

---

## 3. File Structure

```
focusos/
│
├── telemetry/
│   └── collector.py            # Reads psutil + /proc, emits 1-sec snapshots
│
├── windowing/
│   └── sliding_window.py       # Maintains a 120-sample rolling buffer
│
├── features/
│   └── feature_engineer.py     # Converts raw window → statistical feature vector
│
├── models/
│   ├── cluster_trainer.py      # KMeans training for unsupervised discovery
│   ├── label_mapper.py         # Maps cluster IDs → workload names (human step)
│   └── classifier.py           # XGBoost train + inference
│
├── optimization/
│   └── optimizer.py            # Applies nice(), cpu_affinity(), ionice() via psutil
│
├── explanation/
│   └── llm_explainer.py        # Builds LLM prompt from prediction + feature importance
│
├── dashboard/
│   └── dashboard_server.py     # Serves data to React frontend
│
├── utils/
│   └── process_utils.py        # Helper: get foreground app, detect compiler, etc.
│
├── models_saved/
│   ├── kmeans_model.pkl         # Saved KMeans model
│   └── xgboost_model.pkl        # Saved XGBoost classifier
│
└── main.py                     # Entry point: starts daemon loop
```

---

## 4. Function Definitions

### `collector.py`

```python
def collect_snapshot(conn) -> dict
```

**Purpose:** Collects one complete telemetry snapshot from `psutil` and `/proc` every second. Stores the snapshot into the shared SQLite database and returns it as a dict for the sliding window buffer. This is the heartbeat of FocusOS — everything downstream depends on this data.

```python
timestamp < (strftime('%s','now') - 1)
```

---

```python
def get_foreground_app() -> str
```

**Purpose:** Detects the currently focused window title using `xdotool`. Returns the lowercased application name string. Falls back to `'unknown'` if no window manager is available or the call fails.

```python
subprocess.check_output(['xdotool', 'getactivewindow'])
```

---

```python
def get_top_processes(n: int = 5) -> list[dict]
```

**Purpose:** Returns the top N processes sorted by CPU usage, and separately by memory usage. Each entry contains `pid`, `name`, `cpu_percent`, `memory_percent`, `num_threads`, `status`. Called every 5 seconds (Layer 2 telemetry). Only top-5 are stored to keep the database lean.

```python
psutil.process_iter(['pid','name','cpu_percent','memory_percent','num_threads','status'])
```

---

### `sliding_window.py`

```python
class SlidingWindowBuffer(maxlen: int = 120)
```

**Purpose:** Maintains a fixed-size FIFO deque of telemetry snapshots representing the last 2 minutes of system state (120 samples at 1/sec). When the buffer is full, the oldest entry is automatically dropped on each new addition. This is the temporal memory FocusOS reasons over.

```python
self.buffer = deque(maxlen=120)
```

---

```python
def add(self, snapshot: dict) -> None
```

**Purpose:** Appends a new telemetry snapshot to the buffer. If the buffer is already at `maxlen`, the oldest snapshot is evicted automatically by the deque. Called once per second by the daemon loop.

```python
self.buffer.append(snapshot)
```

---

```python
def is_ready(self) -> bool
```

**Purpose:** Returns `True` only when the buffer has accumulated exactly `maxlen` snapshots. FocusOS waits for a full 2-minute window before running its first inference. Prevents classification on incomplete data at startup.

```python
return len(self.buffer) == self.buffer.maxlen
```

---

```python
def get_window(self) -> list[dict]
```

**Purpose:** Returns a plain list copy of the current buffer contents, ordered oldest to newest. This copy is passed to `feature_engineer.py` for statistical feature extraction every 30 seconds.

```python
return list(self.buffer)
```

---

### `feature_engineer.py`

```python
def extract_features(window: list[dict]) -> dict
```

**Purpose:** Converts the 120-snapshot sliding window into a flat statistical feature vector. Computes mean, max, and variance for CPU, RAM, network, and process signals. Also sets binary context flags (`vscode_active`, `compiler_active`). The output dict is the direct input to the XGBoost classifier.

---

```python
def categorize_app(app_name: str) -> int
```

**Purpose:** Maps a raw foreground application name (window title string) to an integer category code used as a numerical feature in the ML model. Categories: `IDE=0`, `Browser=1`, `Game=2`, `Call=3`, `Terminal=4`, `Unknown=5`. Called inside `extract_features()`.

```python
if any(k in app_name for k in ['code', 'pycharm', 'vim']):
    return 0  # IDE
```

---

```python
def get_compiler_flag(window: list[dict]) -> int
```

**Purpose:** Scans the top process names across all 120 snapshots and returns `1` if any known compiler or build tool (`gcc`, `g++`, `make`, `clang`, `rustc`, `javac`, `cargo`) appeared in the top-5 CPU processes during the window. Returns `0` otherwise.

```python
compiler_tools = ['gcc', 'g++', 'make', 'clang', 'rustc', 'javac', 'cargo']
```

---

### `cluster_trainer.py`

```python
def train_kmeans(X: np.ndarray, n_clusters: int = 5) -> KMeans
```

**Purpose:** Trains a KMeans clustering model on collected feature vectors to discover natural workload behavior groups. Called once during the initial bootstrapping phase before any labels exist. Saves the fitted model and scaler to `models_saved/`. This is the unsupervised first step of the semi-supervised pipeline.

```python
model = KMeans(n_clusters=5, random_state=42, n_init=10)
model.fit(X_scaled)
```

---

```python
def assign_pseudo_labels(cluster_ids: np.ndarray, label_map: dict) -> list[str]
```

**Purpose:** Converts raw integer cluster IDs from KMeans output into human-readable workload label strings using a manually defined mapping (e.g. `{0: 'coding', 1: 'video_call', ...}`). This human labelling step is the bridge from unsupervised clustering to supervised classification.

```python
return [label_map.get(cid, 'unknown') for cid in cluster_ids]
```

---

```python
def save_pseudo_labeled_dataset(X: np.ndarray, labels: list[str], path: str) -> None
```

**Purpose:** Persists the pseudo-labeled feature matrix to disk as a CSV file. Each row is one 2-minute window's feature vector, with its assigned workload label as the final column. This dataset is later loaded by `classifier.py` to train XGBoost.

```python
df = pd.DataFrame(X, columns=FEATURE_NAMES)
df['label'] = labels
df.to_csv(path, index=False)
```

---

### `classifier.py`

```python
def train_classifier(X_train: np.ndarray, y_train: np.ndarray) -> XGBClassifier
```

**Purpose:** Trains an XGBoost multi-class classifier on the pseudo-labeled workload dataset. Uses 100 estimators, max depth 6, and learning rate 0.1. Saves the fitted model to `models_saved/xgboost_model.pkl`. Called once after pseudo-labels are generated, and can be retrained periodically.

```python
model = XGBClassifier(n_estimators=100, max_depth=6, learning_rate=0.1)
model.fit(X_train, y_train)
```

---

```python
def predict_workload(features: dict) -> tuple[str, float, dict]
```

**Purpose:** Runs a single real-time inference pass on a feature vector extracted from the current sliding window. Returns the predicted workload label, the confidence score for that label, and a dict of all class probabilities. Called every 30 seconds by the daemon loop.

```python
probs = model.predict_proba(X)[0]
label = WORKLOAD_LABELS[np.argmax(probs)]
confidence = probs[np.argmax(probs)]
```

---

```python
def get_feature_importances() -> dict
```

**Purpose:** Extracts and returns the feature importance scores from the trained XGBoost model as a `{feature_name: score}` dict. The top 3 features by importance are passed to the LLM explanation layer to generate a human-readable reason for the current workload prediction.

```python
return dict(zip(FEATURE_NAMES, model.feature_importances_))
```

---

### `optimizer.py`

```python
def apply_optimization(workload: str, confidence: float) -> None
```

**Purpose:** The action layer of FocusOS. Reads the detected workload and — only if confidence exceeds 80% — adjusts OS-level process scheduling by calling `nice()`, `cpu_affinity()`, and `ionice()` via psutil. Prioritizes relevant processes and deprioritizes background tasks. Logs all actions taken.

---

```python
def prioritize_process(proc_name: str, nice_val: int) -> bool
```

**Purpose:** Finds a running process by name substring match and sets its CPU scheduling priority using `psutil.Process.nice()`. Returns `True` if the process was found and updated, `False` if the process was not running or access was denied. Called internally by `apply_optimization()`.

```python
p = psutil.Process(pid)
p.nice(nice_val)
```

---

```python
def log_optimization_result(workload: str, confidence: float, actions: list[str]) -> None
```

**Purpose:** Writes the optimization event — workload label, confidence score, timestamp, and list of actions applied — to the `focusos_events` table in the shared CogniOS SQLite database. This log is consumed by the dashboard and by BlackBox for pre-crash workload reconstruction.

```python
cur.execute("""
    INSERT INTO focusos_events (timestamp, workload, confidence, actions_json)
    VALUES (?, ?, ?, ?)
""", (time.time(), workload, confidence, json.dumps(actions)))
```

---

### `llm_explainer.py`

```python
def generate_explanation(prediction: str, confidence: float, top_features: dict) -> str
```

**Purpose:** Builds a structured JSON prompt from the workload prediction and top XGBoost feature importances, then sends it to the configured LLM (Ollama local or API). Returns a 2-sentence plain-English explanation of why the current workload was detected. Result is displayed on the dashboard.

```python
prompt = {
    "prediction": prediction,
    "confidence": f"{confidence:.0%}",
    "important_features": [...top 3 features...]
}
return call_llm(system_prompt, json.dumps(prompt))
```

---

## 5. Useful Telemetry Data

FocusOS reads from the shared CogniOS Telemetry Collector. Below are the signals most relevant to FocusOS and the reasoning behind each.

### Layer 1: System Telemetry (Every 1 Second)

| Signal | Why FocusOS Needs It |
|--------|---------------------|
| `cpu_percent` | Primary indicator: coding ~30-50%, compiling ~80-100% |
| `cpu_per_core` | Distribution matters: compiler uses all cores, game pins 2-4 |
| `cpu_user` / `cpu_system` | System-heavy = kernel work; user-heavy = application |
| `cpu_iowait` | High iowait = compiling or heavy disk-bound workload |
| `mem_percent` | Gaming and video editing push RAM high; coding is moderate |
| `mem_cached` | High cache = file-heavy workload (compiling, video) |
| `disk_read_mbps` | Compiling reads many source files |
| `disk_write_mbps` | Build artifacts being written = strong compiling signal |
| `net_bytes_sent` / `net_bytes_recv` | High recv = streaming/video call; near-zero = offline coding |
| `process_count` | Many new processes = build system spawning (make, cargo) |
| `context_switches` | High = many competing threads (compiling, game engine) |
| `load_1m` / `load_5m` | Sustained high load = compile or gaming; spike = anomaly |

### Layer 2: Top Process Telemetry (Every 5 Seconds)

| Signal | Why FocusOS Needs It |
|--------|---------------------|
| Top-5 process `name` | gcc/g++/make = compiling; zoom = video call; code = coding |
| Top process `cpu_percent` | One process at 90% = game; distributed = compile |
| Top process `memory_percent` | Memory-hungry process reveals workload type |
| `num_threads` | Many threads = parallel compile jobs or game engine |
| `read_bytes` / `write_bytes` | Compiler writes output; game engine streams assets |
| `status` | Zombie accumulation signals build system issues |

### Layer 3: Process Metadata (Store Once per New Top-5 Entry)

| Signal | Why FocusOS Needs It |
|--------|---------------------|
| `exe` (executable path) | `/usr/bin/gcc` is unambiguous compiling; `/opt/zoom/zoom` = video call |
| `cmdline` | `python train.py` = ML work; `make -j8` = compiling |
| `nice` (priority) | Know baseline before FocusOS modifies it (needed for rollback) |
| `create_time` | Long-lived compiler process = active sustained build |

### Layer 4: Deep Diagnostics (Anomaly Only — from OS Doctor)

| Signal | Relevance |
|--------|-----------|
| `cpu_affinity` | Avoid double-setting if process is already pinned |
| `io_priority` | Know existing I/O class before overriding |
| `open_files` | Compiler opens many `.c`/`.h` files — confirming signal |
| `net_connections` | Zoom/Teams keeps multiple open sockets — video call signal |

### Final Feature Vector Passed to XGBoost

```python
[
    mean_cpu,                  # Statistical mean of CPU over 2 min window
    max_cpu,                   # Peak CPU during window
    cpu_variance,               # Low variance = sustained load; high = bursty
    mean_ram,                  # Mean memory usage %
    ram_growth_rate,            # RAM trending up → memory-intensive workload
    mean_net_upload,            # Video call = high upload
    mean_net_download,          # Streaming = high download
    net_variance,               # Low = steady call; high = burst downloads
    mean_process_count,         # Build systems spawn many processes
    mean_thread_count,          # Parallel compiler = many threads
    top_proc_cpu_share,         # 1 process at 90% = game; distributed = compile
    foreground_app_category,    # IDE=0, Browser=1, Game=2, Call=3, Terminal=4
    compiler_active,            # 1 if gcc/make/cargo seen in top processes
    vscode_active,               # 1 if VSCode is foreground app
]
```

---

## 6. Additional Information

### 6.1 Why Semi-Supervised (KMeans → XGBoost)?

| Approach | Problem |
|----------|---------|
| Pure supervised | Needs labeled data — hard to collect at scale |
| CNN on heatmap | Needs GPU, hard to explain, overkill for tabular data |
| Pure KMeans | Cannot generalize to new unseen patterns at inference time |
| **KMeans → Pseudo-labels → XGBoost** | No GPU, fast inference, explainable, works on small data |

### 6.2 Why XGBoost Over Other Classifiers?

| Property | Why It Matters for FocusOS |
|----------|---------------------------|
| Tabular data performance | Features are statistical — XGBoost excels here |
| Small dataset | Works well with hundreds to thousands of samples |
| Fast inference | Less than 1ms prediction, critical for 30-second real-time cycle |
| No GPU required | Runs on any Linux machine in the CogniOS target environment |

### 6.3 Integration with Other CogniOS Modules

| Module | Integration Point |
|--------|------------------|
| **Telemetry Collector** | FocusOS reads from the shared SQLite telemetry database (Layers 1-3) |
| **OS Doctor** | OS Doctor flags CPU/Memory > 90% anomalies so FocusOS avoids misclassifying a runaway process as "compiling" |
| **BlackBox** | FocusOS writes its workload timeline to the events table; BlackBox uses this to reconstruct pre-crash workload context |
| **Dashboard** | FocusOS pushes workload, confidence, probabilities, actions, and LLM explanation via WebSocket to the React frontend |

