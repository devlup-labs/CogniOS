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

    query = f'''CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id                                  INTEGER PRIMARY KEY AUTOINCREMENT,

            cpu_usage_percent_gradient          REAL,
            cpu_usage_percent                   REAL,
            cpu_iowait_time_gradient            REAL,
            cpu_iowait_time                     REAL,
            memory_percent_gradient             REAL,
            memory_percent                      REAL,
            disk_read_mb_s_gradient             REAL,
            disk_read_mb_s                      REAL, 
            disk_write_mb_s_gradient            REAL,
            disk_write_mb_s                     REAL, 
            net_rate_mb_s_gradient              REAL, 
            net_rate_mb_s                       REAL,
            running_processes_gradient          REAL,
            running_processes                   REAL,
            cpu_usage_percent_deviation         REAL,
            cpu_ctx_switches_deviation          REAL,
            cpu_ctx_switches                    REAL,
            memory_percent_deviation            REAL,
            swap_percent_deviation              REAL,
            swap_percent                        REAL,
            load_avg_1_deviation                REAL,
            load_avg_1                          REAL,
            avg_temp_deviation                  REAL,
            avg_temp                            REAL,

            timestamp                           TEXT NOT NULL,
            
            cpu_1_cpu_peak_gradient             REAL,
            cpu_1_cpu_peak                      REAL,
            cpu_2_cpu_peak_gradient             REAL,
            cpu_2_cpu_peak                      REAL,
            cpu_3_cpu_peak_gradient             REAL,
            cpu_3_cpu_peak                      REAL,
            cpu_4_cpu_peak_gradient             REAL,
            cpu_4_cpu_peak                      REAL,
            cpu_5_cpu_peak_gradient             REAL,
            cpu_5_cpu_peak                      REAL,
            ram_1_peak_gradient                 REAL,
            ram_1_peak                          REAL,
            ram_1_open_fds_gradient             REAL,
            ram_1_open_fds                      REAL,
            ram_2_peak_gradient                 REAL,
            ram_2_peak                          REAL,
            ram_2_open_fds_gradient             REAL,
            ram_2_open_fds                      REAL,
            ram_3_peak_gradient                 REAL,
            ram_3_peak                          REAL,
            ram_3_open_fds_gradient             REAL,
            ram_3_open_fds                      REAL,
            ram_4_peak_gradient                 REAL,
            ram_4_peak                          REAL,
            ram_4_open_fds_gradient             REAL,
            ram_4_open_fds                      REAL,
            ram_5_peak_gradient                 REAL,
            ram_5_peak                          REAL,
            ram_5_open_fds_gradient             REAL,
            ram_5_open_fds                      REAL
            )
        '''

    cursor.execute(query)
    conn.commit()
    return conn

def write_to_os_doctor_train(ml_features_df, os_doctor_db_path):

    engine = create_engine(f"sqlite:///{os_doctor_db_path}")

    ml_features_df = ml_features_df.copy()

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
                ml_features_df, metadata = get_inference_payload(DB_PATH)
                if ml_features_df is not None:
                    write_to_os_doctor_train(ml_features_df, OS_DOCTOR_DB_PATH)
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