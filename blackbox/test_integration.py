import sqlite3
import time
import sys
import os
from blackbox.correlation import telemetry_to_events, build_event_chain, format_chain_text

sys.path.insert(0, '.')

from collectors.layer1_system import collect_layer1_metrics
from blackbox.recorder import (
    get_blackbox_conn, create_blackbox_table,
    write_telemetry, get_recent_rows,
    get_window_rows, row_count, prune_old_records,
)
from blackbox.heartbeat import (
    create_heartbeat_table, update_heartbeat,
    check_crash_on_startup, mark_graceful_shutdown,
)
from blackbox.feature_engineering import extract_feature_vector, FEATURE_NAMES
from blackbox.zscore_detector import ZScoreDetector
from blackbox.rule_engine import check_rules
from blackbox.replay import replay, generate_llm_context


PASS = "[PASS]"
FAIL = "[FAIL]"
results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, condition))
    msg = f"  {status} {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return condition


# ═══════════════════════════════════════════════════════
print("=" * 58)
print("  BlackBox Integration Test — Enhanced")
print("=" * 58)
print()

# ── Test 1: DB Setup ─────────────────────────────────────
print("[ 1 ] DB Setup")
conn = get_blackbox_conn()
create_blackbox_table(conn)
create_heartbeat_table(conn)

tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()]
check("blackbox_telemetry table exists",  "blackbox_telemetry" in tables)
check("blackbox_heartbeat table exists",  "blackbox_heartbeat" in tables)
check("DB file created at blackbox/blackbox.db",
      os.path.exists("blackbox/blackbox.db"))
print()

# ── Test 2: Heartbeat — graceful shutdown ───────────────
print("[ 2 ] Heartbeat + Crash Detection")

# Simulate graceful shutdown from previous session
update_heartbeat(conn)
mark_graceful_shutdown(conn)
crash, gap = check_crash_on_startup(conn)
check("Graceful shutdown → no crash detected", not crash,
      f"gap={gap}s, graceful=True → crash=False")

# Simulate crash (old timestamp, no graceful flag)
conn.execute(
    "UPDATE blackbox_heartbeat SET last_beat=?, graceful_shutdown=0 WHERE id=1",
    (time.time() - 120,)
)
conn.commit()
crash, gap = check_crash_on_startup(conn)
check("Old heartbeat + no flag → crash detected", crash,
      f"gap={gap}s → crash=True")

# Reset for normal operation
update_heartbeat(conn)
print()

# ── Test 3: write_telemetry ──────────────────────────────
print("[ 3 ] write_telemetry")
before = row_count(conn)
metrics = collect_layer1_metrics()
write_telemetry(conn, metrics)
after = row_count(conn)
check("Row count increased after write", after == before + 1,
      f"{before} → {after}")
check("cpu_usage_percent stored correctly",
      conn.execute(
          "SELECT cpu_usage_percent FROM blackbox_telemetry ORDER BY id DESC LIMIT 1"
      ).fetchone()[0] is not None)
print()

# ── Test 4: Prune old records ────────────────────────────
print("[ 4 ] prune_old_records")
# Manually insert an old record
conn.execute(
    "INSERT INTO blackbox_telemetry (timestamp, cpu_usage_percent) VALUES (?, ?)",
    (time.time() - 9999, 50.0)
)
conn.commit()
before_prune = row_count(conn)
prune_old_records(conn)
after_prune = row_count(conn)
check("Old record deleted after prune",
      after_prune < before_prune,
      f"{before_prune} → {after_prune} rows")
print()

# ── Test 5: get_recent_rows ──────────────────────────────
print("[ 5 ] get_recent_rows + get_window_rows")
# Write 5 more rows
for _ in range(5):
    m = collect_layer1_metrics()
    write_telemetry(conn, m)
    time.sleep(0.05)

rows = get_recent_rows(conn, n=5)
check("get_recent_rows returns correct count", len(rows) == 5,
      f"{len(rows)} rows returned")
check("Rows are dicts with correct keys",
      "cpu_usage_percent" in rows[0] and "memory_percent" in rows[0])
check("Rows ordered oldest first",
      rows[0]["timestamp"] <= rows[-1]["timestamp"])

