import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

# Import the stateless database window function
from focusos.sliding_window import get_window_from_db

# sliding window fetching all the 120 rows via the sliding_window module
def extract_features(df: pd.DataFrame):
    try:
        if df is None or df.empty:
            return None
            
        # reversing the index so that 0 is oldest and -1 is newest
        #df = df.iloc[::-1].reset_index(drop=True)
        #already reversed in the sliding window
        # cpu 
        cpu_mean = df["cpu_usage_percent"].mean()
        cpu_max = df["cpu_usage_percent"].max()
        cpu_variance = df["cpu_usage_percent"].var()
        
        # Time-scaling factor to normalize rate features relative to baseline 120 window
        scale_factor = (120.0 / len(df)) if len(df) > 0 else 1.0

        # mem feature engineering 
        ram_mean = df["memory_percent"].mean()
        ram_growth_rate = ((df["memory_percent"].iloc[-1] - df["memory_percent"].iloc[0]) * scale_factor) if len(df) > 0 else 0
        
        # network: calculate true average throughput rate (MB/s) across the window
        if "net_rate_mb_s" in df.columns and df["net_rate_mb_s"].notnull().any():
            net_mean = float(df["net_rate_mb_s"].mean())
        else:
            # Fallback: MB/s rate computed from total byte delta over window length
            net_combined = df["net_bytes_sent"] + df["net_bytes_recv"]
            total_bytes = max(0, net_combined.iloc[-1] - net_combined.iloc[0])
            net_mean = float((total_bytes / (1024 * 1024)) / len(df)) if len(df) > 0 else 0.0

        #here i am calculating the coeffiecient of var = std/mean
        # 10x spike on ssd == 10x spike on hdd
        disk_combined = df["disk_write_mb_s"] + df["disk_read_mb_s"]
        disk_mean_raw = disk_combined.mean()
        if disk_mean_raw > 0:
            disk_io_mean = float(disk_combined.std() / disk_mean_raw)
        else:
            disk_io_mean = 0.0
        # processes
        process_count_mean = int(df["total_processes"].mean())
        #calculating the normalised value: threads per core
        cpu_cores = os.cpu_count() or 4
        if "num_threads" in df.columns:
            import json
            def safe_sum_threads(val):
                if isinstance(val, str) and val.strip():
                    try:
                        lst = json.loads(val)
                        if isinstance(lst, list):
                            return sum(lst)
                    except Exception:
                        pass
                return 0
            thread_count_mean = df["num_threads"].apply(safe_sum_threads).mean() / cpu_cores
        else:
            thread_count_mean = (df["total_processes"].mean() * 2.5) / cpu_cores


        # We use fillna('') so .str doesn't crash on missing process names
        process_col = df["process_data"].fillna("").str.lower()
        
        vscode_active = int(process_col.str.contains("code|code-insiders|vsls-agent|antigravity|sublime", regex=True).any())
        browser_active = int(process_col.str.contains("chrome|firefox|brave|msedge", regex=True).any())
        compiler_active = int(process_col.str.contains("gcc|g\\+\\+|clang|rustc|javac|make", regex=True).any())
        
        features = {
            "cpu_mean": cpu_mean,
            "cpu_max": cpu_max,
            "cpu_variance": cpu_variance,
            "ram_mean": ram_mean,
            "ram_growth_rate": ram_growth_rate,
            "network_mean": net_mean,
            "disk_io_mean": disk_io_mean,
            "process_count_mean": process_count_mean,
            "thread_count_mean": thread_count_mean,
            "vscode_active": vscode_active,
            "browser_active": browser_active,
            "compiler_active": compiler_active,
        }
        features_df = pd.DataFrame([features])
        return features_df
        
    except Exception as e:
        print(f"Window Extraction Error: {e}")
        return None

if __name__ == "__main__":
    print("Fetching window from database...")
    df = get_window_from_db()
    if df is not None:
        extract_features(df)
    else:
        print("Not enough data or database empty.")