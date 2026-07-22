import os
import sys
import time
import sqlite3
import numpy as np
import pandas as pd
import joblib
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

#path setup so imports work from anywhere

CURRENT_FILE = os.path.abspath(__file__)    # Path to the current file

MODELS_DIR = os.path.dirname(CURRENT_FILE)     # Directory containing cluster_trainer.py

FOCUSOS_DIR = os.path.dirname(MODELS_DIR)     # FocusOS package directory


PROJECT_ROOT = os.path.dirname(FOCUSOS_DIR)    # Project root directory (contains config.py)

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)    # Add project root to Python module search path

from config import DB_PATH
from focusos.sliding_window import get_window_from_db
from focusos.feature_engineer import extract_features

N_CLUSTERS = 6   # Matches: Coding, Gaming, Compiling, Video_Call, Idle,browsing

MIN_SAMPLES_REQUIRED = 500     # Minimum number of samples required to train the model

MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models_saved"
)
FEATURE_COLUMNS = [
    "cpu_mean",
    "cpu_max",
    "cpu_variance",
    "ram_mean",
    "ram_growth_rate",
    "network_mean",
    "disk_io_mean",
    "process_count_mean",
    "thread_count_mean",
    "vscode_active",
    "browser_active",
    "compiler_active",
]  

def collect_feature_vectors(
    db_path: str = DB_PATH,
    n_samples: int = MIN_SAMPLES_REQUIRED,
    sample_interval_sec: int = 30,
) -> pd.DataFrame:
    """
    Collects feature vectors by repeatedly calling the sliding window
    and feature engineering pipeline over time.
 
    PURPOSE:
        KMeans needs many data points (feature vectors) to find meaningful
        clusters. One call to get_window_from_db() + extract_features()
        gives us ONE vector (one 2-minute summary). We need hundreds.
 
    RETURNS:
        DataFrame of shape (n_collected, 12) — one row per feature vector.
        May return fewer than n_samples if the DB doesn't have enough history.
    """
    print(f"\n[cluster_trainer] Collecting feature vectors from DB: {db_path}")
    print(f"[cluster_trainer] Target: {n_samples} samples")
 
    feature_rows = []
 
    try:
        with sqlite3.connect(db_path) as conn:
            # ── count total rows available in the DB ──────────────────────
            total_rows_query = "SELECT COUNT(*) FROM layer1_sys"
            total_rows = conn.execute(total_rows_query).fetchone()[0]
            print(f"[cluster_trainer] Total rows in layer1_sys: {total_rows}")
 
          
            WINDOW_SIZE = 120  # matches SLIDING_WIND_N in config
 
            if total_rows < WINDOW_SIZE:
                print(f"[cluster_trainer] ERROR: Need at least {WINDOW_SIZE} rows, "
                      f"only have {total_rows}. Run telemetry collector longer.")
                return pd.DataFrame()
 
            # ── fetch ALL timestamps in order ─────────────────────────────
            # We'll slide a window of 120 rows, stepping by STEP rows each time.
            # STEP = 30 means each sample is offset by 30 seconds from the last.
            # This gives temporal diversity — we sample from different moments.
            timestamps_df = pd.read_sql_query(
                "SELECT id, timestamp FROM layer1_sys ORDER BY timestamp ASC",
                conn
            )
            all_rowids = timestamps_df["id"].tolist()
 
            STEP = 120  # non-overlapping windows to prevent data leakage
 
            # ── slide through history, extract one feature vector per window ──
            windows_collected = 0
            start_idx = 0
 
            while start_idx + WINDOW_SIZE <= len(all_rowids) and windows_collected < n_samples:
               
                window_rowids = all_rowids[start_idx : start_idx + WINDOW_SIZE]
                rowid_list = ",".join(str(r) for r in window_rowids)
 
                # Fetch exactly those rows from the DB
                window_df = pd.read_sql_query(
                    f"SELECT * FROM layer1_sys WHERE id IN ({rowid_list}) "
                    f"ORDER BY timestamp ASC",
                    conn
                )
 
                if len(window_df) < WINDOW_SIZE:    #to check the required size of window 
                    
                    start_idx += STEP
                    continue
 
              
                feature_vec = extract_features(window_df)
 
                if feature_vec is not None and not feature_vec.empty:
                 
                    feature_rows.append(feature_vec)
                    windows_collected += 1
 
                    if windows_collected % 50 == 0:
                        print(f"[cluster_trainer] Collected {windows_collected}/{n_samples} vectors...")
 
                start_idx += STEP  # advance window by STEP rows
 
    except sqlite3.OperationalError as e:
        print(f"[cluster_trainer] DB error: {e}")
        return pd.DataFrame()
 
    if not feature_rows:
        print("[cluster_trainer] No feature vectors collected. Check DB.")
        return pd.DataFrame()
 
    # Stack all 1-row DataFrames into one big DataFrame
    all_features = pd.concat(feature_rows, ignore_index=True)
 
   
    available_cols = [c for c in FEATURE_COLUMNS if c in all_features.columns] 
    all_features = all_features[available_cols]
 
    print(f"[cluster_trainer] Collection complete: {len(all_features)} feature vectors, "
          f"{len(available_cols)} features each")
    return all_features



