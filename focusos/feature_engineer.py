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
        df = df.iloc[::-1].reset_index(drop=True)
        
        # cpu 
        cpu_mean = df["cpu_usage_percent"].mean()
        cpu_max = df["cpu_usage_percent"].max()
        cpu_variance = df["cpu_usage_percent"].var()
        
        # mem feature engineering 
        ram_mean = df["memory_percent"].mean()
        ram_growth_rate = (df["memory_percent"].iloc[-1] - df["memory_percent"].iloc[0]) if len(df) > 0 else 0
        
        # network
        net_mean = (df["net_bytes_sent"] + df["net_bytes_recv"]).mean()
        disk_io_mean = (df["disk_write_mb_s"] + df["disk_read_mb_s"]).mean()
        
        # processes
        process_count_mean = df["total_processes"].mean()
        # 'thread_count' is not in layer1_sys
        thread_count_mean = 0
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
        print(features_df)
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