import joblib
import time
import pandas as pd

from os_doctor.alerts_db import write_to_alerts_table
from os_doctor.featuring import get_inference_payload_predict
from os_doctor.i_forest_train import expected_columns
from config import DB_PATH

FEATURE_COLUMNS = expected_columns[1:]

# IF ANOMALY SCORE >= BEST THRESHOLD WRITE TO ALERTS TABLE
# ELSE CONTINUE
def flag_anomaly():
    '''
    Feeds the new_vector created by featuring.py every second to the trained
    isolation forest model. If anomaly score >= threshold, appends the
    RAW (unscaled) vector's details to alerts.db, alongside the scaled
    values used for the actual model decision.
    '''
    model = joblib.load('iso_forest_model.joblib')
    scaler = joblib.load('scaler.joblib')
    print("Model loaded. Listening for data...")
    
    try:
        while True:
            try:
                # CHANGED: unpack 3 values now (raw, scaled, metadata).
                # We pass no scaler here — this file owns scaling itself,
                # since it loads its own scaler.joblib separately.
                raw_input, _, metadata = get_inference_payload_predict(DB_PATH)

                if raw_input is not None:
                    raw_input.columns = FEATURE_COLUMNS
                    raw_input = raw_input.drop(columns=["timestamp"], errors="ignore")
                    raw_input = raw_input.dropna()

                    if raw_input.empty:
                        print("No usable rows after dropna(). Skipping tick.")
                        time.sleep(5)
                        continue

                    # CHANGED: scale into a NEW array/frame — raw_input
                    # itself is never overwritten, so it's still valid
                    # for storage after this point.
                    scaled_array = scaler.transform(raw_input)
                    scaled_df = pd.DataFrame(
                        scaled_array, columns=raw_input.columns, index=raw_input.index
                    )

                    ANOMALY_THRESHOLD = -0.1

                    anomaly_score = model.decision_function(scaled_array)
                    score_val = float(anomaly_score[0])
                    print(f"Anomaly score: {round(score_val, 2)}")

                    if score_val <= ANOMALY_THRESHOLD:
                        print(f"Anomaly detected! Score: {round(score_val, 2)} (Threshold: {ANOMALY_THRESHOLD})")

                        data = {
                            "raw": raw_input.to_dict(orient='records')[0],
                            "scaled": scaled_df.to_dict(orient='records')[0],
                            "anomaly_score": score_val,
                        }
                        write_to_alerts_table(data, metadata)
                else:
                    print("No new data available for anomaly detection.")
            except Exception as e:
                print("Error in flag anomaly:", e)
                
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nAnomaly detection stopped.")