# SCALING DOWN OF FEATURE 
def scale_features(df: pd.DataFrame):
    """
    Applies StandardScaler to the feature matrix.
 
    StandardScaler: transforms each feature to mean=0, std=1.
    This is CRITICAL — without it, high-range features (thread_count)
    dominate Euclidean distance and clustering becomes meaningless.

    WHY WE SAVE THE SCALER:
       Because every time the cluster scaling will be different.
 
    ARGS:
        df: DataFrame of shape (n_samples, 12) — raw feature values
 
    RETURNS:
        X_scaled: numpy array (n_samples, 12) — scaled features
        scaler:   fitted StandardScaler object (save this!)
    """
    print("\n[cluster_trainer] Scaling features with StandardScaler...")
 
   
    n_before = len(df)            
    df_clean = df.dropna()         #this will help to handle the NaN values for k means training.
    n_after = len(df_clean)
    if n_before != n_after:
        print(f"[cluster_trainer] Dropped {n_before - n_after} rows with NaN values")
 
    if df_clean.empty:
        raise ValueError("No valid feature vectors after dropping NaN rows.")
 
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_clean.values.astype(float))
 
   
    print(f"[cluster_trainer] Scaled {X_scaled.shape[0]} samples × {X_scaled.shape[1]} features")
    print(f"[cluster_trainer] Feature means (should all be ~0): "
          f"{X_scaled.mean(axis=0).round(3)}")
    print(f"[cluster_trainer] Feature stds (should all be ~1):  "
          f"{X_scaled.std(axis=0).round(3)}")
 
    return X_scaled, scaler, df_clean  # return df_clean too (NaN rows dropped)


def plot_elbow_curve(results: list, best_k: int):
    """Plots the inertia curve for the elbow method."""
    ks = [r[0] for r in results]
    inertias = [r[1] for r in results]

    plt.figure(figsize=(8, 5))
    plt.plot(ks, inertias, marker='o', linewidth=2)
    plt.scatter(best_k, inertias[ks.index(best_k)], s=120, color='red', label=f"Suggested k={best_k}")
    plt.xlabel("Number of Clusters (k)")
    plt.ylabel("Inertia")
    plt.title("Elbow Method")
    plt.xticks(ks)
    plt.grid(True)
    plt.legend()
    plt.show()

#ELBOW METHOD
def find_optimal_k(X_scaled: np.ndarray, k_range=range(2, 11), show_plot: bool = True) -> tuple:
    """
        The "elbow" — where the curve bends — is the optimal k.
    """
    print("\n[cluster_trainer] Running elbow method...")
    results = []

    for k in k_range:
        km = KMeans(
            n_clusters=k,
            init='k-means++',
            n_init=10,          # fewer runs here — just for diagnosis
            max_iter=200,
            random_state=42
        )
        km.fit(X_scaled)
        results.append((k, km.inertia_))
        print(f"  k={k:2d}  inertia={km.inertia_:10.1f}")

    # Find the elbow programmatically (largest drop in inertia reduction rate)
    inertias = [r[1] for r in results]
    drops = [inertias[i] - inertias[i+1] for i in range(len(inertias)-1)]
    drop_reduction = [drops[i] - drops[i+1] for i in range(len(drops)-1)]
    best_k_idx = drop_reduction.index(max(drop_reduction)) + 2  # +2 offset
    best_k = list(k_range)[best_k_idx]
    print(f"\n[cluster_trainer] Elbow suggests k={best_k} (verify visually)")

    if show_plot:
        plot_elbow_curve(results, best_k)

    return results, best_k

