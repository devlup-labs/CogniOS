# BlackBox Module — CogniOS

> **CogniOS Observability Suite — Flight Recorder & Post-Crash Forensics Subsystem**
> "Airplane ka black box" — continuously records telemetry, and after a crash/freeze, replays exactly what happened and why.

---

## 1. Module Overview

BlackBox is CogniOS's **lightweight, crash-resilient telemetry recorder and post-crash forensic analyzer**. It answers one core question:

> _"What happened to the system in the 30 minutes leading up to a crash, freeze, or hard power-off?"_

### What BlackBox is

- A real-time telemetry recorder (rolling 30-minute SQLite window, WAL mode)
- A dual-layer crash/freeze detector (in-process heartbeat + systemd journal inspection)
- A dynamic-baseline anomaly detector (Z-score spikes + linear-regression drift, no ML training required)
- An LLM-powered forensic analyst (Groq API, natural-language Q&A over the reconstructed timeline)

### Core pipeline

```
Linux System Metrics
        ↓
cognios_as_daemon.py (1 Hz telemetry tick)
        ↓
blackbox/recorder.py → blackbox.db (rolling 30-min window, WAL mode)
        ↓
heartbeat.py (every tick: update_heartbeat)
        │
        └─ On daemon startup: full_crash_check()
                ├── Heartbeat gap check
                └── systemd journalctl check
                        ↓
                (if crash detected)
                        ↓
                replay.py → baseline calc, Z-score events, event chain
                        ↓
                nl_query.py → Groq LLM forensic explanation
```

---

## 2. File Structure

```
blackbox/
├── recorder.py     # SQLite WAL connection, schema, writes, pruning, thread locks
├── heartbeat.py     # Daemon liveness tracking, crash/freeze detection (heartbeat + journalctl)
├── replay.py         # Timeline reconstruction, Z-score/drift event detection, LLM context builder
├── nl_query.py       # Groq API interface — interactive natural-language forensic Q&A
```

```
CogniOS/                       # project root
├── config.py                  # All config constants, including BlackBox's
├── .env                       # GROQ_API_KEY, etc.
└── cognios_as_daemon.py       # Daemon entry point, wires BlackBox into main loop
```

> **Note:** `config.py` lives at the project root, not under a `utils/` package —
> every BlackBox module imports it as `from config import ...`.
---

## 3. Function & Class Reference

### `recorder.py`

```python
def get_blackbox_conn(db_path: str | Path | None = None) -> sqlite3.Connection
```
Opens a connection to `blackbox.db` in WAL mode (`synchronous=NORMAL`,
`busy_timeout=5000`). Registers a dedicated `threading.Lock` per connection
(keyed by `id(conn)`) so concurrent daemon threads can read/write safely.

```python
def create_blackbox_table(conn: sqlite3.Connection) -> None
```
Creates the `blackbox_telemetry` table and its timestamp index if they don't
already exist. Also runs an initial prune on call.

```python
def write_telemetry(conn: sqlite3.Connection, metrics: dict) -> None
```
Inserts one Layer 1 metrics row (see `BLACKBOX_METRICS_KEYS`). Fills in
`time.time()` if `timestamp` is missing or invalid. Prunes expired rows and
commits in the same call — the store never holds telemetry older than
`BLACKBOX_WINDOW_SEC` after a write returns.

```python
def prune_old_records(conn: sqlite3.Connection) -> None
```
Public, lock-safe wrapper around the internal `_prune_old_records()` — useful
for calling pruning explicitly outside the write path (e.g. a maintenance
script). Not required in the normal daemon loop since `write_telemetry`
already prunes on every write.

```python
def get_window_rows(conn: sqlite3.Connection, start_time: float, end_time: float) -> list[dict]
```

---

### `heartbeat.py`

```python
def create_heartbeat_table(conn: sqlite3.Connection) -> None
def update_heartbeat(conn: sqlite3.Connection) -> None
def mark_graceful_shutdown(conn: sqlite3.Connection) -> None
```
Single-row `blackbox_heartbeat` table (`id = 1`). `update_heartbeat` is
called every daemon tick; `mark_graceful_shutdown` is called from the
SIGINT/SIGTERM handler to set `graceful_shutdown = 1`. If the daemon dies
without that call (crash, SIGKILL, power loss), the flag stays `0`.

