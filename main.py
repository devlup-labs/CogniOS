import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("Starting CogniOS System...")

# Start the Telemetry Daemon in the background
# Output is routed to telemetry_daemon.log
telemetry_log_path = os.path.join(BASE_DIR, 'telemetry_daemon.log')
telemetry_log = open(telemetry_log_path, 'w')
telemetry_script = os.path.join(BASE_DIR, "cognios_as_daemon.py")
telemetry_process = subprocess.Popen(
    [sys.executable, telemetry_script], 
    stdout=telemetry_log,
    stderr=telemetry_log
)
print(f"Telemetry Daemon started! (PID: {telemetry_process.pid})")
print(f"To view the live logs anytime, run: tail -f '{telemetry_log_path}'")
print("To stop the daemon, run: pkill -f cognios_as_daemon.py")
# Start the FocusOS Daemon in the background
# Output is routed to focusos.log
# focusos_log_path = os.path.join(BASE_DIR, 'focusos.log')
# focusos_log = open(focusos_log_path, 'w')
# focusos_script = os.path.join(BASE_DIR, "focusos_daemon.py")
# focusos_process = subprocess.Popen(
#     [sys.executable, focusos_script], 
#     stdout=focusos_log, 
#     stderr=focusos_log
# )
# print(f"FocusOS Daemon started! (PID: {focusos_process.pid})")

#print("\nAll CogniOS modules are now running silently in the background!")
print("Your terminal is free to use.")

from focusos.models.classifier import WorkloadPredictor, FEATURE_COLUMNS
from focusos.feature_engineer import extract_features
from focusos.sliding_window import get_window_from_db
from focusos.llm_explainer import generate_explanation
from focusos.optimisation import apply_optimization
import time 

def run_focusos():
    predictor = WorkloadPredictor()
    print("FocusOS model inference testing...")
    
    last_workload = None
    last_explanation = ""
    last_explanation_time = 0
    COOLDOWN_SECONDS = 30
    
    while True:
        df_window = get_window_from_db()
        if df_window is not None:
            features = extract_features(df_window)
            if features is not None:
                print("\n========== LIVE FEATURE VECTOR ==========")
                print(features.to_string(index=False))
                print("=========================================\n")

                result = predictor.predict(features)
                if result:
                    workload = result['workload']
                    confidence = result['confidence']
                    print(f"[{time.strftime('%H:%M:%S')}] Detected: {workload} ({confidence}%)")
                    
                    # Extract the top 3 features based on model's feature importance
                    try:
                        importances = predictor.xgb.feature_importances_
                        top_indices = importances.argsort()[::-1][:3]
                        top_features = {}
                        for idx in top_indices:
                            feat_name = FEATURE_COLUMNS[idx]
                            feat_val = float(features[feat_name].iloc[0])
                            top_features[feat_name] = round(feat_val, 4)
                    except Exception as e:
                        print(f"Error extracting top features: {e}")
                        top_features = {}

                    # Generate explanation with rate limiting/caching
                    current_time = time.time()
                    if (workload != last_workload) or (current_time - last_explanation_time >= COOLDOWN_SECONDS):
                        last_explanation = generate_explanation(workload, confidence, top_features)
                        last_workload = workload
                        last_explanation_time = current_time
                        print(f"Explanation (Updated): {last_explanation}\n")
                        # Trigger dynamic system optimizations and log to DB
                        apply_optimization(workload, confidence, last_explanation)
                    else:
                        print(f"Explanation (Cached): {last_explanation}\n")
        time.sleep(2)

if __name__ == "__main__":
    try:
        run_focusos()
    except KeyboardInterrupt:
        print("Stopping CogniOS System...")
    finally:
        if telemetry_process.poll() is None:
            telemetry_process.terminate()
            try:
                telemetry_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                telemetry_process.kill()
                telemetry_process.wait()
        telemetry_log.close()
