import joblib
import time
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from os_doctor.alerts_db import write_to_alerts_table
from os_doctor.featuring import get_inference_payload
from os_doctor.i_forest_train import expected_columns
from config import DB_PATH, ALERTS_DB_PATH

# IF ANOMALY SCORE >= BEST THRESHOLD WRITE TO ALERTS TABLE
# ELSE CONTINUE
def flag_anomaly():
    '''
    This function feeds the new_vector created by featuring.py every second to trained isolation forest model
    If anomaly score >= threshold value, it will appendthe new vector's details to alert.db 
    '''
    model = joblib.load('iso_forest_model.joblib')
    scaler = joblib.load('scaler.joblib')
    print("Model loaded. Listening for data...")
    try:
        while True:
            try:
                new_input, metadata = get_inference_payload(DB_PATH)
                if new_input is not None:
                    new_input.columns = expected_columns[1:]
                    new_input = new_input.drop(columns=["timestamp"])
                    new_input = new_input.dropna()

                    # Scaling
                    new_input = scaler.transform(new_input)
                    anomaly_score = model.decision_function(new_input)
                    print(f"Anomaly score: {round(anomaly_score[0], 2)}")
                    if model.predict(new_input) == -1:
                        print(f"Anomaly detected! Score: {round(anomaly_score[0], 2)}")
                        # Write to alerts table
                        data = new_input.to_dict(orient='records')
                        write_to_alerts_table(data, metadata)
                else: 
                    print("No new data available for anomaly detection.")
            except Exception as e:
                print("in flag anomaly. ", e)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nAnomaly detection stopped.")

   