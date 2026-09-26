""" featuring raw data to useful data."""
import sqlite3
import json
import os
from datetime import datetime
import pandas as pd

#scaling
from sklearn.preprocessing import RobustScaler
import joblib

# single source of truth for where the fitted scaler lives (absolute path)
from config import DB_PATH

# The 24 features the Isolation Forest is trained on, in a FIXED order.
# os_doctor_db.py (training table), i_forest_train.py and inference all import
# this list, so the column order can never drift between them.
ML_FEATURES = [
    # A. scheduler / CPU contention
    "nr_running_per_core",
    "involuntary_context_switch_rate",
    "uninterruptible_d_state_count",
    # B. CPU
    "cpu_usage_percent",
    "cpu_usage_percent_gradient",
    "cpu_iowait_time",              # NOTE: percent of CPU time in iowait, not seconds since boot
    "cpu_psi_some_avg10",
    # C. memory
    "memory_percent",
    "memory_percent_gradient",
    "memory_psi_full_avg10",
    "direct_reclaim_rate",
    "major_page_fault_rate",
    "swap_out_rate",
    # D. storage / I/O
    "disk_read_mb_s",
    "disk_write_mb_s",
    "io_latency",
    "io_psi_some_avg10",
    "io_psi_full_avg10",
    # E. resource leaks
    "open_fds_gradient",
    "thread_count_gradient",
    "zombie_process_count",
    # F. hardware / thermal
    "cpu_frequency_deviation",
    "thermal_throttling_events",
    # G. network
    "tcp_retrans_rate",
]

# layer1_sys column -> ML feature, taken as the latest value
_LATEST_VALUE_FEATURES = {
    "nr_running_per_core": "nr_running_per_core",
    "involuntary_context_switch_rate": "involuntary_context_switch_rate",
    "uninterruptible_d_state_count": "uninterruptible_d_state_count",
    "cpu_usage_percent": "cpu_usage_percent",
    "cpu_iowait_percent": "cpu_iowait_time",
    "cpu_psi_some_avg10": "cpu_psi_some_avg10",
    "memory_percent": "memory_percent",
    "memory_psi_full_avg10": "memory_psi_full_avg10",
    "direct_reclaim_rate": "direct_reclaim_rate",
    "major_page_fault_rate": "major_page_fault_rate",
    "swap_out_rate": "swap_out_rate",
    "disk_read_mb_s": "disk_read_mb_s",
    "disk_write_mb_s": "disk_write_mb_s",
    "io_latency": "io_latency",
    "io_psi_some_avg10": "io_psi_some_avg10",
    "io_psi_full_avg10": "io_psi_full_avg10",
    "zombie_processes": "zombie_process_count",
    "thermal_throttling_events": "thermal_throttling_events",
    "tcp_retrans_rate": "tcp_retrans_rate",
}

# layer1_sys column -> ML feature, as change per second between the last two rows
_GRADIENT_FEATURES = {
    "cpu_usage_percent": "cpu_usage_percent_gradient",
    "memory_percent": "memory_percent_gradient",
    "system_open_fds": "open_fds_gradient",
    "num_threads": "thread_count_gradient",
}

# layer1_sys column -> ML feature, as (latest value - 120-row rolling mean)
_DEVIATION_FEATURES = {
    "cpu_freq": "cpu_frequency_deviation",
}

# NOTE: On macOS many Linux-only columns (nr_running_per_core, PSI, vmstat,
# etc.) are always NULL.  We no longer filter rows by a "ready marker"
# column because that would exclude every row on non-Linux platforms.
# NULLs are safely coerced to 0.0 via pd.to_numeric + fillna downstream.


def _to_epoch_seconds(iso_text):
    # datetime.isoformat() drops ".ffffff" when microseconds == 0, which breaks
    # pandas' format guessing, so parse each value with fromisoformat instead.
    try:
        return datetime.fromisoformat(iso_text).timestamp()
    except (TypeError, ValueError):
        return float("nan")


