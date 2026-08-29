"""Daemon entry point for CogniOS — runs Layer 1 and Layer 2 collection concurrently."""
import time
import json
import signal
import threading
from db import (
    create_connection,
    write_layer1,
    create_layer2_connection,
    init_layer2_db,
    write_layer2,
    ensure_wal_mode,
)
from collectors.layer1_system import collect_layer1_metrics
from collectors.layer2_process import collect_layer2_metrics
from config import DB_PATH
from logging_utils import get_layer_logger

from blackbox.recorder import get_blackbox_conn, create_blackbox_table, write_telemetry
from blackbox.heartbeat import (
    create_heartbeat_table,
    update_heartbeat,
    full_crash_check,
    mark_graceful_shutdown,
)
from blackbox.replay import replay

from focusos.models.classifier import WorkloadPredictor, FEATURE_COLUMNS
from focusos.feature_engineer import extract_features
from focusos.sliding_window import get_window_from_db
from focusos.llm_explainer import generate_explanation
from focusos.optimisation import apply_optimization


def run_layer1_loop(stop_event):
    logger = get_layer_logger("layer1")
    logger.info(f"Starting Layer 1 collection. Saving metrics to '{DB_PATH}' every 1 second.")

    conn = create_connection(DB_PATH)
    bb_conn = get_blackbox_conn()
    create_blackbox_table(bb_conn)
    create_heartbeat_table(bb_conn)

    crash_info = full_crash_check(bb_conn)
    if crash_info["any_crash"]:
        signals = []
        if crash_info["heartbeat_crash"]:
            signals.append("stale heartbeat")
        if crash_info["systemd_crash"]:
            signals.append("system journal")
        logger.warning(
            "Previous session may have crashed! "
            f"Gap = {crash_info['heartbeat_gap']}s; "
            f"signals = {', '.join(signals)}"
        )
        result = replay(bb_conn)
        logger.warning("BlackBox pre-crash timeline:\n" + result['timeline_text'])
    else:
        logger.info(
            "Previous session ended cleanly "
            f"(heartbeat gap = {crash_info['heartbeat_gap']:.1f}s)"
        )

    tick = 0

    try:
        while not stop_event.is_set():
            tick += 1
            try:
                metrics = collect_layer1_metrics()

                # --- Write to permanent DB (cognios_telemetry.db) ---
                write_layer1(
                    conn,
                    metrics['timestamp'],
                    metrics['cpu_usage_percent'],
                    metrics['cpu_current_freq'],
                    metrics['cpu_user_time'],
                    metrics['cpu_system_time'],
                    metrics['cpu_idle_time'],
                    metrics['cpu_iowait_time'],
                    metrics['cpu_busy_time'],
                    metrics['cpu_ctx_switches'],
                    metrics['memory_percent'],
                    metrics['memory_used'],
                    metrics['memory_available'],
                    metrics['memory_cached'],
                    metrics['memory_buffers'],
                    metrics['swap_percent'],
                    metrics['swap_sin'],
                    metrics['swap_sout'],
                    metrics['disk_usage_percent'],
                    metrics['disk_read'],
                    metrics['disk_write'],
                    metrics['disk_read_time'],
                    metrics['disk_write_time'],
                    metrics['load_avg1'],
                    metrics['load_avg5'],
                    metrics['load_avg15'],
                    metrics['total_processes'],
                    metrics['running_processes'],
                    metrics['sleeping_processes'],
                    metrics['zombie_processes'],
                    metrics['avg_temp'],
                    metrics['max_temp'],
                    metrics['battery_percent'],
                    metrics['net_rate_mb_s'],
                    metrics['net_bytes_sent'],
                    metrics['net_bytes_received'],
                    metrics['net_packets_sent'],
                    metrics['net_packets_received'],
                    metrics['net_errs'],
                    metrics['net_drops'],
                    json.dumps(metrics['process_data']),
                    sum(metrics['num_threads']) if isinstance(metrics.get('num_threads'), list) else int(metrics.get('num_threads') or 0),
                    metrics.get('udp_tcp_ratio', 0.10)
                )

                # --- Write to BlackBox rolling-window DB ---
                write_telemetry(bb_conn, metrics)
                update_heartbeat(bb_conn)

                logger.info(f"Successfully saved metrics for timestamp: {metrics['timestamp']}")

            except Exception as e:
                logger.error(f"Error collecting or writing metrics: {e}")

            time.sleep(1)

    finally:
        logger.info("Stopping Layer 1 collection. Shutting down gracefully...")
        mark_graceful_shutdown(bb_conn)
        conn.close()
        bb_conn.close()

