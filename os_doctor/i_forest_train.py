"""Isolation Forest anomaly model for OS Doctor — per-workload training."""
from sklearn.ensemble import IsolationForest
import pandas as pd
from sqlalchemy import create_engine
import os
import joblib

from config import OS_DOCTOR_DB_PATH, OS_DOCTOR_MODELS_DIR, WORKLOADS
from os_doctor.featuring import ML_FEATURES, fit_and_save_scaler


def train_isolation_forest_model(workload_id):
    """
    Train an Isolation Forest model for a specific workload baseline.

    Parameters
    ----------
    workload_id : int
        0 = Idle, 1 = Browsing, 2 = Coding, 3 = Gaming
    """
    if workload_id not in WORKLOADS:
        raise ValueError(f"Unknown workload_id {workload_id}. Must be 0-3.")

    workload = WORKLOADS[workload_id]
    table_name = workload["table"]
    model_path = workload["model_path"]
    scaler_path = workload["scaler_path"]
    name = workload["name"]

    print(f"Training Isolation Forest for workload '{name}' from table '{table_name}'...")

    engine = create_engine(f"sqlite:///{OS_DOCTOR_DB_PATH}")

    df = pd.read_sql_table(
        table_name=table_name,
        con=engine,
    )

    # Select the 24 features BY NAME. id and timestamp are dropped here.
    df = df[ML_FEATURES]

    # Missing values -> 0.0 (the same rule featuring.py uses at inference)
    df = df.apply(pd.to_numeric, errors="coerce").fillna(0.0)

    if len(df) < 256:
        print(f"Warning: only {len(df)} training rows. Collect more data for a reliable model.")

    # Isolation Forest can only split on a feature that varies. A feature that
    # was constant (e.g. memory PSI always 0.00 on an idle machine) is never
    # used, so the model cannot flag an anomaly in it later.
    constant = [col for col in ML_FEATURES if df[col].nunique() <= 1]
    if constant:
        print("Warning: these features never changed in the training data, so the "
              "model is blind to them. Collect data under more varied load:\n  "
              + ", ".join(constant))

    # Scaling: RobustScaler, fitted and saved per workload.
    scaler, df = fit_and_save_scaler(df, scaler_path=scaler_path)

    # HyperParameters
    n_estimators = 100
    contamination = 0.01
    sample_size = min(256, len(df))
    random_state = 42
    max_features = 5  # sqrt(24 features) = 4.9 -> 5
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        max_samples=sample_size,
        random_state=random_state,
        max_features=max_features,
    )

    model.fit(df.values)

    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)
    print(f"[{name}] Model saved to {model_path}. Scaler saved to {scaler_path}.")


def train_all_workloads():
    """Train a separate Isolation Forest for every workload that has data."""
    for wid in sorted(WORKLOADS):
        workload = WORKLOADS[wid]
        try:
            engine = create_engine(f"sqlite:///{OS_DOCTOR_DB_PATH}")
            df = pd.read_sql_table(table_name=workload["table"], con=engine)
            if len(df) == 0:
                print(f"[{workload['name']}] Table '{workload['table']}' is empty. Skipping.")
                continue
        except ValueError:
            print(f"[{workload['name']}] Table '{workload['table']}' not found. Skipping.")
            continue

        train_isolation_forest_model(wid)
