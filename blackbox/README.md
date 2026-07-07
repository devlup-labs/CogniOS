# BlackBox Module — CogniOS

> **"Airplane ka black box"** — continuously record karta rehta hai, crash/freeze ke baad replay karke batata hai exactly kya hua tha aur kyun.

---

## 1. Module Overview

BlackBox is CogniOS's **flight recorder and forensic analysis engine**. It answers one core question:

> _"My system froze/crashed — what happened in the 30 minutes before it?"_

### What BlackBox is

- A real-time telemetry recorder (rolling 30-minute window)
- An anomaly detection engine (Z-score + Isolation Forest)
- A root-cause explanation system (Correlation Engine + LLM)

### Core pipeline

```
Layer 1/2/3/4 Telemetry
        ↓
Rolling Event Store (last 30 min only)
        ↓
Heartbeat System (crash/freeze detection)
        ↓
Feature Engineering (120 rows → 1 feature vector)
        ↓
Z-score Detector (sudden spikes + slow drift)
        ↓
Isolation Forest (multi-metric anomaly confirmation)
        ↓
Rule Engine (deterministic backup checks)
        ↓
Correlation Engine (CAUSE → EFFECT chain)
        ↓
Replay Timeline
        ↓
LLM Explanation (human-readable root cause)
        ↓
Dashboard Alert
```

---

## 2. File Structure

```
blackbox/
├── recorder.py           # Rolling event store — writes + prunes telemetry
├── heartbeat.py          # Crash/freeze detection via heartbeat timestamps
├── feature_engineering.py # Converts raw DB rows → statistical feature vector
├── zscore_detector.py    # Z-score + slope (trend) based anomaly detector
├── anomaly_model.py      # Isolation Forest wrapper (sklearn)
├── rule_engine.py        # Deterministic threshold-based checks (backup)
├── correlation.py        # Builds CAUSE → EFFECT event chains
├── replay.py             # Reconstructs timeline from rolling window
├── nl_query.py           # Natural language query interface over crash data
```

```
utils/
├── config.py             # All BlackBox config constants
├── db.py                 # SQLite connection + schema helpers
└── helpers.py            # rate_mb_s() and other shared utilities
```

---

## 3. Function Definitions

### `recorder.py`

```python
def write_telemetry(conn, metrics: dict) -> None
```

**Purpose:** Inserts one Layer 1 metrics row into the rolling telemetry store.
Calls `prune_old_records()` after every write to enforce the 30-minute window.

```python
def prune_old_records(conn) -> None
```

**Purpose:** Deletes rows older than `BLACKBOX_WINDOW_SEC` (default 1800s).

```sql
DELETE FROM telemetry WHERE timestamp < (strftime('%s','now') - 1800)
```

---

### `heartbeat.py`

```python
def update_heartbeat(conn) -> None
```

**Purpose:** Updates a single-row heartbeat table with `time.time()` every second.
If the daemon crashes, the last saved timestamp persists in SQLite.

```python
def check_crash_on_startup(conn) -> tuple[bool, float]
```

**Purpose:** Called once at daemon startup. Reads last heartbeat timestamp.
Returns `(crash_detected: bool, gap_seconds: float)`.
If `graceful_shutdown = 0` AND `gap > BLACKBOX_CRASH_GAP_SEC` → crash was detected.
Note: Uses graceful shutdown flag approach (not hardcoded gap > 10s — that was arbitrary).
Triggers `replay.py` to reconstruct the pre-crash timeline.

---

### `feature_engineering.py`

```python
def extract_feature_vector(rows: list[dict]) -> list[float]
```

**Purpose:** Converts the last 120 raw telemetry rows (2 minutes × 1 sample/sec)
into a single statistical feature vector for anomaly detection.

**Input:** 120 dicts from `layer1_system` table
**Output:**
`[mean_cpu, max_cpu, cpu_growth_rate, cpu_variance, mean_ram, memory_growth_rate,   	disk_spike_frequency, context_switch_rate]`

Why statistical summary and not raw rows?

- Isolation Forest is **not a time-series model** — it takes a single point in feature space
- Z-score also operates on aggregated values
- 8 features instead of 120×8=960 raw values = faster + less noise

---

### `zscore_detector.py`

```python
class ZScoreDetector:
    def __init__(self,
                 zscore_window=1800,   # seconds of rolling baseline
                 trend_window=600,     # seconds for slope calculation
                 sustained_sec=30,     # spike must last this long
                 z_threshold=2.8,
                 slope_threshold=0.003,
                 sustained_ratio=0.6)
```

