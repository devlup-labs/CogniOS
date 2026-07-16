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
    check_crash_on_startup,
    mark_graceful_shutdown,
)


def run_layer1_loop(stop_event):
    logger = get_layer_logger("layer1")
    logger.info(f"Starting Layer 1 collection. Saving metrics to '{DB_PATH}' every 1 second.")

    conn = create_connection(DB_PATH)
    bb_conn = get_blackbox_conn()
    create_blackbox_table(bb_conn)
    create_heartbeat_table(bb_conn)

    crashed, gap = check_crash_on_startup(bb_conn)
    if crashed:
        logger.warning(f"Previous session may have crashed! Gap = {gap}s")
    else:
        logger.info(f"Previous session ended cleanly (gap = {gap:.1f}s)")

    try:
        while not stop_event.is_set():
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
                    json.dumps(metrics['process_data'])
                )

                # --- Write to BlackBox rolling-window DB (blackbox/blackbox.db) ---
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
    conn = create_layer2_connection()
    init_layer2_db(conn)
    baselines = {}
    logger.info("Starting Layer 2 collection.")

    try:
        while not stop_event.is_set():
            top_cpu, top_mem, baselines = collect_layer2_metrics(baselines)
            write_layer2(conn, top_cpu, top_mem)
            logger.info(
                f"Snapshot committed at t={time.time():.0f} | "
                f"top_cpu={top_cpu[0]['name']} score={top_cpu[0]['cpu_score']} | "
                f"top_ram={top_mem[0]['name']} score={top_mem[0]['ram_score']}"
            )
    finally:
        logger.info("Stopping Layer 2 collection. Shutting down gracefully...")
        conn.close()


def run_daemon():
    ensure_wal_mode(DB_PATH)

    stop_event = threading.Event()

    def _request_shutdown(signum, frame):
        stop_event.set()

    # Explicit handlers so shutdown works even when backgrounded/orphaned, where
    # the shell has already set SIGINT to be ignored and Python's default
    # KeyboardInterrupt handler never gets installed at startup.
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    t1 = threading.Thread(target=run_layer1_loop, args=(stop_event,), daemon=True)
    t2 = threading.Thread(target=run_layer2_loop, args=(stop_event,), daemon=True)
    t1.start()
    t2.start()

    while t1.is_alive() or t2.is_alive():
        time.sleep(1)


if __name__ == "__main__":
    run_daemon()
