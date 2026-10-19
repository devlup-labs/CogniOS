"""Isolation Forest anomaly prediction for OS Doctor — workload-aware."""
import joblib
import time
import os
import pandas as pd

from os_doctor.alerts_db import write_to_alerts_table
from os_doctor.featuring import get_inference_payload_predict, ML_FEATURES, scale_features
from config import DB_PATH, WORKLOADS, OS_DOCTOR_MODELS_DIR


def _load_workload_assets(workload_id):
    """
    Load the model and scaler for a given workload.

    Parameters
    ----------
    workload_id : int
        0 = Idle, 1 = Browsing, 2 = Coding, 3 = Gaming

    Returns
    -------
    (model, scaler, workload_name)

    Raises
    ------
    FileNotFoundError
        If the model or scaler has not been trained yet.
    """
    if workload_id not in WORKLOADS:
        raise ValueError(f"Unknown workload_id {workload_id}. Must be 0-3.")

    workload = WORKLOADS[workload_id]
    model_path = workload["model_path"]
    scaler_path = workload["scaler_path"]
    name = workload["name"]

    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"No trained model for workload '{name}' at '{model_path}'. "
            "Run training first."
        )
    if not os.path.exists(scaler_path):
        raise FileNotFoundError(
            f"No fitted scaler for workload '{name}' at '{scaler_path}'. "
            "Run training first."
        )

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    return model, scaler, name


def _get_default_workload_id():
    """Default callback fetching latest workload from workload_events table or fallback."""
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH, timeout=2.0)
        cursor = conn.cursor()
        cursor.execute("SELECT workload, ml_confidence FROM workload_events ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            wl_str = (row[0] or "").lower()
            conf = float(row[1] or 0.85)
            wl_map = {
                "idle": 0, "browsing": 1, "coding": 2, "compilation": 2,
                "media_processing": 2, "gaming": 3, "video_call": 1
            }
            return wl_map.get(wl_str, 2), conf
    except Exception:
        pass
    return 2, 0.85


def flag_anomaly(get_workload_id=None):
    """
    Continuously predict anomalies using the workload-specific baseline.

    Parameters
    ----------
    get_workload_id : callable, optional
        A function that returns the current workload integer (0-3).
        Called every tick so the baseline can switch dynamically when
        FocusOS detects a workload change. If None, reads from workload_events.
    """
    if get_workload_id is None:
        get_workload_id = _get_default_workload_id

    # Pre-load all available workload models so switching is instant.
    models = {}
    for wid in WORKLOADS:
        try:
            model, scaler, name = _load_workload_assets(wid)
            models[wid] = {"model": model, "scaler": scaler, "name": name}
            print(f"[predict] Loaded model for workload '{name}'")
        except FileNotFoundError as e:
            print(f"[predict] {e}")

    if not models:
        print("[predict] No trained models found. Cannot start prediction.")
        return

    print(f"[predict] Anomaly detection started. {len(models)} workload model(s) loaded.")

    try:
        while True:
            try:
                workload_input = get_workload_id()
                if isinstance(workload_input, (tuple, list)):
                    workload_id = workload_input[0]
                    focusos_confidence = float(workload_input[1]) if len(workload_input) > 1 and workload_input[1] is not None else 0.85
                elif isinstance(workload_input, dict):
                    workload_id = workload_input.get("workload_id")
                    focusos_confidence = float(workload_input.get("confidence", 0.85))
                else:
                    workload_id = workload_input
                    focusos_confidence = 0.85

                if workload_id not in models:
                    # Fallback to an available model (e.g. coding or first loaded)
                    fallback_id = 2 if 2 in models else next(iter(models.keys()))
                    workload_id = fallback_id

                assets = models[workload_id]
                model = assets["model"]
                scaler = assets["scaler"]
                name = assets["name"]

                # Get raw features (unscaled) — we scale with the workload-specific scaler.
                raw_df, _, metadata = get_inference_payload_predict(DB_PATH)

                if raw_df is None:
                    time.sleep(5)
                    continue

                raw_df = raw_df[ML_FEATURES].apply(pd.to_numeric, errors="coerce").fillna(0.0)

                # Scale with the workload-specific scaler
                scaled_array = scaler.transform(raw_df.values)
                scaled_df = pd.DataFrame(scaled_array, columns=ML_FEATURES, index=raw_df.index)

                anomaly_score = model.decision_function(scaled_array)
                prediction = model.predict(scaled_array)

                print(f"[{name}] Anomaly score: {round(anomaly_score[0], 4)} (FocusOS conf: {focusos_confidence})")

                if prediction[0] == -1:
                    print(f"[{name}] ⚠ ANOMALY detected! Score: {round(anomaly_score[0], 4)}")

                    data = {
                        "raw": raw_df.to_dict(orient="records")[0],
                        "scaled": scaled_df.to_dict(orient="records")[0],
                        "workload_id": workload_id,
                        "workload_name": name,
                        "focusos_confidence": focusos_confidence,
                        "anomaly_score": round(anomaly_score[0], 4),
                    }
                    write_to_alerts_table(data, metadata)

            except Exception as e:
                print(f"[predict] Error in flag_anomaly: {e}")

            time.sleep(5)

    except KeyboardInterrupt:
        print("\n[predict] Anomaly detection stopped.")