```python
    def update(self, val: float) -> None
```

**Purpose:** Appends new reading to all internal deques (zscore, trend, sustained).

```python
    def check(self, val: float, metric_name: str, unit: str) -> list[dict]
```

**Purpose:** Runs three independent checks and returns list of detected issues.

**Check 1 — Z-score (sudden spike):**

```
Z = (current_value - rolling_mean) / rolling_std
If |Z| > 2.8 AND spike sustained for 30s → ALERT
```

Catches: CPU suddenly 35% → 95%

**Check 2 — Slope/Trend (slow drift):**

```python
slope = np.polyfit(time_axis, values, 1)[0]  # linear regression
If slope > 0.003 %/sec → ALERT (memory leak pattern)
```

Catches: Memory slowly 40% → 80% over 2 hours (Z-score misses this)
Bonus: predicts `ETA to critical = (90 - current) / slope / 60` minutes

**Check 3 — Sustained filter (false positive prevention):**

```
If < 60% readings above threshold in last 30s → skip (compilation burst)
If ≥ 60% readings above threshold → real anomaly
```

Prevents: Short CPU bursts from `gcc` compilation triggering false alerts

**Why Z-score alone is not enough:**

- Rolling window adapts to slow drift → memory leak goes undetected
- Single-metric check → misses multi-metric correlations
- Solution: Z-score + Slope + Isolation Forest together

---

### `anomaly_model.py`

```python
def train(normal_feature_vectors: np.ndarray) -> IsolationForest
```

**Purpose:** Trains Isolation Forest on normal telemetry data only.
`contamination=0.05` means we expect ~5% of data to be anomalous.

```python
def predict(model: IsolationForest, feature_vector: list) -> tuple[int, float]
```

**Purpose:** Returns `(label, score)` where:

- `label = 1` → normal
- `label = -1` → anomaly
- `score` → negative = more anomalous

**How Isolation Forest works:**
Isolation Forest is an **unsupervised algorithm that detects anomalies in a feature space** — NOT a time-series model.

Core intuition:

- Normal points cluster together → many random splits needed to isolate them
- Anomaly points are sparse → isolated with very few splits
- Points isolated in fewer splits = higher anomaly score

```
Normal [cpu=35, mem=55, disk=2]:  deep in tree → many splits → normal
Anomaly [cpu=40, mem=40, disk=40, net=40]: shallow in tree → few splits → anomaly
```

Key advantage over Z-score: detects **multi-metric combinations** that are individually normal but collectively anomalous.

Example: `CPU=40%, MEM=40%, DISK=40%, NET=40%` — each metric looks fine individually, but this combination never appears in normal usage .

---

### `rule_engine.py`

```python
def check_rules(metrics: dict) -> list[dict]
```

**Purpose:** Deterministic backup checks — always runs alongside ML models.
Catches obvious anomalies even before warmup period ends.

```python
RULES = [
    {"condition": lambda m: m["cpu"] > 95,                   "alert": "cpu_critical"},
    {"condition": lambda m: m["thread_growth_rate"] > 200,   "alert": "thread_explosion"},
    {"condition": lambda m: m["zombie_count"] > 10,           "alert": "zombie_buildup"},
    {"condition": lambda m: m["memory_growth_continuous"],    "alert": "memory_leak"},
]
```

Why rule engine alongside ML?

- ML models need warmup period (60s) → rules work from second 1
- Rules are 100% deterministic → never fail unexpectedly
- Double detection = higher confidence alerts

---

### `correlation.py`

```python
def build_event_chain(events: list[dict]) -> list[dict]
```

**Purpose:** Takes raw timestamped events and builds a CAUSE → EFFECT chain
by correlating events that occurred close together in time.

Example output:

```
Chrome opened (10:01)
      ↓
Renderer processes +12 (10:02)
      ↓
Thread count +340 in 60s (10:03)
      ↓
CPU saturation 87% (10:04)
      ↓
Isolation Forest: ANOMALY -1 (10:05)
      ↓
System freeze detected (10:05)
```

```python
def telemetry_to_events(rows: list[dict]) -> list[dict]
```

**Purpose:** Converts raw telemetry rows into discrete events with type + timestamp.

```python
{"type": "cpu_spike", "time": "10:03:45", "detail": "cpu jumped to 87%"}
```

---

### `replay.py`

```python
def replay(conn, crash_time: float, window_minutes: int = 30) -> list[dict]
```

**Purpose:** Fetches all telemetry rows from `crash_time - window_minutes` to `crash_time`.
Returns ordered list for dashboard timeline visualization.