def run_layer2_loop(stop_event):
    logger = get_layer_logger("layer2")
    try:
        conn = create_layer2_connection()
        init_layer2_db(conn)
        baselines = {}
        logger.info("Starting Layer 2 collection.")

        while not stop_event.is_set():
            try:
                top_cpu, top_mem, baselines = collect_layer2_metrics(baselines)
                write_layer2(conn, top_cpu, top_mem)
                logger.info(
                    f"Snapshot committed at t={time.time():.0f} | "
                    f"top_cpu={top_cpu[0]['name']} score={top_cpu[0]['cpu_score']} | "
                    f"top_ram={top_mem[0]['name']} score={top_mem[0]['ram_score']}"
                )
            except Exception as e:
                logger.warning(f"Layer 2 write skipped (schema mismatch or error): {e}")
                stop_event.wait(timeout=5)
    except Exception as e:
        logger.warning(f"Layer 2 loop disabled — not used by FocusOS ({e})")
    finally:
        logger.info("Layer 2 thread exited.")


def run_focusos_loop(stop_event):
    logger = get_layer_logger("focusos")
    logger.info("Starting FocusOS inference loop.")
    
    try:
        predictor = WorkloadPredictor()
    except Exception as e:
        logger.error(f"Failed to load WorkloadPredictor: {e}")
        return

    last_workload = None
    last_explanation = ""
    last_explanation_time = 0
    COOLDOWN_SECONDS = 30
    
    try:
        while not stop_event.is_set():
            try:
                df_window = get_window_from_db()
                if df_window is not None and not df_window.empty and len(df_window) >= 5:
                    features = extract_features(df_window)
                    if features is not None:
                        result = predictor.predict(features)
                        if result:
                            workload = result['workload']
                            confidence = result['confidence']

                            try:
                                importances = predictor.xgb.feature_importances_
                                top_indices = importances.argsort()[::-1][:3]
                                top_features = {}
                                for idx in top_indices:
                                    feat_name = FEATURE_COLUMNS[idx]
                                    feat_val = float(features[feat_name].iloc[0])
                                    top_features[feat_name] = round(feat_val, 4)
                            except Exception as e:
                                logger.error(f"Error extracting top features: {e}")
                                top_features = {}

                            current_time = time.time()

                            # Regenerate LLM explanation only on workload change or cooldown
                            if (workload != last_workload) or (current_time - last_explanation_time >= COOLDOWN_SECONDS):
                                last_explanation = generate_explanation(workload, confidence, top_features)
                                last_workload = workload
                                last_explanation_time = current_time

                            # Write fresh prediction every cycle → dashboard stays live.
                            # apply_optimization() skipped intentionally (wired in later).
                            try:
                                import json as _json
                                import sqlite3 as _sq
                                # last_explanation may be a dict from generate_explanation
                                _expl = last_explanation if isinstance(last_explanation, str) else _json.dumps(last_explanation)
                                _conn = _sq.connect(DB_PATH, timeout=5.0)
                                _conn.execute(
                                    "INSERT INTO focusos_events "
                                    "(timestamp, workload, confidence, actions, explanation) "
                                    "VALUES (?, ?, ?, ?, ?)",
                                    (
                                        time.time(), workload, confidence,
                                        _json.dumps([f"Detected: {workload} ({confidence:.1f}%)"]),
                                        _expl,
                                    )
                                )
                                _conn.commit()
                                _conn.close()
                            except Exception as _e:
                                logger.warning(f"focusos_events write failed: {_e}")
                            logger.info(f"FocusOS: {workload} ({confidence:.1f}%)") 

            except Exception as e:
                logger.error(f"Error in FocusOS inference loop: {e}")

            time.sleep(2)
    finally:
        logger.info("Stopping FocusOS inference loop.")


def run_daemon():
    ensure_wal_mode(DB_PATH)

    stop_event = threading.Event()

    def _request_shutdown(signum, frame):
        stop_event.set()
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    # Import OS Doctor modules
    from os_doctor.i_forest_predict import flag_anomaly
    from os_doctor.llm_layer import run_llm_daemon

    t1 = threading.Thread(target=run_layer1_loop, args=(stop_event,), daemon=True)
    t2 = threading.Thread(target=run_layer2_loop, args=(stop_event,), daemon=True)
    t3 = threading.Thread(target=run_focusos_loop, args=(stop_event,), daemon=True)
    t4 = threading.Thread(target=flag_anomaly, daemon=True)
    t5 = threading.Thread(target=run_llm_daemon, daemon=True)
    
    t1.start()
    t2.start()
    t3.start()
    t4.start()
    t5.start()

    try:
        while t1.is_alive() or t2.is_alive() or t3.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
        t1.join(timeout=2)
        t2.join(timeout=2)
        t3.join(timeout=2)


if __name__ == "__main__":
    run_daemon()