def extract_and_engineer_sys(db_path, window_size=120):
    source_cols = sorted(set(_LATEST_VALUE_FEATURES) | set(_GRADIENT_FEATURES) | set(_DEVIATION_FEATURES))
    # ORDER BY id (insert order), not timestamp: a backwards clock jump (NTP)
    # would otherwise shuffle the rows.
    query = f"""
        SELECT id, timestamp, {', '.join(source_cols)}
        FROM layer1_sys
        ORDER BY id DESC
        LIMIT ?
    """

    with sqlite3.connect(db_path) as conn:

        conn.execute("PRAGMA journal_mode=WAL")

        df_sys = pd.read_sql_query(query, conn, params=(window_size,))

    if len(df_sys) < 2:
        return pd.DataFrame()

    # Data comes back newest-first (DESC); flip to chronological order so
    # diff()/rolling() see the correct time direction and .iloc[-1] is "now".
    df_sys = df_sys.iloc[::-1].reset_index(drop=True)

    # All-NULL columns load as dtype=object with None; coerce to numeric (NaN).
    # NaN is turned into 0.0 only at the very end.
    for col in source_cols:
        df_sys[col] = pd.to_numeric(df_sys[col], errors='coerce')

    features = {}

    for src, name in _LATEST_VALUE_FEATURES.items():
        features[name] = df_sys[src].iloc[-1]

    # Gradients are per SECOND, using the real gap between the last two rows.
    # Rows are ~1.2-1.5 s apart (work + 1 s sleep), not exactly 1 s.
    epoch = df_sys['timestamp'].map(_to_epoch_seconds)
    gap = epoch.iloc[-1] - epoch.iloc[-2]
    for src, name in _GRADIENT_FEATURES.items():
        change = df_sys[src].iloc[-1] - df_sys[src].iloc[-2]
        features[name] = change / gap if gap > 0 else float("nan")

    for src, name in _DEVIATION_FEATURES.items():
        rolling_baseline = df_sys[src].rolling(window=120, min_periods=1).mean()
        features[name] = df_sys[src].iloc[-1] - rolling_baseline.iloc[-1]

    # Single-row frame [1, 24] in the fixed ML_FEATURES order; missing -> 0.0
    sys_vec = pd.DataFrame([{name: features[name] for name in ML_FEATURES}])
    sys_vec = sys_vec.astype(float).fillna(0.0).round(4)
    sys_vec['timestamp'] = df_sys['timestamp'].iloc[-1]   # metadata, not a feature
    return sys_vec

def extract_and_engineer_processes(db_path, window_size=24):

    query = """
            SELECT timestamp,
            cpu_1_pid, cpu_1_ppid, cpu_1_name, cpu_1_status, cpu_1_cpu_peak, 
            cpu_2_pid, cpu_2_ppid, cpu_2_name, cpu_2_status, cpu_2_cpu_peak,
            cpu_3_pid, cpu_3_ppid, cpu_3_name, cpu_3_status, cpu_3_cpu_peak,
            cpu_4_pid, cpu_4_ppid, cpu_4_name, cpu_4_status, cpu_4_cpu_peak,
            cpu_5_pid, cpu_5_ppid, cpu_5_name, cpu_5_status, cpu_5_cpu_peak,    
            ram_1_pid, ram_1_ppid, ram_1_name, ram_1_status, ram_1_peak, ram_1_open_fds,
            ram_2_pid, ram_2_ppid, ram_2_name, ram_2_status, ram_2_peak, ram_2_open_fds,
            ram_3_pid, ram_3_ppid, ram_3_name, ram_3_status, ram_3_peak, ram_3_open_fds,
            ram_4_pid, ram_4_ppid, ram_4_name, ram_4_status, ram_4_peak, ram_4_open_fds,
            ram_5_pid, ram_5_ppid, ram_5_name, ram_5_status, ram_5_peak, ram_5_open_fds

            FROM layer2_proc
            ORDER BY id DESC
            LIMIT ?
        """
    
    with sqlite3.connect(db_path) as conn:

        conn.execute("PRAGMA journal_mode=WAL")

        df_raw = pd.read_sql_query(query, conn, params=(window_size,))

    df_raw = df_raw.iloc[::-1].reset_index(drop=True)

    cols = ['cpu_1_pid', 'cpu_1_ppid', 'cpu_1_name', 'cpu_1_status', 'cpu_1_cpu_peak',
           'cpu_2_pid', 'cpu_2_ppid', 'cpu_2_name', 'cpu_2_status', 'cpu_2_cpu_peak',
           'cpu_3_pid', 'cpu_3_ppid', 'cpu_3_name', 'cpu_3_status', 'cpu_3_cpu_peak',
           'cpu_4_pid', 'cpu_4_ppid', 'cpu_4_name', 'cpu_4_status', 'cpu_4_cpu_peak',
           'cpu_5_pid', 'cpu_5_ppid', 'cpu_5_name', 'cpu_5_status', 'cpu_5_cpu_peak',
           'ram_1_pid', 'ram_1_ppid', 'ram_1_name', 'ram_1_status', 'ram_1_peak', 'ram_1_open_fds',
           'ram_2_pid', 'ram_2_ppid', 'ram_2_name', 'ram_2_status', 'ram_2_peak', 'ram_2_open_fds',
           'ram_3_pid', 'ram_3_ppid', 'ram_3_name', 'ram_3_status', 'ram_3_peak', 'ram_3_open_fds',
           'ram_4_pid', 'ram_4_ppid', 'ram_4_name', 'ram_4_status', 'ram_4_peak', 'ram_4_open_fds',
           'ram_5_pid', 'ram_5_ppid', 'ram_5_name', 'ram_5_status', 'ram_5_peak', 'ram_5_open_fds']

    flat_proc_dict = {}

    # Names and statuses are text. Before, they were coerced to numbers too,
    # so every process name in the metadata became 0.0.
    text_cols = [col for col in cols if col.endswith('_name') or col.endswith('_status')]
    numeric_cols = [col for col in cols if col not in text_cols]

    for col in numeric_cols:
        if col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0.0)

    df_raw = df_raw.copy()
    for col in numeric_cols:
            df_raw[f'{col}_gradient'] = df_raw[col].diff(periods=1).fillna(0.0)
    
    for col in numeric_cols:
        flat_proc_dict[f'{col}_gradient'] = round(df_raw[f'{col}_gradient'].iloc[-1], 2)
        flat_proc_dict[f'{col}'] = round(df_raw[f'{col}'].iloc[-1], 2)

    for col in text_cols:
        flat_proc_dict[col] = df_raw[col].iloc[-1]

    
    proc_vec = pd.DataFrame([flat_proc_dict])
    # Return single row vector for cpu and ram
    # print(proc_vec)
    return proc_vec

