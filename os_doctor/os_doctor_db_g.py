import sqlite3
import time
from sqlalchemy import create_engine

from os_doctor.featuring import get_inference_payload_train, ML_FEATURES
from config import DB_PATH, OS_DOCTOR_DB_PATH

TABLE_NAME = "os_doctor_train_g"

def create_connection(os_doctor_db_path):
    conn = sqlite3.connect(os_doctor_db_path)
    cursor = conn.cursor()

    # Columns are generated from ML_FEATURES so this table always matches
    # what featuring.py produces.
    feature_columns = ",\n            ".join(f"{name} REAL" for name in ML_FEATURES)
    query = f'''CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            {feature_columns}
            )
        '''

    cursor.execute(query)
    conn.commit()
    return conn

def write_to_os_doctor_train_g(ml_features_df, timestamp, os_doctor_db_path):

    engine = create_engine(f"sqlite:///{os_doctor_db_path}")

    ml_features_df = ml_features_df[ML_FEATURES].copy()
    ml_features_df.insert(0, "timestamp", timestamp)

    ml_features_df.to_sql(
        name=TABLE_NAME,
        con=engine,
        if_exists='append',
        index=False
    )

def execute_os_doctor_db():
    conn = create_connection(OS_DOCTOR_DB_PATH)
    # Track the last written timestamp to avoid duplicate rows when the
    # daemon isn't producing new telemetry.
    row = conn.execute(f"SELECT timestamp FROM {TABLE_NAME} ORDER BY id DESC LIMIT 1").fetchone()
    last_written_timestamp = row[0] if row else None

    try:
        print("Starting the appending process for os_doctor_train_g (gaming). Press Ctrl+C to stop")
        while True:
            try:
                ml_features_df, metadata = get_inference_payload_train(DB_PATH)
                if ml_features_df is not None:
                    timestamp = metadata["timestamp"]
                    if timestamp == last_written_timestamp:
                        print("[gaming] No new telemetry since the last row. Skipping.")
                    else:
                        write_to_os_doctor_train_g(ml_features_df, timestamp, OS_DOCTOR_DB_PATH)
                        last_written_timestamp = timestamp
                        print("[gaming] Successfully appended to os_doctor_train_g")
            except Exception as e:
                print(e)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nAppending process stopped.")
        conn.close()