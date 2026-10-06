"""
FocusOS XGBoost Workload Classifier
Trains and serves direct supervised XGBoost classifier on the 22-feature
system telemetry vector, exposing WorkloadPredictor for live inference.

Workload classes: idle · coding · browsing · video_call
"""

import os
import sys
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import threading
import xgboost as xgb

# ──────────────────────────────────────────────────────────────────────
# Path Configuration
# ──────────────────────────────────────────────────────────────────────
CURRENT_FILE = os.path.abspath(__file__)
PROJECT_DIR = os.path.dirname(CURRENT_FILE)
MODELS_DIR = os.path.join(PROJECT_DIR, "models_saved")

# Search order for the training CSV
_CANDIDATE_DATASET_PATHS = [
    os.path.join(os.path.dirname(os.path.dirname(PROJECT_DIR)), "focusos_training_data_ideapad.csv"),
    os.path.join(PROJECT_DIR, "focusos_training_data_ideapad.csv"),
    os.path.join(MODELS_DIR, "focusos_training_data_ideapad.csv"),
    os.path.join(os.path.expanduser("~"), "focusos_training_data_ideapad.csv"),
]
DATASET_PATH = next(
    (p for p in _CANDIDATE_DATASET_PATHS if os.path.exists(p)),
    _CANDIDATE_DATASET_PATHS[0],
)

# ──────────────────────────────────────────────────────────────────────
# Full 22-Feature Schema (must match generate_dataset_ideapad.py)
# ──────────────────────────────────────────────────────────────────────
FEATURE_COLUMNS = [
    "cpu_mean",
    "cpu_max",
    "cpu_variance",
    "ram_mean",
    "ram_growth_rate",
    "swap_percent",
    "network_mean",
    "network_symmetry",
    "net_variance",
    "udp_tcp_ratio",
    "disk_io_mean",
    "process_count_mean",
    "thread_count_mean",
    "load_avg",
    "ctx_switches_per_core",
    "cpu_user_system_ratio",
    "psi_cpu_some",
    "psi_mem_some",
    "psi_io_some",
    "vscode_active",
    "browser_active",
    "compiler_active",
]

EXPECTED_CLASSES = {"idle", "coding", "browsing", "video_call"}


# ──────────────────────────────────────────────────────────────────────
# Inference Predictor
# ──────────────────────────────────────────────────────────────────────
class WorkloadPredictor:
    """Production inference predictor for FocusOS workload classification."""

    def __init__(self, models_dir: str = None):
        if not models_dir or not os.path.exists(os.path.join(models_dir, "xgboost_model.json")):
            candidates = [
                MODELS_DIR,
                os.path.join(os.path.dirname(PROJECT_DIR), "models_saved"),
                os.path.join(os.path.dirname(os.path.dirname(PROJECT_DIR)), "focusos/models_saved"),
                os.path.join(os.path.dirname(os.path.dirname(PROJECT_DIR)), "focusos/models/models_saved"),
            ]
            for c in candidates:
                if os.path.exists(os.path.join(c, "xgboost_model.json")):
                    models_dir = c
                    break
        self.models_dir = models_dir or MODELS_DIR
        self.scaler: StandardScaler = joblib.load(
            os.path.join(self.models_dir, "scaler.pkl")
        )
        self.label_encoder: LabelEncoder = joblib.load(
            os.path.join(self.models_dir, "label_encoder.pkl")
        )
        self.xgb = xgb.XGBClassifier()
        self.xgb.load_model(os.path.join(self.models_dir, "xgboost_model.json"))

    def predict(self, features_df: pd.DataFrame) -> dict | list[dict] | None:
        """
        Predict workload for one or more feature rows.

        Parameters
        ----------
        features_df : pd.DataFrame
            DataFrame with columns matching ``FEATURE_COLUMNS``.

        Returns
        -------
        dict for a single row, list[dict] for multiple rows, or None if empty.
        """
        if features_df is None or features_df.empty:
            return None

        # Validate required columns
        missing = sorted(set(FEATURE_COLUMNS) - set(features_df.columns))
        if missing:
            raise ValueError(f"Input is missing required features: {missing}")

        X_input = features_df[FEATURE_COLUMNS].astype(float)

        # Guard against NaN / Inf slipping through the collector pipeline
        if not np.isfinite(X_input.to_numpy()).all():
            raise ValueError("Input contains NaN or non-finite feature values.")

        scaled = self.scaler.transform(X_input)
        probs = self.xgb.predict_proba(scaled)

        results = []
        for i in range(len(scaled)):
            row_probs = probs[i]
            pred_idx = int(np.argmax(row_probs))
            workload_name = str(
                self.label_encoder.inverse_transform([pred_idx])[0]
            )
            confidence = float(row_probs[pred_idx] * 100)

            # Build per-class probability breakdown
            class_probs = {
                str(self.label_encoder.inverse_transform([j])[0]): round(
                    float(row_probs[j]) * 100, 2
                )
                for j in range(len(row_probs))
            }

            results.append(
                {
                    "workload": workload_name,
                    "confidence": round(confidence, 2),
                    "probabilities": class_probs,
                }
            )

        return results[0] if len(results) == 1 else results