#   Separates the Isolation Forest input (the 24 ML_FEATURES) from
#   human-readable metadata. Process data is NOT an ML feature any more;
#   it is kept in the metadata for diagnosis after an anomaly is found.
    
def build_unified_vector(sys_vec, proc_vec):

    ml_features_df = sys_vec[ML_FEATURES].astype(float)

    metadata_payload = {"timestamp": sys_vec['timestamp'].iloc[0]}
    for col, value in proc_vec.iloc[0].to_dict().items():
        # a PID "gradient" has no meaning, skip it
        if col.endswith('_pid_gradient') or col.endswith('_ppid_gradient'):
            continue
        metadata_payload[col] = value

    return ml_features_df, metadata_payload



# NEW: FEATURE SCALING LAYER

# Placement in the pipeline (see docstrings below):

#   raw telemetry -> extract features -> gradients -> rolling averages ->
#   build_unified_vector() [concatenation + metadata removal] ->
#   >>> SCALING HAPPENS HERE <<< -> Isolation Forest
#
# RobustScaler is used (median/IQR-based) instead of StandardScaler or

# Metadata (PID, PPID, process name) is never touched — it was already stripped out by build_unified_vector() before this stage runs.


def fit_and_save_scaler(ml_features_df, scaler_path):
    """
    OFFLINE TRAINING ONLY.

    Fits a RobustScaler on the historical/offline training feature matrix
    and persists it to disk with joblib. This is the ONLY place in the
    codebase where `.fit()` / `.fit_transform()` is called on the scaler.

    Parameters
    ----------
    ml_features_df : pd.DataFrame
        The full training-set numerical feature matrix (metadata already
        removed, as produced by build_unified_vector / concatenation of
        many historical ticks).
    scaler_path : str
        Where to persist the fitted scaler.

    Returns
    -------
    scaler : RobustScaler (fitted)
    ml_features_scaled_df : pd.DataFrame (scaled training features)
    """
    ml_features_df = ml_features_df[ML_FEATURES]   # fixed column order
    scaler = RobustScaler()

    scaled_array = scaler.fit_transform(ml_features_df.values)  # fit ONLY here

    ml_features_scaled_df = pd.DataFrame(
        scaled_array,
        columns=ml_features_df.columns,
        index=ml_features_df.index,
    )

    os.makedirs(os.path.dirname(scaler_path), exist_ok=True)
    joblib.dump(scaler, scaler_path)

    return scaler, ml_features_scaled_df


def load_scaler(scaler_path):
    """
    INFERENCE / RUNTIME ONLY.

    Loads the previously fitted RobustScaler from disk. Never fits.
    Raises a clear error if training hasn't happened yet, rather than
    silently falling back to an unfitted scaler.
    """
    if not os.path.exists(scaler_path):
        raise FileNotFoundError(
            f"No fitted scaler found at '{scaler_path}'. "
            "Run offline training (fit_and_save_scaler) before starting "
            "real-time inference."
        )
    return joblib.load(scaler_path)


