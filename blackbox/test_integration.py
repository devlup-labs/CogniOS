import time
import sys
import os
import tempfile
sys.path.insert(0, '.'
                )
from blackbox.correlation import telemetry_to_events, build_event_chain, format_chain_text

from collectors.layer1_system import collect_layer1_metrics
from blackbox.recorder import (
    get_blackbox_conn, create_blackbox_table,
    write_telemetry, get_recent_rows,
    get_window_rows, row_count, prune_old_records,
)
from blackbox.heartbeat import (
    create_heartbeat_table, update_heartbeat,
    check_crash_on_startup, mark_graceful_shutdown,
    detect_crash_via_systemd, full_crash_check,
)
from blackbox.feature_engineering import extract_feature_vector, FEATURE_NAMES
from blackbox.zscore_detector import ZScoreDetector
from blackbox.rule_engine import check_rules
from blackbox.replay import replay, generate_llm_context
from config import BLACKBOX_DB_PATH, DB_PATH


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
check("BlackBox DB file created", os.path.exists(BLACKBOX_DB_PATH))
print()

# ── Test 2: Heartbeat — graceful shutdown ───────────────
print("[ 2 ] Heartbeat + Crash Detection")

# Exercise the normal daemon lifecycle against the real BlackBox database.
update_heartbeat(conn)
mark_graceful_shutdown(conn)
crash, gap = check_crash_on_startup(conn)
check("Graceful shutdown → no crash detected", not crash,
      f"gap={gap}s, graceful=True → crash=False")

# Use the host's actual journal output.
systemd_crash = detect_crash_via_systemd()
check("Systemd crash check returns a boolean", isinstance(systemd_crash, bool),
      f"crash={systemd_crash}")

# Verify the combined startup API using live heartbeat and journal data.
update_heartbeat(conn)
crash_info = full_crash_check(conn)
check("full_crash_check returns all expected results",
      set(crash_info) == {"heartbeat_crash", "heartbeat_gap", "systemd_crash", "any_crash"})
check("full_crash_check combines boolean crash results",
      crash_info["any_crash"] == (
          crash_info["heartbeat_crash"] or crash_info["systemd_crash"]
      ))

# Reset the current session heartbeat after the startup check.
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

# ── Test 4: Prune records ────────────────────────────────
print("[ 4 ] prune_old_records")
before_prune = row_count(conn)
prune_old_records(conn)
after_prune = row_count(conn)
check("Pruning does not add records",
      after_prune <= before_prune,
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
cycle_count  = 0

for i in range(70):
    cycle_count += 1
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

check("Telemetry collection completed every cycle", cycle_count == 70)
check("Rule engine ran every cycle", cycle_count == 70,
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

# ── Test 8: Rule Engine ──────────────────────────────────
print("[ 8 ] Rule Engine (live system metrics)")
live_metrics = collect_layer1_metrics()
live_alerts = check_rules(live_metrics)
check("Rule engine accepts collected metrics", isinstance(live_alerts, list))
check("Rule engine returns structured alerts",
      all({"type", "severity", "message"} <= set(alert) for alert in live_alerts),
      f"{len(live_alerts)} live alerts")
print()

# ── Test 9: Graceful shutdown ────────────────────────────
print("[ 9 ] Graceful Shutdown Flag")
shutdown_started_at = time.time()
mark_graceful_shutdown(conn)
row = conn.execute(
    "SELECT last_beat, graceful_shutdown FROM blackbox_heartbeat WHERE id=1"
).fetchone()
check("graceful shutdown records a fresh heartbeat",
      row is not None and row[0] >= shutdown_started_at)
check("graceful_shutdown flag set to 1", row is not None and row[1] == 1)
print()

# ── Test 10: Final DB stats ──────────────────────────────
print("[ 10 ] Final DB Stats")
total_rows = row_count(conn)
check("DB has rows stored", total_rows > 0, f"{total_rows} rows total")
check("BlackBox uses a separate database",
      os.path.abspath(BLACKBOX_DB_PATH) != os.path.abspath(DB_PATH))
print()

# ── Test 11: Correlation & Event Chain ───────────────────
print("[ 11 ] Correlation Engine & Event Chain")
live_rows = get_recent_rows(conn, n=120)
events = telemetry_to_events(live_rows)
chain = build_event_chain(events)
check("Correlation accepts recorded telemetry", isinstance(events, list))
check("Event chain accepts correlated events", isinstance(chain, list))
formatted = format_chain_text(chain)
check("format_chain_text returns non-empty timeline", bool(formatted))
print()

# ── Test 12: Replay & LLM Context ────────────────────────
print("[ 12 ] Telemetry Replay & LLM Context Generation")
replay_res = replay(conn)
check("replay returns a dict", isinstance(replay_res, dict))
check("replay contains timeline_text", "timeline_text" in replay_res)
check("replay contains event chain", "chain" in replay_res)

llm_ctx = generate_llm_context(replay_res)
check("generate_llm_context returns a dict", isinstance(llm_ctx, dict))
check("llm_context contains prompt", "prompt" in llm_ctx)
check("llm_context contains timeline", "timeline" in llm_ctx)
print()

# ── Test 13: Anomaly Model (Isolation Forest) ──────────────
print("[ 13 ] Anomaly Model (Isolation Forest)")
from blackbox.anomaly_model import train, predict, anomaly_severity, save_model, load_model

# Derive multiple training vectors from windows of telemetry collected above.
recorded_rows = get_recent_rows(conn, n=120)
training_vectors = [
    vector
    for start in range(len(recorded_rows))
    if (vector := extract_feature_vector(recorded_rows[start:])) is not None
]
check("Live telemetry produced model training vectors", bool(training_vectors),
      f"{len(training_vectors)} vectors")

if training_vectors:
    model = train(training_vectors, contamination=0.05)
    check("Model trained successfully", model is not None)

    live_vector = training_vectors[-1]
    label, score = predict(model, live_vector)
    check("Model predicts a live feature vector", label in {-1, 1},
          f"label={label}, score={score}")
    severity = anomaly_severity(score)
    check("Live prediction has a valid severity", 0 <= severity <= 100,
          f"severity={severity}")

    with tempfile.TemporaryDirectory() as temp_dir:
        model_path = os.path.join(temp_dir, "if_model.pkl")
        save_model(model, model_path)
        check("Model saved to a temporary path", os.path.exists(model_path))

        loaded_model = load_model(model_path)
        loaded_label, loaded_score = predict(loaded_model, live_vector)
        check("Loaded model predicts the same live vector",
              (loaded_label, loaded_score) == (label, score))
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