# ──────────────────────────────────────────────────────────────────────
# Production Live Inference Service
# ──────────────────────────────────────────────────────────────────────
_GLOBAL_PREDICTOR = None
_GLOBAL_PREDICTOR_LOCK = threading.Lock()


def get_predictor(models_dir: str = None) -> WorkloadPredictor:
    """Thread-safe singleton accessor for WorkloadPredictor."""
    global _GLOBAL_PREDICTOR
    if _GLOBAL_PREDICTOR is None:
        with _GLOBAL_PREDICTOR_LOCK:
            if _GLOBAL_PREDICTOR is None:
                _GLOBAL_PREDICTOR = WorkloadPredictor(models_dir=models_dir)
    return _GLOBAL_PREDICTOR


def predict_live_workload(window_df: pd.DataFrame = None, db_path: str = None) -> dict:
    """
    Executes live workload inference using XGBoost on the current sliding window.

    Returns a standardized dictionary:
    {
        "workload": "CODING" | "BROWSING" | "VIDEO_CALL" | "IDLE" | "UNKNOWN",
        "workload_raw": str,
        "confidence": float (0.0 to 1.0),
        "confidence_pct": float (0.0 to 100.0),
        "probabilities": dict (e.g. {"coding": 0.85, ...}),
        "features": dict of 22 features,
        "model_type": "xgboost",
        "sample_count": int,
        "is_valid": bool,
        "status": str
    }
    """
    from focusos.sliding_window import get_window_from_db
    from focusos.feature_engineer import extract_features

    try:
        if window_df is None:
            window_df = get_window_from_db(db_path=db_path) if db_path else get_window_from_db()

        if window_df is None or window_df.empty:
            return {
                "workload": "IDLE",
                "workload_raw": "idle",
                "confidence": 0.0,
                "confidence_pct": 0.0,
                "probabilities": {"browsing": 0.0, "coding": 0.0, "idle": 1.0, "video_call": 0.0},
                "features": {},
                "model_type": "xgboost",
                "sample_count": 0,
                "is_valid": False,
                "status": "empty_window",
            }

        feats_df = extract_features(window_df)
        if feats_df is None or feats_df.empty:
            return {
                "workload": "UNKNOWN",
                "workload_raw": "unknown",
                "confidence": 0.0,
                "confidence_pct": 0.0,
                "probabilities": {},
                "features": {},
                "model_type": "xgboost",
                "sample_count": len(window_df),
                "is_valid": False,
                "status": "feature_extraction_failed",
            }

        predictor = get_predictor()
        pred = predictor.predict(feats_df)
        if isinstance(pred, list):
            pred = pred[0]

        raw_wl = str(pred.get("workload", "idle")).lower()
        conf_pct = float(pred.get("confidence", 0.0))
        conf_ratio = round(conf_pct / 100.0, 4)
        norm_wl = raw_wl.upper()

        probs_pct = pred.get("probabilities", {})
        probs_ratio = {k: round(float(v) / 100.0, 4) for k, v in probs_pct.items()}
        features_dict = feats_df.iloc[0].to_dict()

        return {
            "workload": norm_wl,
            "workload_raw": raw_wl,
            "confidence": conf_ratio,
            "confidence_pct": conf_pct,
            "probabilities": probs_ratio,
            "probabilities_pct": probs_pct,
            "features": features_dict,
            "model_type": "xgboost",
            "sample_count": len(window_df),
            "is_valid": True,
            "status": "ok",
        }
    except Exception as exc:
        return {
            "workload": "UNKNOWN",
            "workload_raw": "unknown",
            "confidence": 0.0,
            "confidence_pct": 0.0,
            "probabilities": {},
            "features": {},
            "model_type": "xgboost",
            "sample_count": 0,
            "is_valid": False,
            "error": str(exc),
            "status": "error",
        }