def scale_features(ml_features_df, scaler):
    """
    Applies an already-fitted scaler to a feature matrix. Used both at the
    end of training (on validation data) and at every inference tick.
    Only ever calls `.transform()` — never `.fit()` or `.fit_transform()`.

    Metadata columns are never passed into this function; the caller is
    expected to pass only the output of build_unified_vector()'s
    ml_features_df, which already excludes PID/PPID/name columns.
    """
    ml_features_df = ml_features_df[ML_FEATURES]   # same order as at training time
    scaled_array = scaler.transform(ml_features_df.values)

    return pd.DataFrame(
        scaled_array,
        columns=ml_features_df.columns,
        index=ml_features_df.index,
    )

def get_inference_payload_predict(db_path, scaler=None):
    """
    Centralized orchestration function called by the main daemon loop.
 
    CHANGED: now always returns the RAW (unscaled) feature frame alongside
    an optional SCALED one, instead of overwriting raw -> scaled in place.
    Callers that need raw values for storage/display (alerts, LLM layer)
    and callers that need scaled values for the model (Isolation Forest)
    both get what they need from a single call, with no ambiguity based
    on whether `scaler` was passed.
 
    Returns
    -------
    (ml_features_raw_df, ml_features_scaled_df, metadata)
        ml_features_scaled_df is None if no scaler was provided.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM layer2_proc;")
            row_count_layer2 = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM layer1_sys;")
            row_count_layer1 = cursor.fetchone()[0]
 
        if row_count_layer1 < 120 or row_count_layer2 < 24:
            print(f"Pipeline Warm-up Phase: {row_count_layer1}/120 records collected. Skipping tick.")
            print(f"Pipeline Warm-up Phase: {row_count_layer2}/24 records collected. Skipping tick.")
            return None, None, None
 
    except sqlite3.Error as e:
        print(f"Database error during warm-up check: {e}")
        return None, None, None
 
    try:
        sys_vec = extract_and_engineer_sys(db_path)
        proc_vec = extract_and_engineer_processes(db_path)
 
        if sys_vec.empty or proc_vec.empty:
            print("Warning: One of the sub-vectors returned an empty frame. Skipping inference.")
            return None, None, None
 
        # Raw features, kept as-is — this is what gets stored/displayed.
        ml_features_raw_df, metadata = build_unified_vector(sys_vec, proc_vec)
 
        # Scaled features, computed into a SEPARATE frame — raw is never
        # mutated, so callers can't accidentally lose it.
        ml_features_scaled_df = None
        if scaler is not None:
            ml_features_scaled_df = scale_features(ml_features_raw_df, scaler)
 
        return ml_features_raw_df, ml_features_scaled_df, metadata
    except Exception as e:
        print(f"Critical error during feature engineering pipeline orchestration: {e}")
        return None, None, None

def get_inference_payload_train(db_path, scaler=None):
    # Run safety check to ensure database has enough historical data
    # We need a minimum of 120 rows (120 seconds) of system metrics to build our vectors
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM layer2_proc;")
            row_count_layer2 = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM layer1_sys;")
            row_count_layer1 = cursor.fetchone()[0]
            
        
        if row_count_layer1 < 120 or row_count_layer2 < 24:
           
            print(f"Pipeline Warm-up Phase: {row_count_layer1}/120 records collected. Skipping tick.")
            print(f"Pipeline Warm-up Phase: {row_count_layer2}/24 records collected. Skipping tick.")
            return None, None
            
    except sqlite3.Error as e:
        print(f"Database error during warm-up check: {e}")
        return None, None

    # Sequential execution 
    try:
        # 1. Fetch system vector
        sys_vec = extract_and_engineer_sys(db_path)
        
        # 2. Fetch process vectors 
        proc_vec = extract_and_engineer_processes(db_path)
        
        # 3. Check for empty payloads before stitching to prevent concat failures
        if sys_vec.empty or proc_vec.empty:
            print("Warning: One of the sub-vectors returned an empty frame. Skipping inference.")
            return None, None
            
        # 4. Consolidate and strip metadata 
        ml_features_df, metadata = build_unified_vector(sys_vec, proc_vec)

        # NEW: 5. Scale numerical features only (transform-only, no fit)
        if scaler is not None:
            ml_features_df = scale_features(ml_features_df, scaler)
        
        return ml_features_df, metadata

    except Exception as e:
        print(f"Critical error during feature engineering pipeline orchestration: {e}")
        return None, None

if __name__ == "__main__":
    features, metadata = get_inference_payload_train(DB_PATH)
    if features is not None:
        print(features.T)