```python
def check_crash_on_startup(conn: sqlite3.Connection) -> tuple[bool, float]
```
Reads and clears the previous session's heartbeat state under a single lock
(avoids a race with a concurrent write leaving a stale marker for the next
startup). Detection order:
1. `graceful_shutdown == 1` → not a crash, regardless of gap size.
2. `graceful_shutdown == 0` and `gap > BLACKBOX_CRASH_GAP_SEC` (30s) → crash.
3. Gap is clamped to `≥ 0` to absorb clock corrections.

```python
def detect_crash_via_systemd() -> bool
```
Runs `journalctl -b -1 -n 10 --no-pager` (5s timeout) and scans the last
boot's final log lines for crash signals (`kernel panic`, `oom`,
`oom-killer`, `out of memory`, `segfault`) vs. clean signals (`power-off`,
`shutdown`, `reboot`, `stopped target`). Fails safe — any subprocess error,
timeout, or ambiguous output is treated as a suspected crash rather than
silently passing.

```python
def full_crash_check(conn: sqlite3.Connection) -> dict
```
Combines both checks:
```python
{
    "heartbeat_crash": bool,
    "heartbeat_gap":   float,
    "systemd_crash":   bool,
    "any_crash":       bool,   # heartbeat_crash OR systemd_crash
}
```

---

### `replay.py`

```python
def replay(conn, crash_time: float = None, window_minutes: int = 30) -> dict
```
Fetches the window, detects events, deduplicates them into a chain, and
returns:
```python
{
    'crash_time': float, 'window_start': float, 'total_rows': int,
    'events': list[dict], 'chain': list[dict],
    'timeline_text': str, 'trend_summary': str,
}
```

```python
def build_llm_context(conn, crash_time=None, heartbeat_gap=None, systemd_crash=None) -> str
```
Wraps `replay()`'s output plus crash-signal info into a formatted context
block for the LLM prompt.

**Detection logic** (baseline = mean/σ of the first 20% of window rows,
minimum 10 rows):

| Event | Condition |
|---|---|
| CPU spike | Z-score > 2.0 |
| Memory spike | Z-score > 2.0 |
| Memory leak | Linear-fit slope > 0.01%/s over the full window |
| Process explosion | `Δ total_processes > 30` between consecutive rows |
| Zombie buildup | `zombie_processes > 5` |
| Disk I/O storm | Z-score > 2.5 |
| Swap spike | Z-score > 2.0 |

**Dedup & formatting:**
- `_build_chain()` — same event `type` can't repeat within `min_gap_sec`
  (default **30s**; widened from an earlier 5s window that produced
  excessive near-duplicate entries on noisy metrics).
- `_format_chain()` — hard-caps the timeline at `max_events` (default
  **25**), prioritizing `severity: high` events first, chronological among
  survivors. Prevents unbounded prompt growth from a very noisy crash
  window.

---

### `nl_query.py`

```python
def query_telemetry(user_query: str, conn=None, stream=True, model=GROQ_MODEL,
                    api_key=None, crash_time=None, crash_info=None) -> str
```
Builds the telemetry context via `build_llm_context()`, appends it to the
module-level `_chat_history`, and calls `ask_groq()`.

```python
def ask_groq(user_content, system_prompt=SYSTEM_PROMPT, model=GROQ_MODEL,
             stream=True, api_key=None, history=None) -> str
```
Thin wrapper around `groq.Groq().chat.completions.create()`. Streams to
stdout when `stream=True`.

**CLI entry point (`main()`):**
```bash
python3 -m blackbox.nl_query "Why did my system crash?"   # one-shot query
python3 -m blackbox.nl_query                                # interactive REPL (multi-turn)
```
In REPL mode, `_chat_history` persists for the life of the process, so
follow-up questions retain conversation context. One-shot mode starts a
fresh process each time and has no memory across separate invocations.