```python
def generate_narrative(events: list[dict], anomaly_type: str) -> str
```

**Purpose:** Formats the event chain into a structured JSON for LLM input.

---

### `nl_query.py`

```python
def query(conn, question: str) -> str
```

**Purpose:** Accepts free-text questions about crash data and returns answers
by querying SQLite + formatting context for LLM.

Example:

```
Input:  "Which process caused the freeze at 10:05?"
Output: "Chrome (PID 1823) spawned 340 additional threads between 10:01-10:04,
         causing CPU saturation that led to the system freeze."
```

---

## 4. Useful Telemetry Data

BlackBox consumes data from all 4 collector layers:

### From `layer1_system` (Layer 1 — every 1s)

| Column              | Use in BlackBox                         |
| ------------------- | --------------------------------------- |
| `cpu_usage_percent` | Primary Z-score metric, spike detection |
| `memory_percent`    | Memory leak slope detection             |
| `disk_read_mb_s`    | I/O storm detection                     |
| `net_rate_mb_s`     | Network exfiltration detection          |
| `cpu_ctx_switches`  | Scheduler congestion (feature vector)   |
| `total_processes`   | Thread explosion detection              |
| `zombie_processes`  | Zombie accumulation rule check          |
| `load_avg_1`        | Scheduler load feature                  |
| `swap_percent`      | Memory pressure feature                 |

### From `layer2_top_processes` (Layer 2 — every 5s)

| Column        | Use in BlackBox                                |
| ------------- | ---------------------------------------------- |
| `pid`, `name` | Identify culprit process in correlation engine |
| `cpu_percent` | Which process caused CPU spike                 |
| `rss_memory`  | Which process is leaking memory                |
| `timestamp`   | Timeline correlation                           |

### From `process_metadata` (Layer 3 — on first seen)

| Column        | Use in BlackBox                        |
| ------------- | -------------------------------------- |
| `cmdline`     | What exact command was running         |
| `exe_path`    | Where executable came from             |
| `username`    | Who launched the process               |
| `create_time` | When process started relative to crash |

### From `process_diagnostics` (Layer 4 — on anomaly)

| Column             | Use in BlackBox                          |
| ------------------ | ---------------------------------------- |
| `open_files_count` | File handle leak detection               |
| `thread_details`   | Which threads were consuming CPU         |
| `net_connections`  | Active network connections at crash time |
| `trigger_reason`   | Why Layer 4 was triggered                |

### Rolling window SQL

```sql
-- Fetch last 2 minutes for feature extraction
SELECT cpu_usage_percent, memory_percent,
       disk_read_mb_s, net_rate_mb_s,
       total_processes, cpu_ctx_switches
FROM layer1_system
ORDER BY timestamp DESC
LIMIT 120;

--Trim to 30-minute window
DELETE FROM telemetry
WHERE timestamp < (strftime('%s', 'now') - 1800);
```

---

## 5. Additional Info

### Config values (from `utils/config.py`)

```python
# BlackBox — all tunable from one place (mentor requirement)
BLACKBOX_WINDOW_SEC      = 1800   # rolling window duration
BLACKBOX_WARMUP_SEC      = 60     # seconds before detection starts
BLACKBOX_Z_THRESHOLD     = 2.8    # standard deviations
BLACKBOX_SLOPE_THRESHOLD = 0.003  # %/sec rising = suspicious
BLACKBOX_SUSTAINED_SEC   = 30     # spike must last this long
BLACKBOX_SUSTAINED_RATIO = 0.6    # 60% readings must be above threshold
BLACKBOX_TREND_WINDOW    = 600    # 10 min for slope calculation
```

### Key design decisions

**Why SQLite over other storage?**
Lightweight, local, crash-resistant (data survives daemon crash), queryable via SQL, replay-friendly.

**Why rolling 30-minute window?**
30 minutes of pre-crash context is sufficient for root-cause analysis. Longer window = more disk usage with diminishing returns.

**Why Isolation Forest and not supervised model?**
No labeled anomaly dataset exists initially. IF is unsupervised — trained on normal data only, no labels needed.

**Why Z-score threshold 2.8 and not 3.0?**
3.0 is the classic threshold but at 3.0, a developer's laptop (higher baseline CPU) barely crossed the threshold for genuine spikes. 2.8 gives slightly better sensitivity while keeping false positives low with the sustained filter.

---

## 6. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Linux System (laptop)                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ psutil + /proc
                      ▼
┌─────────────────────────────────────────────────────────────┐
│         Telemetry Collector — collectors/layer1_system.py   │
│                      every 1 second                          │
└──────────────┬──────────────────────┬───────────────────────┘
               │                      │
               ▼                      ▼