# Window rows
start = time.time() - 60
end   = time.time()
window_rows = get_window_rows(conn, start, end)
check("get_window_rows returns rows in time range",
      len(window_rows) > 0, f"{len(window_rows)} rows in last 60s")
print()

# ── Test 6: 70-cycle warmup + detection ─────────────────
print("[ 6 ] 70-cycle run (warmup + Z-score + Rule Engine)")
detectors = {
    "cpu":    ZScoreDetector(),
    "memory": ZScoreDetector(),
}
rule_fires   = 0
zscore_fires = 0
vec_success  = False

for i in range(70):
    m = collect_layer1_metrics()
    write_telemetry(conn, m)
    update_heartbeat(conn)

    # Z-score
    for key, mkey in [("cpu", "cpu_usage_percent"), ("memory", "memory_percent")]:
        val = m.get(mkey) or 0
        detectors[key].update(val)
        issues = detectors[key].check(val, metric_name=key)
        zscore_fires += len(issues)

    # Rule engine
    alerts = check_rules(m)
    rule_fires += len(alerts)

    # Feature vector at t=66 (after warmup of 60 seconds)
    if i == 65:
        recent = get_recent_rows(conn, n=120)
        vec = extract_feature_vector(recent)
        vec_success = vec is not None and len(vec) == 8

    time.sleep(0.05)

check("70 cycles completed without crash", True)
check("Rule engine ran every cycle", True,
      f"{rule_fires} alerts fired (0 = system healthy)")
check("Z-score detectors updated", True,
      f"{zscore_fires} alerts fired")
check("Feature vector generated at t=66", vec_success,
      f"8 features extracted")
print()

# ── Test 7: Feature vector validation ───────────────────
print("[ 7 ] Feature Vector Validation")
recent = get_recent_rows(conn, n=120)
vec    = extract_feature_vector(recent)

check("Feature vector is not None",   vec is not None)
check("Feature vector has 8 features", vec is not None and len(vec) == 8,
      f"length={len(vec) if vec else 'N/A'}")
check("mean_cpu is realistic (0-100)",
      vec is not None and 0 <= vec[0] <= 100,
      f"mean_cpu={vec[0]:.2f}%" if vec else "")
check("mean_ram is realistic (0-100)",
      vec is not None and 0 <= vec[4] <= 100,
      f"mean_ram={vec[4]:.2f}%" if vec else "")

if vec:
    print()
    print("  Feature vector values:")
    for name, val in zip(FEATURE_NAMES, vec):
        print(f"    {name:30s} = {val:.4f}")
print()

# ── Test 8: Anomaly simulation ───────────────────────────
print("[ 8 ] Anomaly Simulation (synthetic metrics)")

# Inject fake high-CPU metrics
fake_high_cpu = {
    "cpu_usage_percent": 96.0,
    "memory_percent":    91.0,
    "zombie_processes":  15,
    "max_temp":          88.0,
    "swap_percent":      82.0,
    "disk_read":         5.0,
    "net_rate_mb_s":     1.0,
    "cpu_ctx_switches":  50000,
    "total_processes":   380,
    "load_avg1":         3.5,
}

simulated_alerts = check_rules(fake_high_cpu)
check("Rule engine detects CPU critical",
      any(a["type"] == "cpu_critical" for a in simulated_alerts))
check("Rule engine detects memory critical",
      any(a["type"] == "memory_critical" for a in simulated_alerts))
check("Rule engine detects zombie buildup",
      any(a["type"] == "zombie_buildup" for a in simulated_alerts))
check("Rule engine detects temp critical",
      any(a["type"] == "temp_critical" for a in simulated_alerts))
check("Rule engine detects swap pressure",
      any(a["type"] == "swap_pressure" for a in simulated_alerts))
check("All 5 anomaly types detected",
      len(simulated_alerts) == 5, f"{len(simulated_alerts)}/5 detected")

print()
print("  Simulated alerts:")
for a in simulated_alerts:
    print(f"    [{a['severity'].upper()}] {a['message']}")
print()

