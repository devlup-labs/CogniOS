import joblib
import time
import pandas as pd

from os_doctor.alerts_db import write_to_alerts_table
from os_doctor.featuring import get_inference_payload
from os_doctor.i_forest_train import expected_columns
from os_doctor.llm_layer import generate_llm_explanation 
from config import DB_PATH, MODEL_PATH, SCALER_PATH

def flag_anomaly():
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    print("Model loaded. Listening for data...")
    
    try:
        while True:
            try:
                new_input, metadata = get_inference_payload(DB_PATH)
                if new_input is not None:
                    # 1. Clean input copy for ML processing
                    clean_input = new_input.copy()
                    clean_input.columns = expected_columns[1:]
                    clean_input = clean_input.drop(columns=["timestamp"]).dropna()

                    # 2. Scale features for Isolation Forest
                    scaled_input = scaler.transform(clean_input)
                    anomaly_score = model.decision_function(scaled_input)
                    print(f"Anomaly score: {round(anomaly_score[0], 2)}")
                    # 3. Check for anomaly flag (-1)
                    if model.predict(scaled_input)[0] == -1:
                        print(f"Anomaly detected! Score: {round(anomaly_score[0], 2)}")
                        
                        # 4. Generate LLM explanation using raw metadata
                        llm_explanation = generate_llm_explanation(metadata)
                        
                        # 5. Write to alerts DB (data = LLM output, metadata = raw system info)
                        write_to_alerts_table(data=llm_explanation, metadata=metadata)
                        print("Alert & LLM explanation successfully saved to database.")

                else: 
                    print("No new data available for anomaly detection.")
            except Exception as e:
                print("Error in flag anomaly:", e)
                
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nAnomaly detection stopped.")
