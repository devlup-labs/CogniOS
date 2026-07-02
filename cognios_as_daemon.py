"""Daemon entry point for CogniOS."""
import time
import json
import logging
from db import create_connection, write_layer1
from collectors.layer1_system import collect_layer1_metrics
from config import DB_PATH

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_daemon():
    logging.info(f"Starting CogniOS Daemon. Saving metrics to '{DB_PATH}' every 1 second.")
    
    # Initialize database connection
    conn = create_connection(DB_PATH)
    
    try:
        while True:
            try:
                metrics = collect_layer1_metrics()
                
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
                logging.info(f"Successfully saved metrics for timestamp: {metrics['timestamp']}")
                
            except Exception as e:
                logging.error(f"Error collecting or writing metrics: {e}")
                
            # Wait for 1 second before the next collection
            time.sleep(1)
            
    except KeyboardInterrupt:
        logging.info("Stopping CogniOS Daemon. Shutting down gracefully...")
    finally:
        conn.close()

if __name__ == "__main__":
    run_daemon()