# ──────────────────────────────────────────────────────────────────────
# Training Pipeline
# ──────────────────────────────────────────────────────────────────────
def train_classifier(dataset_path: str = DATASET_PATH) -> None:
    print("\n" + "═" * 64)
    print("  FocusOS — XGBoost Classifier Training (IdeaPad 22-Core)")
    print("═" * 64)

    os.makedirs(MODELS_DIR, exist_ok=True)

    # ── Load dataset ─────────────────────────────────────────────────
    if not os.path.exists(dataset_path):
        print(f"[train] ✗ Dataset not found: {dataset_path}")
        print("[train]   Run generate_dataset_ideapad.py first, then copy")
        print(f"[train]   the CSV into {PROJECT_DIR}/")
        sys.exit(1)

    df = pd.read_csv(dataset_path)
    print(f"[train] Loaded {len(df)} rows from {dataset_path}")

    # ── Schema validation ────────────────────────────────────────────
    required_cols = FEATURE_COLUMNS + ["workload_label"]
    missing = sorted(set(required_cols) - set(df.columns))
    if missing:
        raise ValueError(f"CSV is missing columns: {missing}")

    # Coerce numeric and drop rows with NaN/Inf
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    finite_mask = np.isfinite(df[FEATURE_COLUMNS].to_numpy()).all(axis=1)
    n_bad = (~finite_mask).sum()
    if n_bad:
        print(f"[train] Dropping {n_bad} rows with non-finite values.")
        df = df.loc[finite_mask].copy()

    # Sanity: non-negative constraints on key columns
    non_neg = [
        "cpu_mean", "cpu_max", "cpu_variance", "ram_mean",
        "network_mean", "disk_io_mean", "process_count_mean",
        "thread_count_mean", "load_avg", "ctx_switches_per_core",
    ]
    neg_mask = (df[non_neg] >= 0).all(axis=1)
    n_neg = (~neg_mask).sum()
    if n_neg:
        print(f"[train] Dropping {n_neg} rows with negative constraint violations.")
        df = df.loc[neg_mask].copy()

    # Validate class labels
    actual_classes = set(df["workload_label"].unique())
    if actual_classes != EXPECTED_CLASSES:
        print(f"[train] ⚠ Expected classes {EXPECTED_CLASSES}, got {actual_classes}")

    print(f"[train] Final clean dataset: {len(df)} rows, {df['workload_label'].nunique()} classes")
    print(f"[train] Class distribution:\n{df['workload_label'].value_counts().to_string()}\n")

    # ── Prepare X, y ─────────────────────────────────────────────────
    X = df[FEATURE_COLUMNS].copy()
    y_raw = df["workload_label"].values

    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    # 80/20 stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"[train] Split: {len(X_train)} train / {len(X_test)} test")

    # ── Fit scaler on training data only ─────────────────────────────
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # ── Save pre-processing artifacts ────────────────────────────────
    joblib.dump(scaler, os.path.join(MODELS_DIR, "scaler.pkl"))
    joblib.dump(le, os.path.join(MODELS_DIR, "label_encoder.pkl"))
    # Save feature column order for downstream validation
    joblib.dump(FEATURE_COLUMNS, os.path.join(MODELS_DIR, "feature_columns.pkl"))
    print(f"[train] Saved scaler, label_encoder, feature_columns → {MODELS_DIR}/")

    # ── Train XGBoost ────────────────────────────────────────────────
    print("[train] Fitting XGBClassifier...")
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        gamma=0.1,
        reg_alpha=0.05,
        reg_lambda=1.0,
        random_state=42,
        eval_metric="mlogloss",
        n_jobs=-1,
    )
    model.fit(
        X_train_scaled,
        y_train,
        eval_set=[(X_test_scaled, y_test)],
        verbose=False,
    )

    # ── Evaluate ─────────────────────────────────────────────────────
    y_pred = model.predict(X_test_scaled)
    accuracy = np.mean(y_pred == y_test)
    target_names = [str(c) for c in le.classes_]

    print(f"\n[eval] Test Accuracy: {accuracy * 100:.2f}%")
    print("\n[eval] Classification Report:")
    print(classification_report(y_test, y_pred, target_names=target_names))
    print("[eval] Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    # Pretty-print with class labels
    cm_df = pd.DataFrame(cm, index=target_names, columns=target_names)
    print(cm_df.to_string())

    # ── Cross-validation sanity ──────────────────────────────────────
    print("\n[eval] 5-Fold Stratified Cross-Validation on full dataset...")
    X_full_scaled = scaler.transform(X)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_full_scaled, y, cv=cv, scoring="accuracy")
    print(f"[eval] CV Accuracy: {cv_scores.mean() * 100:.2f}% ± {cv_scores.std() * 100:.2f}%")

    # ── Feature importance ───────────────────────────────────────────
    print("\n[eval] Top-10 Feature Importances (gain):")
    importances = model.feature_importances_
    feat_imp = sorted(
        zip(FEATURE_COLUMNS, importances), key=lambda x: x[1], reverse=True
    )
    for rank, (feat, imp) in enumerate(feat_imp[:10], 1):
        bar = "█" * int(imp * 50)
        print(f"  {rank:>2}. {feat:<28s} {imp:.4f}  {bar}")

    # ── Save model ───────────────────────────────────────────────────
    model_path = os.path.join(MODELS_DIR, "xgboost_model.json")
    model.save_model(model_path)
    print(f"\n[train] ✓ Model saved → {model_path}")
    print("═" * 64 + "\n")


if __name__ == "__main__":
    train_classifier()
