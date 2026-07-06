""" featuring raw data to useful data."""
import sqlite3
import json
import pandas as pd 

def extract_and_engineer_sys(db_path, window_size=120):
    query = """
        SELECT
            timestamp, 
            cpu_usage_percent, cpu_freq, cpu_user_time, cpu_system_time, cpu_idle_time, cpu_iowait_time, cpu_busy_time,
            cpu_ctx_switches,
            memory_percent, memory_used, memory_available,
            memory_cached, memory_buffers, swap_percent, swap_sin, swap_sout,
            disk_usage_percent, disk_read_mb_s, disk_write_mb_s, disk_read_time,
            disk_write_time, net_rate_mb_s, net_bytes_sent,
            net_bytes_recv, net_packets_sent, net_packets_recv,
            net_errs, net_drops, load_avg_1, load_avg_5, load_avg_15, total_processes,
            running_processes, sleeping_processes, zombie_processes, avg_temp,
            max_temp, battery_percent,  process_data
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

    # timestamp/process_data aren't numeric features for the model
    df_sys_numeric = df_sys.drop(columns=['timestamp', 'process_data'])

    # Columns that are all-NULL in sqlite (e.g. temp/iowait/cached on platforms
    # that don't report them) load as dtype=object with None, not NaN, which
    # breaks diff()'s subtraction. Coerce to numeric so missing sensors = 0.0.
    df_sys_numeric = df_sys_numeric.apply(pd.to_numeric, errors='coerce').fillna(0.0)

    df_sys_gradients = df_sys_numeric.diff(periods=1).fillna(0.0)
    df_sys_rolling_avg = df_sys_numeric.rolling(window=window_size, min_periods=1).mean()

    flat_sys_dict = {}

    for col in df_sys_numeric.columns:
        flat_sys_dict[f'sys_{col}'] = df_sys_numeric[col].iloc[-1]
        flat_sys_dict[f'sys_{col}_gradient'] = df_sys_gradients[col].iloc[-1]
        flat_sys_dict[f'sys_{col}_rolling_avg'] = df_sys_rolling_avg[col].iloc[-1]

    # Convert to a single-row 2D DataFrame [1, num_sys_features]
    sys_vec = pd.DataFrame([flat_sys_dict])
    return sys_vec

    
# This function converts json formatted string to a Pandas' Long-Form DataFrame
# Resamples the data and finally returns two vectors cpu_vec and ram_vec

# Flow of our data: sql table + Json -> list of dict -> sep lists -> stretched df -> single-row vector

def extract_and_engineer_processes(db_path, window_size=24):

    query = """
            SELECT timestamp, top_cpu_json, top_ram_json
            FROM layer2_proc
            ORDER BY timestamp DESC
            LIMIT ?
        """
    
    with sqlite3.connect(db_path) as conn:

        conn.execute("PRAGMA journal_mode=WAL")

        df_raw = pd.read_sql_query(query, conn, params=(window_size,))

    df_raw = df_raw.iloc[::-1].reset_index(drop=True)

    parsed_snapshots = []

    # In this block: extracting the json strings into a list of dicts
    for index, row in df_raw.iterrows():
        timestamp = row['timestamp']
        
        try:
            cpu_list = json.loads(row['top_cpu_json'])
            ram_list = json.loads(row['top_ram_json'])
            
            parsed_snapshots.append({
                "timestamp": timestamp,
                "cpu_processes": cpu_list,  
                "ram_processes": ram_list 
            })
            
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Skipping corrupt database row at frame {timestamp}: {e}")
            continue

    # In this block: converting the list of dicts to separate lists 
    long_form_cpu_rows = []
    long_form_ram_rows = []

    for snapshot in parsed_snapshots:

        ts = snapshot["timestamp"]

        for proc in snapshot["cpu_processes"]:
            long_form_cpu_rows.append({
                "timestamp": ts,
                "pid": proc.get("pid"),
                "ppid": proc.get("ppid"),
                "name": proc.get("name"),
                "cpu_score": proc.get("cpu_score"),
                "cpu_avg": proc.get("cpu_avg"),
                "cpu_peak": proc.get("cpu_peak"),
                "user_time": proc.get("user_time"),
                "system_time": proc.get("system_time"),
                "ctx_vol_rate": proc.get("ctx_vol_rate"),
                "ctx_invol_rate": proc.get("ctx_invol_rate"),
            })

        for proc in snapshot["ram_processes"]:
            long_form_ram_rows.append({
                "timestamp": ts,
                "pid": proc.get("pid"),
                "ppid": proc.get("ppid"),
                "name": proc.get("name"),
                "ram_score": proc.get("ram_score"),
                "ram_avg": proc.get("ram_avg"),
                "ram_peak": proc.get("ram_peak"),
                "read_bytes_rate": proc.get("read_bytes_rate"),
                "write_bytes_rate": proc.get("write_bytes_rate"),
                "open_fds": proc.get("open_fds"),
                "net_conn_count": proc.get("net_conn_count"),
            })

    # Converting python lists to pandas' DataFrame
    df_long_cpu = pd.DataFrame(long_form_cpu_rows)
    df_long_ram = pd.DataFrame(long_form_ram_rows)

    # In this block: we resample the above DataFrames rows to match the 120 rows final DataFrame

    def resample_process_dataframe(df_long, feature_columns, window_seconds=120):
        if df_long.empty:
            return pd.DataFrame()

        df_long['timestamp_dt'] = pd.to_datetime(df_long['timestamp'], unit='s')
        
        df_pivoted = df_long.pivot(index='timestamp_dt', columns='pid', values=feature_columns)
         
        df_resampled = df_pivoted.resample('1s').ffill()
        
        # Crop/Truncate the timeline to make sure it matches our exact 120-second window length
        df_resampled = df_resampled.tail(window_seconds)
        
        # Fill remaining missing history blocks with 0.0 (Cold Start/Zero-Imputation)
        df_resampled = df_resampled.fillna(0.0)
        
        return df_resampled

    cpu_features = ['cpu_score', 'cpu_avg', 'cpu_peak', 'user_time', 'system_time', 'ctx_vol_rate', 'ctx_invol_rate']
    df_cpu_stretched = resample_process_dataframe(df_long_cpu, cpu_features)

    ram_features = ['ram_score', 'ram_avg', 'ram_peak', 'read_bytes_rate', 'write_bytes_rate', 'open_fds', 'net_conn_count']
    df_ram_stretched = resample_process_dataframe(df_long_ram, ram_features)

    # CALCULATE MATH FEATURES
    # Gradients for ALL CPU features and PIDs simultaneously
    df_cpu_gradients = df_cpu_stretched.diff(periods=1).fillna(0.0)

    # Compute Rolling Averages for ALL CPU columns
    df_cpu_rolling_avg = df_cpu_stretched.rolling(window=30, min_periods=1).mean()

    # Compute Gradients for ALL RAM features and PIDs simultaneously 
    df_ram_gradients = df_ram_stretched.diff(periods=1).fillna(0.0)

    # EXTRACT CPU RANK VECTOR 

    # Get the last row of the raw scores matrix -> for naming and storing them
    current_cpu_scores = df_cpu_stretched['cpu_score'].iloc[-1]
    top_cpu_pids = current_cpu_scores.sort_values(ascending=False).head(5).index.tolist()

    flat_cpu_dict = {}
    for i in range(5):
        rank = i + 1
        if i < len(top_cpu_pids):
            pid = top_cpu_pids[i]
            
            # Extract numerical features for the Isolation Forest
            flat_cpu_dict[f'pid_cpu_{rank}_score'] = df_cpu_stretched[('cpu_score', pid)].iloc[-1]
            flat_cpu_dict[f'pid_cpu_{rank}_avg'] = df_cpu_stretched[('cpu_avg', pid)].iloc[-1]
            flat_cpu_dict[f'pid_cpu_{rank}_peak'] = df_cpu_stretched[('cpu_peak', pid)].iloc[-1]
            flat_cpu_dict[f'pid_cpu_{rank}_user_time'] = df_cpu_stretched[('user_time', pid)].iloc[-1]
            flat_cpu_dict[f'pid_cpu_{rank}_system_time'] = df_cpu_stretched[('system_time', pid)].iloc[-1]
            flat_cpu_dict[f'pid_cpu_{rank}_ctx_vol_rate'] = df_cpu_stretched[('ctx_vol_rate', pid)].iloc[-1]
            flat_cpu_dict[f'pid_cpu_{rank}_ctx_invol_rate'] = df_cpu_stretched[('ctx_invol_rate', pid)].iloc[-1]
            
            # Extract math features 
            flat_cpu_dict[f'pid_cpu_{rank}_gradient'] = df_cpu_gradients[('cpu_peak', pid)].iloc[-1]
            flat_cpu_dict[f'pid_cpu_{rank}_rolling_avg'] = df_cpu_rolling_avg[('cpu_avg', pid)].iloc[-1]
            
            # Inject metadata to final vector
            static_info = df_long_cpu[df_long_cpu['pid'] == pid].iloc[-1]
            flat_cpu_dict[f'pid_cpu_{rank}_id'] = int(pid)
            flat_cpu_dict[f'pid_cpu_{rank}_name'] = static_info['name']
            flat_cpu_dict[f'pid_cpu_{rank}_ppid'] = int(static_info['ppid'])
        else:
            # Padding loop if the system has fewer than 5 active processes
            flat_cpu_dict[f'pid_cpu_{rank}_score'] = 0.0
            flat_cpu_dict[f'pid_cpu_{rank}_avg'] = 0.0
            flat_cpu_dict[f'pid_cpu_{rank}_peak'] = 0.0
            flat_cpu_dict[f'pid_cpu_{rank}_user_time'] = 0.0
            flat_cpu_dict[f'pid_cpu_{rank}_system_time'] = 0.0
            flat_cpu_dict[f'pid_cpu_{rank}_ctx_vol_rate'] = 0.0
            flat_cpu_dict[f'pid_cpu_{rank}_ctx_invol_rate'] = 0.0
            flat_cpu_dict[f'pid_cpu_{rank}_gradient'] = 0.0
            flat_cpu_dict[f'pid_cpu_{rank}_rolling_avg'] = 0.0
            flat_cpu_dict[f'pid_cpu_{rank}_id'] = 0
            flat_cpu_dict[f'pid_cpu_{rank}_name'] = "None"
            flat_cpu_dict[f'pid_cpu_{rank}_ppid'] = 0

    # Convert to a single-row 2D DataFrame [1, num_cpu_features]
    cpu_vec = pd.DataFrame([flat_cpu_dict])


    # EXTRACT RAM RANK VECTOR 
    current_ram_scores = df_ram_stretched['ram_score'].iloc[-1]
    top_ram_pids = current_ram_scores.sort_values(ascending=False).head(5).index.tolist()

    flat_ram_dict = {}
    for i in range(5):
        rank = i + 1
        if i < len(top_ram_pids):
            pid = top_ram_pids[i]
            
            flat_ram_dict[f'pid_ram_{rank}_score'] = df_ram_stretched[('ram_score', pid)].iloc[-1]
            flat_ram_dict[f'pid_ram_{rank}_avg'] = df_ram_stretched[('ram_avg', pid)].iloc[-1]
            flat_ram_dict[f'pid_ram_{rank}_peak'] = df_ram_stretched[('ram_peak', pid)].iloc[-1]
            flat_ram_dict[f'pid_ram_{rank}_read_bytes_rate'] = df_ram_stretched[('read_bytes_rate', pid)].iloc[-1]
            flat_ram_dict[f'pid_ram_{rank}_write_bytes_rate'] = df_ram_stretched[('write_bytes_rate', pid)].iloc[-1]
            flat_ram_dict[f'pid_ram_{rank}_open_fds'] = df_ram_stretched[('open_fds', pid)].iloc[-1]
            flat_ram_dict[f'pid_ram_{rank}_net_conn_count'] = df_ram_stretched[('net_conn_count', pid)].iloc[-1]
            
            # Extract RAM math features 
            flat_ram_dict[f'pid_ram_{rank}_gradient'] = df_ram_gradients[('ram_avg', pid)].iloc[-1]
            
            # Inject metadata to final vector
            static_info = df_long_ram[df_long_ram['pid'] == pid].iloc[-1]
            flat_ram_dict[f'pid_ram_{rank}_id'] = int(pid)
            flat_ram_dict[f'pid_ram_{rank}_name'] = static_info['name']
            flat_ram_dict[f'pid_ram_{rank}_ppid'] = int(static_info['ppid'])
        else:
            flat_ram_dict[f'pid_ram_{rank}_score'] = 0.0
            flat_ram_dict[f'pid_ram_{rank}_avg'] = 0.0
            flat_ram_dict[f'pid_ram_{rank}_peak'] = 0.0
            flat_ram_dict[f'pid_ram_{rank}_read_bytes_rate'] = 0.0
            flat_ram_dict[f'pid_ram_{rank}_write_bytes_rate'] = 0.0
            flat_ram_dict[f'pid_ram_{rank}_open_fds'] = 0.0
            flat_ram_dict[f'pid_ram_{rank}_net_conn_count'] = 0.0
            flat_ram_dict[f'pid_ram_{rank}_gradient'] = 0.0
            flat_ram_dict[f'pid_ram_{rank}_id'] = 0
            flat_ram_dict[f'pid_ram_{rank}_name'] = "None"
            flat_ram_dict[f'pid_ram_{rank}_ppid'] = 0

    # Convert to a single-row 2D DataFrame [1, num_ram_features]
    ram_vec = pd.DataFrame([flat_ram_dict])

    # Return single row vectors for cpu and ram
    return cpu_vec, ram_vec

#   Concatenates system and process feature spaces into a fixed-dimensional matrix.
#   Separates isolation_forest ready numerical rows from human-readable metadata.
    
def build_unified_vector(sys_vec, cpu_vec, ram_vec):

    df_unified = pd.concat([sys_vec, cpu_vec, ram_vec], axis=1)
    
    metadata_cols = [col for col in df_unified.columns 
                     if col.endswith('_name') or col.endswith('_id') or col.endswith('_ppid')]
    
    metadata_payload = df_unified[metadata_cols].iloc[0].to_dict()
    
    ml_features_df = df_unified.drop(columns=metadata_cols)
    
    ml_features_df = ml_features_df.reindex(sorted(ml_features_df.columns), axis=1)
    
    return ml_features_df, metadata_payload

def get_inference_payload(db_path):
    """
    Centralized orchestration function called by the main daemon loop.
    Enforces data safety buffers and executes functions 1, 2, and 3 sequentially.
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
            # System is still warming up; return None to skip this execution tick safely
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
        cpu_vec, ram_vec = extract_and_engineer_processes(db_path)
        
        # 3. Check for empty payloads before stitching to prevent concat failures
        if sys_vec.empty or cpu_vec.empty or ram_vec.empty:
            print("Warning: One of the sub-vectors returned an empty frame. Skipping inference.")
            return None, None
            
        # 4. Consolidate and strip metadata 
        ml_features_df, metadata_payload = build_unified_vector(sys_vec, cpu_vec, ram_vec)
        
        # Return the clean tuple directly down to the ML execution loop!
        return ml_features_df, metadata_payload

    except Exception as e:
        print(f"Critical error during feature engineering pipeline orchestration: {e}")
        return None, None