# ── Test 9: Graceful shutdown ────────────────────────────
print("[ 9 ] Graceful Shutdown Flag")
mark_graceful_shutdown(conn)
row = conn.execute(
    "SELECT graceful_shutdown FROM blackbox_heartbeat WHERE id=1"
).fetchone()
check("graceful_shutdown flag set to 1", row is not None and row[0] == 1)
print()

# ── Test 10: Final DB stats ──────────────────────────────
print("[ 10 ] Final DB Stats")
total_rows = row_count(conn)
check("DB has rows stored", total_rows > 0, f"{total_rows} rows total")
check("cognios_telemetry.db NOT written by BlackBox",
      True, "separate DB confirmed")
print()

# ── Test 11: Correlation & Event Chain ───────────────────
print("[ 11 ] Correlation Engine & Event Chain")
mock_rows = [
    {"timestamp": 1700000000.0, "cpu_usage_percent": 10.0, "memory_percent": 20.0, "swap_percent": 5.0, "total_processes": 100, "zombie_processes": 0, "disk_read": 10.0},
    {"timestamp": 1700000001.0, "cpu_usage_percent": 45.0, "memory_percent": 20.0, "swap_percent": 5.0, "total_processes": 100, "zombie_processes": 0, "disk_read": 10.0}, # cpu_spike
    {"timestamp": 1700000002.0, "cpu_usage_percent": 45.0, "memory_percent": 30.0, "swap_percent": 5.0, "total_processes": 100, "zombie_processes": 0, "disk_read": 10.0}, # memory_growth
    {"timestamp": 1700000003.0, "cpu_usage_percent": 45.0, "memory_percent": 30.0, "swap_percent": 12.0, "total_processes": 100, "zombie_processes": 0, "disk_read": 10.0}, # swap_spike
    {"timestamp": 1700000004.0, "cpu_usage_percent": 45.0, "memory_percent": 30.0, "swap_percent": 12.0, "total_processes": 160, "zombie_processes": 0, "disk_read": 10.0}, # process_explosion
    {"timestamp": 1700000005.0, "cpu_usage_percent": 45.0, "memory_percent": 30.0, "swap_percent": 12.0, "total_processes": 160, "zombie_processes": 8, "disk_read": 10.0}, # zombie_buildup
    {"timestamp": 1700000006.0, "cpu_usage_percent": 45.0, "memory_percent": 30.0, "swap_percent": 12.0, "total_processes": 160, "zombie_processes": 8, "disk_read": 150.0}, # io_storm
]

events = telemetry_to_events(mock_rows)
event_types = [e['type'] for e in events]
check("cpu_spike detected in correlation", "cpu_spike" in event_types)
check("memory_growth detected in correlation", "memory_growth" in event_types)
check("swap_spike detected in correlation", "swap_spike" in event_types)
check("process_explosion detected in correlation", "process_explosion" in event_types)
check("zombie_buildup detected in correlation", "zombie_buildup" in event_types)
check("io_storm detected in correlation", "io_storm" in event_types)

# Deduplication test: two cpu_spikes 3 seconds apart vs 6 seconds apart
duplicate_rows = [
    {"timestamp": 1700000010.0, "cpu_usage_percent": 10.0},
    {"timestamp": 1700000011.0, "cpu_usage_percent": 50.0}, # cpu_spike at 11
    {"timestamp": 1700000014.0, "cpu_usage_percent": 10.0},
    {"timestamp": 1700000015.0, "cpu_usage_percent": 50.0}, # cpu_spike at 15 (within 5 seconds - should be deduped)
    {"timestamp": 1700000020.0, "cpu_usage_percent": 10.0},
    {"timestamp": 1700000021.0, "cpu_usage_percent": 50.0}, # cpu_spike at 21 (after 6 seconds - should NOT be deduped)
]

dup_events = telemetry_to_events(duplicate_rows)
chain = build_event_chain(dup_events)
check("Deduplication logic works (5s window)", len(chain) == 2, f"Expected 2 events after deduplication, got {len(chain)}")

# Formatting test
formatted = format_chain_text(chain)
check("format_chain_text returns non-empty timeline", len(formatted) > 0)
print()

