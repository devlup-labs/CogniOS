""" featuring raw data to useful data."""
import sqlite3
import json
import os
import pandas as pd

#scaling
from sklearn.preprocessing import RobustScaler
import joblib

#  single source of truth for where the fitted scaler lives 
SCALER_PATH = os.path.join(os.path.dirname(__file__), "models", "robust_scaler.joblib")

from config import DB_PATH

def extract_and_engineer_sys(db_path, window_size=120):
    query = """
        SELECT
            timestamp, 
            cpu_usage_percent, cpu_freq, cpu_user_time, cpu_system_time, cpu_iowait_time, cpu_busy_time,
            cpu_ctx_switches,
            memory_percent, swap_percent, disk_read_mb_s, disk_write_mb_s, disk_read_time,
            disk_write_time, net_rate_mb_s, net_errs, net_drops, load_avg_1, total_processes,
            running_processes, sleeping_processes, zombie_processes, avg_temp,
            max_temp, battery_percent
        FROM layer1_sys
        ORDER BY timestamp DESC
        LIMIT ?
    """

    with sqlite3.connect(db_path) as conn:

        conn.execute("PRAGMA journal_mode=WAL")

        df_sys = pd.read_sql_query(query, conn, params=(window_size,))

    # Data comes back newest-first (DESC); flip to chronological order so
    # diff()/rolling() see the correct time direction and .iloc[-1] is "now".
    df_sys = df_sys.iloc[::-1].reset_index(drop=True)

    # Latest timestamp, kept as metadata (not a numeric feature for the model)
    latest_timestamp = df_sys['timestamp'].iloc[-1]

    # Columns that are all-NULL in sqlite (e.g. temp/iowait/cached on platforms
    # that don't report them) load as dtype=object with None, not NaN, which
    # breaks diff()'s subtraction. Coerce to numeric so missing sensors = 0.0.

    flat_sys_dict = {}
    # it into metadata_payload instead of the model's feature matrix.
    # flat_sys_dict['timestamp'] = latest_timestamp

    gradient_cols = [
        'cpu_usage_percent',
        'cpu_iowait_time',
        'memory_percent',
        'disk_read_mb_s', 
        'disk_write_mb_s', 
        'net_rate_mb_s', 
        'running_processes',
    ]

    deviation_cols = [
            'cpu_usage_percent',
            'cpu_ctx_switches',
            'memory_percent',
            'swap_percent',
            'load_avg_1',
            'avg_temp'
        ]

    cols_to_clean = gradient_cols + deviation_cols

    # Handling NaN values
    for col in cols_to_clean:
        if col in df_sys.columns:
            df_sys[col] = pd.to_numeric(df_sys[col], errors='coerce').fillna(0.0)

    for col in gradient_cols:
        df_sys[f'{col}_gradient'] = df_sys[col].diff(periods=1).fillna(0.0)
        df_sys = df_sys.copy()

    for col in gradient_cols:
        flat_sys_dict[f'{col}_gradient'] = round(df_sys[f'{col}_gradient'].iloc[-1], 2)
        flat_sys_dict[f'{col}'] = round(df_sys[f'{col}'].iloc[-1], 2)

    for col in deviation_cols:
        rolling_baseline = df_sys[col].rolling(window=120, min_periods=1).mean()
        df_sys[f'{col}_deviation'] = df_sys[col] - rolling_baseline
        df_sys = df_sys.copy()

    for col in deviation_cols:
        flat_sys_dict[f'{col}_deviation'] = round(df_sys[f'{col}_deviation'].iloc[-1], 2)
        flat_sys_dict[f'{col}'] = round(df_sys[f'{col}'].iloc[-1], 2)

    # Convert to a single-row 2D DataFrame [1, num_sys_features]
    sys_vec = pd.DataFrame([flat_sys_dict])
    sys_vec['timestamp'] = latest_timestamp  # Add timestamp 
    # for col in sys_vec.columns:
    #     print(col)
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
            ORDER BY timestamp DESC
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

    for col in cols:
        if col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0.0)

    for col in cols:
            df_raw[f'{col}_gradient'] = df_raw[col].diff(periods=1).fillna(0.0)
            df_raw = df_raw.copy()
    
    for col in cols:
        flat_proc_dict[f'{col}_gradient'] = round(df_raw[f'{col}_gradient'].iloc[-1], 2)
        flat_proc_dict[f'{col}'] = round(df_raw[f'{col}'].iloc[-1], 2)

    
    proc_vec = pd.DataFrame([flat_proc_dict])
    # Return single row vector for cpu and ram
    # print(proc_vec)
    return proc_vec

#   Concatenates system and process feature spaces into a fixed-dimensional matrix.
#   Separates isolation_forest ready numerical rows from human-readable metadata.
    
def build_unified_vector(sys_vec, proc_vec):

    df_unified = pd.concat([sys_vec, proc_vec], axis=1)
    

    metadata_cols = [col for col in df_unified.columns
                             if col.endswith('_name') or col.endswith('_id') or col.endswith('_ppid') or col.endswith('_pid') or col.endswith('_status')]
    metadata_payload = df_unified[metadata_cols].iloc[0].to_dict()

    cols_to_drop = [col for col in df_unified.columns
                         if col.endswith('_name_gradient') or col.endswith('_name') or col.endswith('_id_gradient') or col.endswith('_id') or col.endswith('_ppid_gradient') or col.endswith('_ppid') or col.endswith('_status_gradient') or col.endswith('_pid') or col.endswith('_pid_gradient') or col.endswith('_status')]
    
    ml_features_df = df_unified.drop(columns=cols_to_drop)

    
    # ml_features_df = ml_features_df.reindex(sorted(ml_features_df.columns), axis=1)

    return ml_features_df, metadata_payload



# NEW: FEATURE SCALING LAYER

# Placement in the pipeline (see docstrings below):

#   raw telemetry -> extract features -> gradients -> rolling averages ->
#   build_unified_vector() [concatenation + metadata removal] ->
#   >>> SCALING HAPPENS HERE <<< -> Isolation Forest
#
# RobustScaler is used (median/IQR-based) instead of StandardScaler or

# Metadata (PID, PPID, process name) is never touched — it was already stripped out by build_unified_vector() before this stage runs.


def fit_and_save_scaler(ml_features_df, scaler_path=SCALER_PATH):
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


def load_scaler(scaler_path=SCALER_PATH):
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
    scaled_array = scaler.transform(ml_features_df.values)

    return pd.DataFrame(
        scaled_array,
        columns=ml_features_df.columns,
        index=ml_features_df.index,
    )


def get_inference_payload(db_path, scaler=None):
    """
    Centralized orchestration function called by the main daemon loop.
    Enforces data safety buffers and executes functions 1, 2, and 3 sequentially.

    NEW: accepts a pre-loaded `scaler` (RobustScaler, already fitted and
    loaded via load_scaler() at service startup). If provided, the returned
    ml_features_df is scaled (transform-only, no fitting) before being handed
    to the Isolation Forest for prediction. Metadata is returned unscaled
    and untouched, exactly as before.
    """
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
    # extract_and_engineer_sys()
    extract_and_engineer_processes(DB_PATH)