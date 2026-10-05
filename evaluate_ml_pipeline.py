#!/usr/bin/env python3
"""
DIRECTIVE: MACHINE LEARNING PIPELINE EVALUATION
Evaluates and validates the FocusOS XGBoost architecture using focusos_training_data_ideapad.csv.
Tests mathematical accuracy, confusion matrix, and feature importances.
"""

import os
import sys
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import xgboost as xgb

# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA INGESTION & PREPROCESSING
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_CANDIDATES = [
    os.path.join(BASE_DIR, "focusos_training_data_ideapad.csv"),
    os.path.join(os.path.expanduser("~"), "focusos_training_data_ideapad.csv"),
    "/home/nikhil/Desktop/updated models/focusos_training_data_ideapad.csv",
]

csv_path = None
for candidate in CSV_CANDIDATES:
    if os.path.exists(candidate):
        csv_path = candidate
        break

if not csv_path:
    raise FileNotFoundError("Could not locate focusos_training_data_ideapad.csv in candidate paths.")

print("=" * 70)
print("  FOCUSOS MACHINE LEARNING PIPELINE EVALUATION")
print("=" * 70)
print(f"[*] Ingesting dataset: {csv_path}")

df = pd.read_csv(csv_path)
print(f"[*] Ingested {len(df)} records across {len(df.columns)} columns.")

TARGET_COL = "workload_label"
if TARGET_COL not in df.columns:
    raise ValueError(f"Target column '{TARGET_COL}' not found in dataset.")

# Isolate feature columns (22 features)
feature_cols = [c for c in df.columns if c != TARGET_COL]
print(f"[*] Isolated {len(feature_cols)} feature columns:")
print("   ", ", ".join(feature_cols))

X = df[feature_cols].copy()
y_raw = df[TARGET_COL].astype(str).str.upper().values

# Encode labels
le = LabelEncoder()
y = le.fit_transform(y_raw)
class_names = [str(cls) for cls in le.classes_]
print(f"[*] Target classes detected ({len(class_names)}): {class_names}")

# Stratified 80/20 train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)
print(f"[*] Train/Test split: {len(X_train)} training / {len(X_test)} validation samples.")

# Standardize feature matrix with StandardScaler
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
print("[*] Applied StandardScaler to erase scale differences (zero mean, unit variance).")

# ─────────────────────────────────────────────────────────────────────────────
# 2. MODEL TRAINING ENGINES
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "-" * 70)
print("  INITIALIZING & TRAINING XGBOOST CLASSIFIER")
print("-" * 70)

params = {
    "n_estimators": 100,
    "max_depth": 5,
    "learning_rate": 0.1,
    "subsample": 0.8,
    "objective": "multi:softprob",
    "eval_metric": "mlogloss",
    "random_state": 42,
    "n_jobs": -1,
}
print(f"[*] Hyperparameters: {params}")

clf = xgb.XGBClassifier(**params)
clf.fit(
    X_train_scaled,
    y_train,
    eval_set=[(X_test_scaled, y_test)],
    verbose=False
)
print("[✓] Model training completed successfully.")

# ─────────────────────────────────────────────────────────────────────────────
# 3. RIGOROUS DIAGNOSTIC EVALUATION
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  RIGOROUS DIAGNOSTIC EVALUATION REPORT")
print("=" * 70)

y_pred = clf.predict(X_test_scaled)
overall_acc = np.mean(y_pred == y_test) * 100
print(f"\n[+] Validation Accuracy: {overall_acc:.2f}%\n")

print("[+] Classification Report:")
report_str = classification_report(y_test, y_pred, target_names=class_names, digits=4)
print(report_str)

print("[+] Confusion Matrix (Actual rows vs Predicted columns):")
cm = confusion_matrix(y_test, y_pred)
cm_df = pd.DataFrame(cm, index=[f"Actual_{c}" for c in class_names], columns=[f"Pred_{c}" for c in class_names])
print(cm_df.to_string())

# ─────────────────────────────────────────────────────────────────────────────
# 4. FEATURE IMPORTANCE (SHORTCUT LEARNING PROOF)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  FEATURE IMPORTANCE (GAIN) & DECISION ANALYSIS")
print("=" * 70)

importances = clf.feature_importances_
feat_imp = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)

print(f"{'Rank':<5} | {'Feature Name':<26} | {'Gain Weight':<12} | {'Visual Distribution'}")
print("-" * 70)
for rank, (feat, weight) in enumerate(feat_imp[:10], 1):
    bar = "█" * int(weight * 40)
    print(f"#{rank:<4} | {feat:<26} | {weight:<12.4f} | {bar}")

print("\n[*] Full Feature Ranking Summary:")
for rank, (feat, weight) in enumerate(feat_imp, 1):
    print(f"   {rank:>2}. {feat:<24}: {weight:.4f}")

# Critical assertions verification
top_10_feats = [f[0] for f in feat_imp[:10]]
key_context_features = [
    f for f in ["vscode_active", "browser_active", "compiler_active", "network_symmetry", "udp_tcp_ratio"]
    if f in feature_cols
]

print("\n[+] Verification of Key Decision Features:")
for feat in key_context_features:
    rank = next(idx for idx, (f, _) in enumerate(feat_imp, 1) if f == feat)
    wt = next(w for f, w in feat_imp if f == feat)
    print(f"   - {feat:<20} -> Rank #{rank} (Weight: {wt:.4f})")

print("\n" + "=" * 70)
print("  EVALUATION COMPLETE")
print("=" * 70)