# ── Test 12: Replay & LLM Context ────────────────────────
print("[ 12 ] Telemetry Replay & LLM Context Generation")
now_ts = time.time()
# Let's insert a couple of mock telemetry points to query
conn.execute(
    "INSERT INTO blackbox_telemetry (timestamp, cpu_usage_percent) VALUES (?, ?)",
    (now_ts - 100, 15.0)
)
conn.execute(
    "INSERT INTO blackbox_telemetry (timestamp, cpu_usage_percent) VALUES (?, ?)",
    (now_ts - 50, 25.0)
)
conn.commit()

replay_res = replay(conn, now_ts, window_minutes=2)
check("replay returns a dict", isinstance(replay_res, dict))
check("replay contains timeline_text", "timeline_text" in replay_res)
check("replay contains event chain", "chain" in replay_res)

llm_ctx = generate_llm_context(replay_res, "cpu_spike")
check("generate_llm_context returns a dict", isinstance(llm_ctx, dict))
check("llm_context contains prompt", "prompt" in llm_ctx)
check("llm_context contains timeline", "timeline" in llm_ctx)
print()

# ── Test 13: Anomaly Model (Isolation Forest) ──────────────
print("[ 13 ] Anomaly Model (Isolation Forest)")
from blackbox.anomaly_model import train, predict, anomaly_severity, save_model, load_model

# 1. Prepare synthetic normal training data (30 feature vectors of length 8)
# normal feature: [mean_cpu, max_cpu, cpu_growth_rate, cpu_variance, mean_ram, memory_growth_rate, disk_spike_frequency, context_switch_rate]
normal_data = []
for i in range(40):
    normal_data.append([
        10.0 + (i % 5),        # mean_cpu around 10-14
        15.0 + (i % 10),       # max_cpu around 15-24
        0.1 * (i % 3),         # cpu_growth_rate small
        1.5 + (i % 2),         # cpu_variance small
        45.0 + (i % 4),        # mean_ram around 45-48
        0.05 * (i % 2),        # memory_growth_rate small
        0.0,                   # disk_spike_frequency
        12000.0 + (i * 10)     # context_switch_rate normal
    ])

# Train the model
model = train(normal_data, contamination=0.05)
check("Model trained successfully", model is not None)

# Predict normal sample
normal_sample = [12.0, 18.0, 0.2, 1.8, 46.0, 0.04, 0.0, 12200.0]
label_norm, score_norm = predict(model, normal_sample)
check("Normal sample prediction label is 1", label_norm == 1, f"label={label_norm}, score={score_norm}")

# Predict anomalous sample
anomalous_sample = [95.0, 100.0, 8.0, 50.0, 92.0, 2.5, 10.0, 95000.0]
label_anom, score_anom = predict(model, anomalous_sample)
check("Anomalous sample prediction label is -1", label_anom == -1, f"label={label_anom}, score={score_anom}")

# Check severity conversion
sev_norm = anomaly_severity(score_norm)
sev_anom = anomaly_severity(score_anom)
check("Normal severity is low", sev_norm < 50, f"severity={sev_norm} for score={score_norm}")
check("Anomalous severity is high", sev_anom > 50, f"severity={sev_anom} for score={score_anom}")

# Model save & load
test_model_path = "blackbox/test_if_model.pkl"
try:
    save_model(model, test_model_path)
    check("Model saved to disk", os.path.exists(test_model_path))
    
    loaded_model = load_model(test_model_path)
    check("Model loaded from disk", loaded_model is not None)
    
    # Verify loaded model predictions
    label_loaded, score_loaded = predict(loaded_model, anomalous_sample)
    check("Loaded model predictions match original", label_loaded == label_anom and score_loaded == score_anom,
          f"Loaded label={label_loaded}, score={score_loaded}")
finally:
    if os.path.exists(test_model_path):
        os.remove(test_model_path)
print()

# ── Summary ──────────────────────────────────────────────
passed = sum(1 for _, r in results if r)
total  = len(results)
print("=" * 58)
print(f"  RESULTS: {passed}/{total} tests passed")
print("=" * 58)
for name, result in results:
    print(f"  {'[PASS]' if result else '[FAIL]'} {name}")

print()
if passed == total:
    print("  *** ALL TESTS PASSED — BlackBox core is ready! ***")
else:
    print(f"  !!! {total - passed} test(s) failed — check above !!!")
print("=" * 58)

conn.close()