#train k means 
def train_kmeans(X_scaled: np.ndarray, n_clusters: int = N_CLUSTERS) -> KMeans:
    """
    Fits KMeans clustering on the scaled feature matrix.
 
    WHAT IT PRODUCES:
        model.labels_           → array of shape (n_samples,)
                                   value 0-4: which cluster each window belongs to
        model.cluster_centers_  → array of shape (5, 12)
                                   centroid of each cluster in scaled feature space
        model.inertia_          → float: total within-cluster sum of squares
                                   lower = tighter, more distinct clusters
        model.n_iter_           → how many iterations it actually took
 
    ARGS:
        X_scaled:    scaled feature matrix (n_samples, n_features)
        n_clusters:  number of clusters (default 5)
 
    RETURNS:
        Fitted KMeans model.
    """
    print(f"\n[cluster_trainer] Training KMeans with n_clusters={n_clusters}...")
    print(f"[cluster_trainer] Input shape: {X_scaled.shape}")
 
    model = KMeans(
        n_clusters=n_clusters,
        init='k-means++',
        n_init=20,
        max_iter=200,
        tol=1e-4,
        random_state=42,
        algorithm='lloyd',
        verbose=0,
    )
 
    model.fit(X_scaled)
 
    print(f"[cluster_trainer] Converged in {model.n_iter_} iterations")
    print(f"[cluster_trainer] Final inertia: {model.inertia_:.2f}")
 
    unique, counts = np.unique(model.labels_, return_counts=True)
    print(f"\n[cluster_trainer] Cluster size distribution:")    #this will give the bar graph representation for checking
    for cid, count in zip(unique, counts):
        pct = 100 * count / len(model.labels_)
        bar = "█" * int(pct / 2)
        print(f"  Cluster {cid}: {count:4d} samples ({pct:5.1f}%)  {bar}")
 
    return model

#cluster_inspect

def inspect_clusters(
    model: KMeans,
    df_clean: pd.DataFrame,
    scaler: StandardScaler
) -> None:
    """
    Prints a detailed summary of each cluster's characteristics.
 
        After reading this output, update CLUSTER_TO_WORKLOAD
        in label_mapper.py with your findings.
 
    ARGS:
        model:    fitted KMeans model
        df_clean: original (unscaled) feature DataFrame (NaN rows dropped)
        scaler:   the fitted StandardScaler (to inverse-transform centroids)
    """
    print("\n" + "="*70)
    print(" CLUSTER INSPECTION — Read this to assign workload labels")
    print("="*70)
 
    df_labeled = df_clean.copy()
    df_labeled["cluster_id"] = model.labels_
 
    centroids_original = scaler.inverse_transform(model.cluster_centers_)  #show the centroid in unscaled
    centroids_df = pd.DataFrame(
        centroids_original,
        columns=df_clean.columns,
        index=[f"Cluster_{i}" for i in range(model.n_clusters)]
    )
 
    for cid in range(model.n_clusters):
        subset = df_labeled[df_labeled["cluster_id"] == cid]
        n = len(subset)
        pct = 100 * n / len(df_labeled)
 
        print(f"\n{'─'*60}")
        print(f"  CLUSTER {cid}  ({n} samples, {pct:.1f}%)")
        print(f"{'─'*60}")
        print(f"  {'Feature':<25} {'Mean':>10}  {'Hint'}")
        print(f"  {'─'*25} {'─'*10}  {'─'*20}")
 
        # Print each feature with an interpretation hint
        hints = {
            "cpu_mean":          "high → CPU-heavy workload",
            "cpu_max":           "high → peak CPU spikes",
            "cpu_variance":      "high → bursty CPU usage",
            "ram_mean":          "high → memory-heavy app",
            "ram_growth_rate":   "positive → memory growing (possible leak or load)",
            "network_mean":      "high → network activity (video call, browsing)",
            "disk_io_mean":      "high → disk-heavy (compiling, large file ops)",
            "process_count_mean":"high → many processes running",
            "thread_count_mean": "high → heavily threaded app",
            "vscode_active":     "1 = VSCode detected → likely Coding",
            "browser_active":    "1 = browser open → Browsing or Video Call",
            "compiler_active":   "1 = compiler (gcc/make) → Compiling",
        }
 
        for col in df_clean.columns:
            val = subset[col].mean()
            hint = hints.get(col, "")
            print(f"  {col:<25} {val:>10.3f}  {hint}")
 
    print("\n" + "="*70)
    print(" ACTION REQUIRED:")
    print("  Look at the output above. For each cluster, decide:")
    print("  - Which workload type does it most resemble?")
    print("  - Update CLUSTER_TO_WORKLOAD in label_mapper.py")
    print("\n  Example mapping (YOURS WILL DIFFER):")
    print("  CLUSTER_TO_WORKLOAD = {")
    print("      0: 'Coding',      # vscode_active≈1, moderate cpu")
    print("      1: 'Compiling',   # compiler_active≈1, high cpu")
    print("      2: 'Idle',        # low everything")
    print("      3: 'Video_Call',  # high network, browser_active≈1")
    print("      4: 'Gaming',      # high cpu, no vscode/compiler")
    print("  }")
    print("="*70)
 
 #pseudo code generation 

