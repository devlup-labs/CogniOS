import sqlite3
import time
from sqlalchemy import create_engine

from os_doctor.featuring import get_inference_payload
from config import DB_PATH

OS_DOCTOR_DB_PATH = "os_doctor.db"
TABLE_NAME = "os_doctor_train"

def create_connection(os_doctor_db_path):
    conn = sqlite3.connect(os_doctor_db_path)
    cursor = conn.cursor()

    cpu_metrics = [
        ("score", "REAL"), ("avg", "REAL"), ("peak", "REAL"), ("user_time", "REAL"),
        ("system_time", "REAL"), ("ctx_invol_rate", "REAL"), ("ctx_vol_rate", "REAL"),
        ("gradient", "REAL"), ("rolling_avg", "REAL")
    ]

    ram_metrics = [
        ("score", "REAL"), ("avg", "REAL"), ("peak", "REAL"),("gradient", "REAL"),
        ("net_conn_count", "REAL"), ("open_fds", "REAL"), ("read_bytes_rate", "REAL"),
        ("write_bytes_rate", "REAL")
    ]

    sys_metrics = [
        ("cpu_usage_percent", "REAL"),
        ("cpu_freq", "REAL"),
        ("cpu_user_time", "REAL"),
        ("cpu_system_time", "REAL"),
        ("cpu_idle_time", "REAL"),
        ("cpu_iowait_time", "REAL"),
        ("cpu_busy_time", "REAL"),
        ("cpu_ctx_switches", "REAL"),

        ("memory_percent", "REAL"),
        ("memory_used", "INTEGER"),
        ("memory_available", "INTEGER"),
        ("memory_cached", "INTEGER"),
        ("memory_buffers", "INTEGER"),
        ("swap_percent", "REAL"),
        ("swap_sin", "INTEGER"),
        ("swap_sout", "INTEGER"),

        ("disk_usage_percent", "REAL"),
        ("disk_read_mb_s", "REAL"),
        ("disk_write_mb_s", "REAL"),
        ("disk_read_time", "INTEGER"),
        ("disk_write_time", "INTEGER"),

        ("net_rate_mb_s", "REAL"),
        ("net_bytes_sent", "INTEGER"),
        ("net_bytes_recv", "INTEGER"),
        ("net_packets_sent", "INTEGER"),
        ("net_packets_recv", "INTEGER"),
        ("net_errs", "INTEGER"),
        ("net_drops", "INTEGER"),

        ("load_avg_1", "REAL"),
        ("load_avg_5", "REAL"),
        ("load_avg_15", "REAL"),
        ("total_processes", "INTEGER"),
        ("running_processes", "INTEGER"),
        ("sleeping_processes", "INTEGER"),
        ("zombie_processes", "INTEGER"),

        ("avg_temp", "REAL"),
        ("max_temp", "REAL"),
        ("battery_percent", "REAL"),
        # ("process_data", "TEXT")
    ]   

    query = f'''CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL'''
    
    for i in range(1,6):
        for metric_name, data_type in cpu_metrics:
            query += f",\n pid_cpu_{i}_{metric_name} {data_type}"
    
    for i in range(1,6):
        for metric_name, data_type in ram_metrics:
            query += f",\n pid_ram_{i}_{metric_name} {data_type}"

    for metric_name, data_type in sys_metrics:
        query += f",\n sys_{metric_name} {data_type}"
        query += f",\n sys_{metric_name}_gradient REAL"
        query += f",\n sys_{metric_name}_rolling_avg REAL"

    query += "\n)"

    cursor.execute(query)
    conn.commit()
    return conn
    # print(query)

def write_to_os_doctor_train(ml_features_df, metadata_payload, os_doctor_db_path):

    engine = create_engine(f"sqlite:///{os_doctor_db_path}")

    ml_features_df = ml_features_df.copy()
    ml_features_df.insert(0, "timestamp", metadata_payload["timestamp"])

    ml_features_df.to_sql(
        name=TABLE_NAME,
        con=engine,
        if_exists='append',
        index=False
    )

def execute_os_doctor_db():
    conn = create_connection(OS_DOCTOR_DB_PATH)

    try:
        print("Starting the appending procces for os_doctor_train. Press Ctrl+C to stop")
        while True:
            try:
                ml_features_df, metadata_payload = get_inference_payload(DB_PATH)
                if ml_features_df is not None:
                    write_to_os_doctor_train(ml_features_df, metadata_payload, OS_DOCTOR_DB_PATH)
                    print("Successfully appended to os_doctor_train")
            except Exception as e:
                print(e)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nAppending process stopped.")
        conn.close()

# if __name__ == "__main__":

    # for col in ml_features_df:
    #     print(col)

    # conn = create_connection(OS_DOCTOR_DB_PATH)

    # try:
    #     print("Starting the appending procces for os_doctor_train. Press Ctrl+C to stop")
    #     while True:
    #         try:
    #             ml_features_df, metadata_payload = get_inference_payload(DB_PATH)
    #             write_to_os_doctor_train(ml_features_df, metadata_payload, OS_DOCTOR_DB_PATH)
    #             print("Successfully appended to os_doctor_train")
    #             time.sleep(1)
    #         except Exception as e: 
    #             print(e)
    #             conn.close()
    # except KeyboardInterrupt:
    #     print("\nAppending process stopped.")
    #     conn.close()