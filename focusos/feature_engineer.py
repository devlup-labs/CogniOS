import pandas as pd
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

# Import the stateless database window function
from focusos.sliding_window import get_window_from_db

# sliding window fetching all the SLIDING_WIND_N rows via the sliding_window module
def extract_features(df: pd.DataFrame):
    try:
        if df is None or df.empty:
            return None
            
       # CPU features 
        cpu_mean = df["cpu_usage_percent"].mean()
        cpu_max = df["cpu_usage_percent"].max()
        cpu_variance = df["cpu_usage_percent"].var()

       # Memory features
        ram_mean = df["memory_percent"].mean()
        ram_growth_rate = (
                  df["memory_percent"].iloc[-1] - df["memory_percent"].iloc[0]
                  if len(df) > 0
                  else 0
              )
      
              # Network features
        net_combined = df["net_bytes_sent"] + df["net_bytes_recv"]
        # Bytes transferred during the window
        bytes_transferred = float(net_combined.iloc[-1] - net_combined.iloc[0]) if len(df) > 0 else 0.0
        # Convert to MB/s (assuming 1-second sample intervals)
        net_mean = (bytes_transferred / len(df)) / (1024 * 1024)
      
              # Disk I/O coefficient of variation
        disk_combined = df["disk_write_mb_s"] + df["disk_read_mb_s"]
        disk_mean_raw = disk_combined.mean()
      
        if disk_mean_raw > 0:
                  disk_io_mean = float(disk_combined.std() / disk_mean_raw)
        else:
                  disk_io_mean = 0.0
      
              # Process statistics
        process_count_mean = int(df["total_processes"].mean())
      
        cpu_cores = os.cpu_count() or 4
      
        if "num_threads" in df.columns:
      
                  def safe_sum_threads(val):
                      if isinstance(val, str) and val.strip():
                          try:
                              lst = json.loads(val)
                              if isinstance(lst, list):
                                  return sum(lst)
                          except Exception:
                              pass
                      return 0
      
                  thread_count_mean = (
                      df["num_threads"].apply(safe_sum_threads).mean()
                      # NOTE: NOT divided by cpu_cores — training data uses absolute
                      # total thread count (65–160 range). Hardware-tier variation
                      # in generate_dataset.py already handles hardware-agnosticism.
                  )
        else:
                  thread_count_mean = (
                      df["total_processes"].mean() * 2.5
                      # NOT divided by cpu_cores — matches training data scale
                  )
      
              # Process detection
        process_col = df["process_data"].fillna("").str.lower()
      
        vscode_active = int(
            process_col.str.contains(
                "code|code-insiders|vsls-agent|antigravity|sublime",
                regex=True,
            ).any()
        )

        if len(df) > 1 and "net_bytes_sent" in df.columns and "net_bytes_recv" in df.columns:
            sent_delta = df["net_bytes_sent"].iloc[-1] - df["net_bytes_sent"].iloc[0]
            recv_delta = df["net_bytes_recv"].iloc[-1] - df["net_bytes_recv"].iloc[0]
            network_symmetry = sent_delta / (sent_delta + recv_delta + 1e-6)
        else:
            network_symmetry = df["network_symmetry"].mean()
        if len(df) > 1 and "cpu_ctx_switches" in df.columns:
            ctx_switch_per_core = (df["cpu_ctx_switches"].iloc[-1] - df["cpu_ctx_switches"].iloc[0]) / float(len(df)) / cpu_cores
        else:
            ctx_switch_per_core = 0.0
        psi_cpu_some = df["psi_metrics_cpu"].mean()
        psi_mem_some = df["psi_metrics_mem"].mean()
        psi_io_some = df["psi_metrics_io"].mean()
        swap_percent = df["swap_percent"].mean()
        net_variance = df["net_rate_mb_s"].var()
        udp_tcp_ratio = df["udp_tcp_ratio"].mean()
        load_avg = df["load_avg_1"].mean()
        if len(df) > 1:
            user_delta = df["cpu_user_time"].iloc[-1] - df["cpu_user_time"].iloc[0]
            system_delta = df["cpu_system_time"].iloc[-1] - df["cpu_system_time"].iloc[0]
            cpu_user_system_ratio = user_delta / (system_delta + 1e-6)
        else:
            cpu_user_system_ratio = 0.0
      
        browser_active = int(
                  process_col.str.contains(
                      "chrome|firefox|brave|msedge",
                      regex=True,
                  ).any()
              )
      
            #changes this compiler active detection for testing compilation
      
        def detect_compiler_active(df):
                  """
                  Detects compilation in two ways:
      
                  1. Direct compiler process names.
                  2. VSCode consuming high CPU while compiling.
                  """
      
                  compiler_names = {
                      "gcc",
                      "cc1",
                      "cc1plus",
                      "g++",
                      "clang",
                      "clang++",
                      "rustc",
                      "javac",
                      "make",
                      "ninja",
                      "cargo",
                      "ld",
                      "as",
                      "collect2",
                      "cmake",
                  }
      
                  for _, row in df.iterrows():
      
                      try:
                          raw = row.get("process_data", "")
      
                          if not raw or not isinstance(raw, str):
                              continue
      
                          processes = json.loads(raw)
      
                          for proc in processes:
      
                              if not proc or len(proc) < 2:
                                  continue
      
                              name = str(proc[0]).lower()
                              cpu = float(proc[1]) if len(proc) > 1 else 0
      
                              # Way 1: compiler process detected
                              if any(comp in name for comp in compiler_names):
                                  return 1
      
                              # Way 2: VSCode using high CPU
                              if "code" in name and cpu > 50:
                                  return 1
      
                      except (json.JSONDecodeError, ValueError, IndexError, TypeError):
                          continue
      
                  return 0
      
        compiler_active = detect_compiler_active(df)
      
              # Feature vector
        features = {
                  "cpu_mean": cpu_mean,
                  "cpu_max": cpu_max,
                  "cpu_variance": cpu_variance,
                  "ram_mean": ram_mean,
                  "ram_growth_rate": ram_growth_rate,
                  "swap_percent": swap_percent,
                  "network_mean": net_mean,
                  "network_symmetry": network_symmetry,
                  "net_variance": net_variance,                  
                  "udp_tcp_ratio": udp_tcp_ratio,
                  "disk_io_mean": disk_io_mean,
                  "process_count_mean": process_count_mean,
                  "thread_count_mean": thread_count_mean,
                  "load_avg": load_avg,                  
                  "ctx_switches_per_core": ctx_switch_per_core,
                  "cpu_user_system_ratio": cpu_user_system_ratio,
                  "psi_cpu_some": psi_cpu_some,
                  "psi_mem_some": psi_mem_some,
                  "psi_io_some": psi_io_some,
                  "vscode_active": vscode_active,
                  "browser_active": browser_active,
                  "compiler_active": compiler_active
              }
      
        features_df = pd.DataFrame([features])
        features_df = features_df.fillna(0.0)
      
        return features_df
      
    except Exception as e:
              print(f"Window Extraction Error: {e}")
              return None
      
      
if __name__ == "__main__":
    print("Fetching window from database...")
      
    df = get_window_from_db()
      
    if df is not None:
              features = extract_features(df)
      
              if features is not None:
                  print(features)
    else:
        print("Not enough data or database empty.")
      
      
      
        







        