def generate_pseudo_labels(
    model: KMeans,
    df_clean: pd.DataFrame,
    cluster_to_workload: dict
) -> pd.DataFrame:
    """
    Attaches cluster IDs and workload names to the feature DataFrame.
 
    PURPOSE:
        This is the BRIDGE between unsupervised (KMeans) and supervised (XGBoost).
 
        KMeans discovered groupings in unlabeled data.
        You gave those groups human-readable names (in cluster_to_workload).
        Now we attach those names to every feature vector.
 
        The resulting DataFrame is the TRAINING DATA for XGBoost:
          - features (cpu_mean, vscode_active, etc.) are the X
          - workload_label (Coding, Gaming, etc.) is the y
 
    ARGS:
        model:               fitted KMeans model (has .labels_ attribute)
        df_clean:            feature DataFrame used to train KMeans
        cluster_to_workload: dict mapping {0: 'Coding', 1: 'Gaming', ...}
                             (comes from label_mapper.py — YOU fill this in)
 
    RETURNS:
        DataFrame with all original features + 'cluster_id' + 'workload_label'
    """
    df_out = df_clean.copy()
    df_out["cluster_id"] = model.labels_
    df_out["workload_label"] = [cluster_to_workload.get(c, f"Unknown_{c}")
                                 for c in model.labels_]
 
    print(f"\n[cluster_trainer] Pseudo-label distribution:")
    print(df_out["workload_label"].value_counts().to_string())
 
    return df_out
 
 

 # SAVE MODELS
 
def save_models(model: KMeans, scaler: StandardScaler, save_dir: str = MODELS_DIR) -> None:
    """
    Saves the trained KMeans model and StandardScaler to disk.
 
    PURPOSE:
        Both the model and scaler must be saved together.
        At inference time (every 30 sec), we:
          1. Load the SAME scaler → apply to new feature vector
          2. Load the SAME KMeans → predict cluster (used for pseudo-label
             generation if retraining; NOT used in runtime inference path)
 
        If you save the model but not the scaler, and retrain the scaler
        later on different data, the cluster assignments will be meaningless.
 
    FILES SAVED:
        models_saved/kmeans_model.pkl    → the KMeans model
        models_saved/feature_scaler.pkl  → the StandardScaler
        models_saved/feature_columns.pkl → list of feature column names in order
    """
    os.makedirs(save_dir, exist_ok=True)
 
    model_path  = os.path.join(save_dir, "kmeans_model.pkl")
    scaler_path = os.path.join(save_dir, "feature_scaler.pkl")
    cols_path   = os.path.join(save_dir, "feature_columns.pkl")
 
    joblib.dump(model,           model_path)
    joblib.dump(scaler,          scaler_path)
    joblib.dump(FEATURE_COLUMNS, cols_path)
 
    print(f"\n[cluster_trainer] Models saved:")
    print(f"  KMeans  → {model_path}")
    print(f"  Scaler  → {scaler_path}")
    print(f"  Columns → {cols_path}")

# utils load (used by optimizer and classifier)

def load_scaler(save_dir: str = MODELS_DIR) -> StandardScaler:
    """
    Loads the saved StandardScaler.
 
    Returns: fitted StandardScaler, or None if not found.
    """
    scaler_path = os.path.join(save_dir, "feature_scaler.pkl")
    if not os.path.exists(scaler_path):
        print(f"[cluster_trainer] Scaler not found at {scaler_path}. Run training first.")
        return None
    return joblib.load(scaler_path)
 
 
def load_kmeans(save_dir: str = MODELS_DIR) -> KMeans:
    """
    Loads the saved KMeans model.
 
    Returns: fitted KMeans, or None if not found.
    """
    model_path = os.path.join(save_dir, "kmeans_model.pkl")
    if not os.path.exists(model_path):
        print(f"[cluster_trainer] KMeans not found at {model_path}. Run training first.")
        return None
    return joblib.load(model_path)
 
 