┌──────────────────────┐   ┌──────────────────────────────────┐
│  cognios_telemetry   │   │     blackbox/blackbox.db          │
│  .db  (permanent)    │   │   (rolling 30-min window only)    │
│                      │   │                                   │
│  layer1_sys          │   │   blackbox_telemetry              │
│  top_cpu_telemetry   │   │   blackbox_heartbeat              │
│  top_ram_telemetry   │   └──────────────┬─────────────────── ┘
│  process_metadata    │                  │
│  process_diagnostics │                  ▼
│                      │   ┌──────────────────────────────────┐
│  OS Doctor ──────────┤   │        BlackBox Module            │
│  FocusOS ────────────┤   │                                   │
│  Research Engine ────┘   │  recorder.py                      │
│                           │  heartbeat.py                     │
└──────────────────────┘   │  feature_engineering.py           │
                           │  zscore_detector.py               │
                           │  rule_engine.py                   │
                           │  anomaly_model.py                 │
                           │  correlation.py                   │
                           │  replay.py                        │
                           └──────────────┬─────────────────── ┘
                                          │
                                          ▼
                           ┌──────────────────────────────────┐
                           │       Streamlit Dashboard         │
                           │  Timeline · Alerts · NL Query     │
                           └──────────────────────────────────┘
```

### Why two separate databases?

| `cognios_telemetry.db`                      | `blackbox/blackbox.db`                |
| ------------------------------------------- | ------------------------------------- |
| Permanent — never pruned                    | Rolling window — last 30 min only     |
| All Layer 1/2/3/4 data                      | Only BlackBox-relevant metrics        |
| Read by OS Doctor, FocusOS, Research Engine | Read only by BlackBox                 |
| Grows indefinitely                          | Max ~1800 rows (1 per second × 1800s) |

---

## 7. Missing + Updated Function Definitions

### `recorder.py` — additional functions

```python
def get_blackbox_conn() -> sqlite3.Connection
```

**Purpose:** Opens and returns a connection to `blackbox/blackbox.db` with WAL mode for crash-safe writes.  
**Input:** None  
**Output:** `sqlite3.Connection`

```python
def get_recent_rows(conn, n: int = 120) -> list[dict]
```

**Purpose:** Returns last `n` rows from `blackbox_telemetry`, ordered oldest-first.  
**Input:** `conn`, `n` (default 120 = last 2 minutes)  
**Output:** `list[dict]` — each dict has column names as keys  
**Used by:** `feature_engineering.py`, `correlation.py`

```python
def get_window_rows(conn, start_time: float, end_time: float) -> list[dict]
```

**Purpose:** Returns all rows between two Unix timestamps for crash replay.  
**Input:** `conn`, `start_time` (Unix float), `end_time` (Unix float)  
**Output:** `list[dict]` ordered by timestamp ASC  
**Used by:** `replay.py`

```python
def row_count(conn) -> int
```

**Purpose:** Returns total number of rows currently in `blackbox_telemetry`.  
**Input:** `conn`  
**Output:** `int`

---

### `heartbeat.py` — updated with graceful shutdown flag

> **Mentor feedback:** "Why should we have gap only 10 seconds?"
>
> Hardcoded `gap > 10s` was arbitrary — HDD systems take 20+ seconds to reboot causing false positives. We use a **graceful shutdown flag** instead. Gap is only a fallback for SIGKILL/power cuts.

```python
def mark_graceful_shutdown(conn) -> None
```

**Purpose:** Sets `graceful_shutdown = 1` flag. Must be called in daemon's SIGTERM/SIGINT handler.  
**Input:** `conn`  
**Output:** None  
**Note:** If NOT called (crash/SIGKILL/power cut), flag stays 0 → crash detected on next startup.

```python
def check_crash_on_startup(conn) -> tuple[bool, float]
```

**Purpose:** Called once on daemon startup to detect whether previous session ended in a crash.  
**Input:** `conn`  
**Output:** `(crash_detected: bool, gap_seconds: float)`

**Detection logic (priority order):**

1. `graceful_shutdown = 1` → normal shutdown, no crash
2. `graceful_shutdown = 0` AND `gap > BLACKBOX_CRASH_GAP_SEC` → crash detected
3. Always resets flag to 0 for the next session

**In daemon signal handler:**

```python
def handle_signal(sig, frame):
    global running
    running = False
    mark_graceful_shutdown(bb_conn)   # ← required for correct crash detection
    print("[CogniOS] Graceful shutdown.")