---

## 4. Data Storage & Schema

### `blackbox_telemetry`

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Row ID |
| `timestamp` | `REAL NOT NULL` | Epoch time (indexed) |
| `cpu_usage_percent`, `cpu_ctx_switches`, `cpu_busy_time`, `cpu_iowait_time` | `REAL` | CPU metrics |
| `memory_percent` | `REAL` | RAM usage % |
| `memory_used` | `INTEGER` | RAM used (bytes) |
| `swap_percent` | `REAL` | Swap usage % |
| `disk_read`, `disk_write` | `REAL` | Disk throughput (MB/s) |
| `net_rate_mb_s` | `REAL` | Network throughput (MB/s) |
| `net_bytes_sent`, `net_bytes_received` | `INTEGER` | Cumulative network counters |
| `total_processes`, `running_processes`, `zombie_processes` | `INTEGER` | Process counts |
| `load_avg1`, `load_avg5` | `REAL` | System load averages |
| `avg_temp` | `REAL` | Average thermal reading (°C) |

### `blackbox_heartbeat`

Single-row table (`id = 1`):

| Column | Type | Description |
|---|---|---|
| `last_beat` | `REAL NOT NULL` | Epoch time of last successful tick |
| `graceful_shutdown` | `INTEGER NOT NULL DEFAULT 0` | `1` = clean exit, `0` = crash/abrupt |

### Concurrency & crash safety

- **WAL mode**: reads don't block writes; uncommitted writes survive an abrupt daemon crash.
- **`synchronous=NORMAL`**: balances 1 Hz write throughput with disk durability.
- **`busy_timeout=5000`**: avoids `SQLITE_BUSY` errors under concurrent access.
- **`_conn_locks`**: `id(conn) → threading.Lock()` mapping in `recorder.py`, ensuring thread-safe access across the daemon's threads. Assumes a single long-lived connection per process — if connections are ever created/destroyed dynamically, revisit this, since Python object IDs can be reused after garbage collection.

---

## 5. Configuration Reference

From `config.py` (project root):

```python
BLACKBOX_DB_PATH          = "blackbox/blackbox.db"
BLACKBOX_WINDOW_SEC       = 1800   # Rolling retention window (30 min)
BLACKBOX_CRASH_GAP_SEC    = 30     # Heartbeat gap threshold for crash detection
GROQ_MODEL                = "qwen/qwen3.6-27b"
```

### `.env`

```
GROQ_API_KEY=your_key_here
```

---

## 6. How to Run

### Prerequisites

```bash
pip install psutil numpy groq python-dotenv
```

### Run the daemon (recording + crash detection)

```bash
python3 cognios_as_daemon.py
```

On startup: creates tables if missing, runs `full_crash_check()`, and if a
crash is detected, logs the pre-crash timeline via `replay()`. Then enters
the 1 Hz telemetry loop (`collect_layer1_metrics → write_telemetry →
update_heartbeat`), trapping SIGINT/SIGTERM to mark a graceful shutdown.

### Query the BlackBox forensically (Groq LLM)

```bash
# One-shot
python3 -m blackbox.nl_query "Why did my system crash?"

# Interactive (multi-turn, retains conversation context)
python3 -m blackbox.nl_query
```

**Groq model notes:**
- `qwen/qwen3.6-27b` is a hybrid thinking/non-thinking reasoning model.
  `ask_groq()` passes `reasoning_format="hidden"` so the model's internal
  `<think>` trace is suppressed server-side and never counted toward
  visible output — but it **still consumes `max_completion_tokens`**
  internally, so the completion budget needs enough headroom for both
  reasoning and the visible answer (currently `3000` for streaming, `1500`
  for non-streaming).
- Groq enforces a **tokens-per-minute (TPM)** limit per account tier
  (`on_demand` tier: 8,000 TPM at time of writing). The `max_events=25` cap
  and `min_gap_sec=30` dedup window in `replay.py` exist specifically to
  keep the injected telemetry context small enough to stay under this
  limit — don't loosen either without checking prompt size against your
  tier's TPM budget.