def predict_cluster(
    feature_vector: np.ndarray,
    model: KMeans = None,
    scaler: StandardScaler = None
) -> int:
    """
    Predicts the cluster ID for a single new feature vector.
 
    ARGS:
        feature_vector: 1D array of shape (12,) — one window's features
        model:  KMeans model (loaded from disk if None)
        scaler: StandardScaler (loaded from disk if None)
 
    RETURNS:
        cluster_id (int 0–4)
    """
    if model is None:
        model = load_kmeans()
    if scaler is None:
        scaler = load_scaler()
    if model is None or scaler is None:
        return -1
 
    vec = np.array(feature_vector).reshape(1, -1)  # shape (1, 12)
    vec_scaled = scaler.transform(vec)              # apply same scaler as training
    cluster_id = model.predict(vec_scaled)[0]
    return int(cluster_id)

# main pipeline

def run_training_pipeline(
    db_path: str = DB_PATH,
    n_samples: int = MIN_SAMPLES_REQUIRED,
    run_elbow: bool = False,
    cluster_to_workload: dict = None,
) -> pd.DataFrame:
    """
    Full KMeans training pipeline from raw DB to pseudo-labeled dataset.
 
    ARGS:
        db_path:             path to SQLite DB with telemetry
        n_samples:           how many feature windows to collect
        run_elbow:           if True, runs elbow method to suggest optimal k
        cluster_to_workload: optional mapping {0: 'Coding', ...}
                             if None, trains and inspects only (you fill mapping later)
 
    RETURNS:
        pseudo_labeled_df if cluster_to_workload provided, else None
    """
    print("\n" + "═"*60)
    print(" FocusOS — KMeans Cluster Training Pipeline")
    print("═"*60)
 
    # ── 1. Collect feature vectors 
    df_features = collect_feature_vectors(db_path=db_path, n_samples=n_samples)
 
    if df_features.empty:
        print("[cluster_trainer] ABORT: Not enough data. Collect more telemetry.")
        return None
 
    if len(df_features) < 50:
        print(f"[cluster_trainer] WARNING: Only {len(df_features)} samples. "
              f"Results may be poor. Recommended minimum: 200.")
 
    # ── 2. Scale features 
    X_scaled, scaler, df_clean = scale_features(df_features)
 
    # ── 3.  Elbow method 
    if run_elbow:
        find_optimal_k(X_scaled)
 
    # ── 4. Train KMeans 
    model = train_kmeans(X_scaled, n_clusters=N_CLUSTERS)
 
    # ── 5. Inspect clusters 
    inspect_clusters(model, df_clean, scaler)
 
    # ── 6. Save models 
    save_models(model, scaler)
 
    # ── 7. Generate pseudo-labels (only if mapping provided) 
    if cluster_to_workload is not None:
        df_labeled = generate_pseudo_labels(model, df_clean, cluster_to_workload)
 
        # Save labeled dataset for XGBoost training
        out_path = os.path.join(MODELS_DIR, "pseudo_labeled_dataset.csv")
        df_labeled.to_csv(out_path, index=False)
        print(f"\n[cluster_trainer] Pseudo-labeled dataset saved → {out_path}")
        print(f"[cluster_trainer] Feed this into classifier.py to train XGBoost")
        return df_labeled
 
    print("\n[cluster_trainer] Training complete.")
    print("[cluster_trainer] Next step: read the cluster inspection above,")
    print("[cluster_trainer] update CLUSTER_TO_WORKLOAD in label_mapper.py,")
    print("[cluster_trainer] then re-run with cluster_to_workload argument.")
    return None
 
 
if __name__ == "__main__":
    """
    TYPICAL WORKFLOW:
    
    FIRST RUN (no mapping yet):
        python -m focusos.models.cluster_trainer
        → Collects data, trains, prints cluster inspection
        → You read the output and fill in CLUSTER_TO_WORKLOAD below
    
    SECOND RUN (with your mapping):
        → Uncomment and fill MY_MAPPING below based on first run output
        → Re-run to generate pseudo_labeled_dataset.csv
        → Then run classifier.py to train XGBoost on it
    """
 
    # ── Fill this in after first run, based on inspect_clusters() output ──,Numbers on the LEFT (0–4) come from KMeans,Strings on the RIGHT are what you name each cluster after reading output.,Your mapping WILL differ from this example — read inspect_clusters() output!
    MY_MAPPING = None  # ← set to None on first run; fill in after inspection
 
    run_training_pipeline(
        db_path=DB_PATH,
        n_samples=MIN_SAMPLES_REQUIRED,
        run_elbow=False,          # set True on first run to verify k=5
        cluster_to_workload=MY_MAPPING,
    )