```

---

### `anomaly_model.py` — additional functions

```python
def anomaly_severity(score: float) -> int
```

**Purpose:** Converts raw Isolation Forest `decision_function` score to a 0–100 severity integer for dashboard.  
**Input:** `score` (float — more negative = more anomalous)  
**Output:** `int` between 0 and 100  
**Example:** score=-0.3 → severity=80

```python
def save_model(model: IsolationForest, path: str = "blackbox/if_model.pkl") -> None
```

**Purpose:** Saves trained model to disk using pickle.  
**Input:** trained `IsolationForest`, file path  
**Output:** None

```python
def load_model(path: str = "blackbox/if_model.pkl") -> IsolationForest
```

**Purpose:** Loads a previously saved model from disk.  
**Input:** file path  
**Output:** `IsolationForest`

---

## 8. How to Run

### Prerequisites

```bash
pip install psutil numpy scikit-learn
```

### First time setup

```bash
cd CogniOS

python3 -c "
import sys
sys.path.insert(0, '.')
from blackbox.recorder import get_blackbox_conn, create_blackbox_table
from blackbox.heartbeat import create_heartbeat_table

conn = get_blackbox_conn()
create_blackbox_table(conn)
create_heartbeat_table(conn)
print('BlackBox DB initialised at blackbox/blackbox.db')
"
```

### Run full daemon

```bash
python3 cognios_as_daemon.py
```

### Run BlackBox integration test only

```bash
python3 -c "
import sys, time
sys.path.insert(0, '.')
from collectors.layer1_system import collect_layer1_metrics
from blackbox.recorder import get_blackbox_conn, create_blackbox_table, write_telemetry, row_count
from blackbox.heartbeat import create_heartbeat_table, update_heartbeat
from blackbox.zscore_detector import ZScoreDetector
from blackbox.rule_engine import check_rules

conn = get_blackbox_conn()
create_blackbox_table(conn)
create_heartbeat_table(conn)
detector = ZScoreDetector()

for i in range(40):
    m = collect_layer1_metrics()
    write_telemetry(conn, m)
    update_heartbeat(conn)
    detector.update(m.get('cpu_usage_percent', 0))
    check_rules(m)
    time.sleep(0.1)

print('Rows in blackbox.db:', row_count(conn))
print('Integration test PASSED ✅')
"
```

### Generate Isolation Forest training data

```bash
sudo apt install stress-ng
python3 cognios_as_daemon.py &

stress-ng --cpu 8 --timeout 60s              # cpu_overload
sleep 30
stress-ng --vm 4 --vm-bytes 80% --timeout 60s   # memory_pressure
sleep 30
stress-ng --hdd 4 --timeout 60s             # disk_io_stress
sleep 30
stress-ng --pthread 100 --timeout 60s       # thread_explosion
```

---

## 9. Improvements & Future Work

### High priority (low effort)

**WAL mode for crash-safe writes** (2 lines of code):

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
```

Default SQLite write mode can lose the last few seconds of telemetry if daemon crashes mid-write. WAL mode writes to a separate file first — crash during write means no data loss.

**Continuous anomaly severity score:**
Replace binary `-1/1` output with 0–100 score using `decision_function()`. Dashboard can show gradual escalation (40→60→80→100) instead of a sudden binary alert.

### Medium priority

**Per-metric Isolation Forest models:**
One combined model learns a confused boundary across all metrics. Separate models per metric with different `contamination` rates give better detection accuracy.

**Exponential Moving Average (EMA) baseline:**
Replace simple rolling mean with EMA for faster adaptation to regime changes, reducing false positives when user starts a new heavy workload.

### Low priority (research phase)

**LSTM Autoencoder hybrid:**
LSTM captures temporal dependencies that Isolation Forest cannot — sequential patterns like memory growing over 2 hours. A hybrid approach (LSTM reconstruction error fed into Isolation Forest) significantly improves detection. Requires TensorFlow and more training data.

### Known limitations

| Limitation                             | Impact                                     | Workaround                              |
| -------------------------------------- | ------------------------------------------ | --------------------------------------- |
| Z-score slow drift blind spot          | Memory leaks over 2+ hours may not trigger | Slope detector partially covers this    |
| IF needs warmup data                   | No anomaly detection for first 60s         | Rule Engine covers warmup period        |
| `stress-ng` training data is synthetic | Real anomalies may differ                  | Collect real anomaly data and retrain   |
| SIGKILL bypasses graceful flag         | Gap fallback may miss very fast restarts   | `BLACKBOX_CRASH_GAP_SEC = 30` as buffer |
