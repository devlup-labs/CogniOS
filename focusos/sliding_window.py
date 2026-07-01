import pandas as pd
import sqlite3
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

#sliding window fetcing all the 120 rows
def extract_features(db_path=DB_PATH):
    try:
        with sqlite3.connect(db_path) as conn:
            # Assuming 'table_name' will be replaced with actual table name later
            query_all_columns = 'select * from layer1_sys order by timestamp desc limit 120'
            df = pd.read_sql_query(query_all_columns, conn)
            
        if df.empty:
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
        
        # process lists -> flags if found-> 1 else 0
        # 'process_name' is not stored in layer1_sys (only process_data as JSON or similar if stored, but here not available)
        vscode_active = 0
        browser_active = 0
        compiler_active = 0
        
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
    extract_features()