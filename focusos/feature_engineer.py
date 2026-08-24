import pandas as pd
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

# Import the stateless database window function
from focusos.sliding_window import get_window_from_db

# Full 22-Feature Schema matching IdeaPad training dataset
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


def extract_features(df: pd.DataFrame):
    """
    Extracts the 22-feature statistical vector from a sliding window telemetry DataFrame.
    Matches the schema of focusos_training_data_ideapad.csv.
    """
    try:
        if df is None or df.empty:
            return None

        cpu_cores = os.cpu_count() or 4

        # Calculate time delta across the sliding window
        if "timestamp" in df.columns and len(df) > 1:
            try:
                t_series = pd.to_datetime(df["timestamp"])
                dt = max(1.0, float((t_series.iloc[-1] - t_series.iloc[0]).total_seconds()))
            except Exception:
                dt = float(len(df))
        else:
            dt = float(len(df)) if len(df) > 0 else 1.0

        # 1-3. CPU basic statistics
        cpu_mean = float(df["cpu_usage_percent"].mean()) if "cpu_usage_percent" in df.columns else 0.0
        cpu_max = float(df["cpu_usage_percent"].max()) if "cpu_usage_percent" in df.columns else 0.0
        cpu_variance = float(df["cpu_usage_percent"].var(ddof=0)) if ("cpu_usage_percent" in df.columns and len(df) > 1) else 0.0

        # 4-5. RAM statistics
        ram_mean = float(df["memory_percent"].mean()) if "memory_percent" in df.columns else 0.0
        ram_growth_rate = (
            float(df["memory_percent"].iloc[-1] - df["memory_percent"].iloc[0])
            if ("memory_percent" in df.columns and len(df) > 0)
            else 0.0
        )

        # 6. Swap usage percent
        swap_percent = float(df["swap_percent"].mean()) if "swap_percent" in df.columns else 0.0

        # 7-9. Network statistics (rate per second in MB/s over window)
        sent_delta = float(max(0, df["net_bytes_sent"].iloc[-1] - df["net_bytes_sent"].iloc[0])) if "net_bytes_sent" in df.columns and len(df) > 1 else 0.0
        recv_delta = float(max(0, df["net_bytes_recv"].iloc[-1] - df["net_bytes_recv"].iloc[0])) if "net_bytes_recv" in df.columns and len(df) > 1 else 0.0
        sent_rate_mb = sent_delta / (1024 * 1024 * dt)
        recv_rate_mb = recv_delta / (1024 * 1024 * dt)
        net_mean = sent_rate_mb + recv_rate_mb

        if "net_rate_mb_s" in df.columns and not df["net_rate_mb_s"].isna().all():
            net_var = float(df["net_rate_mb_s"].var(ddof=0)) if len(df) > 1 else 0.05
        else:
            net_var = 0.05

        # Network symmetry is high (~0.7) ONLY during active bidirectional streams like video calls
        # When traffic is idle/bursty download, it is highly asymmetric (~0.03)
        if net_mean > 0.02 and (sent_rate_mb > 0.005 and recv_rate_mb > 0.005):
            net_symmetry = float(min(sent_rate_mb, recv_rate_mb) / (max(sent_rate_mb, recv_rate_mb) + 1e-5))
        else:
            net_symmetry = 0.03

        # 11. Disk I/O activity mean
        if "disk_write_mb_s" in df.columns and "disk_read_mb_s" in df.columns:
            disk_io_mean = float((df["disk_write_mb_s"] + df["disk_read_mb_s"]).mean())
        else:
            disk_io_mean = 0.0

        # 12-13. Process & Thread counts
        process_count_mean = float(df["total_processes"].mean()) if "total_processes" in df.columns else 400.0
        thread_count_mean = float(process_count_mean * 2.5 / cpu_cores)

        # 14. Load average per core
        if "load_avg_1" in df.columns and not df["load_avg_1"].isna().all():
            load_avg = float(df["load_avg_1"].mean() / cpu_cores)
        elif "load_avg1" in df.columns and not df["load_avg1"].isna().all():
            load_avg = float(df["load_avg1"].mean() / cpu_cores)
        else:
            load_avg = float(cpu_mean / 100.0)

        # 15. Context switches rate per second per core
        if "cpu_ctx_switches" in df.columns and len(df) > 1:
            ctx_delta = float(max(0, df["cpu_ctx_switches"].iloc[-1] - df["cpu_ctx_switches"].iloc[0]))
            ctx_switches = float(ctx_delta / (dt * cpu_cores))
        else:
            ctx_switches = 65.0

        # 16. CPU user to system time ratio
        if "cpu_user_time" in df.columns and "cpu_system_time" in df.columns and len(df) > 1:
            u_delta = float(max(0, df["cpu_user_time"].iloc[-1] - df["cpu_user_time"].iloc[0]))
            s_delta = float(max(0, df["cpu_system_time"].iloc[-1] - df["cpu_system_time"].iloc[0]))
            cpu_user_system_ratio = float(u_delta / (s_delta + 1e-5)) if (u_delta > 0 or s_delta > 0) else 10.0
        else:
            cpu_user_system_ratio = 10.0

        # 17-19. Linux Pressure Stall Information (PSI)
        psi_cpu_some = float(df["psi_metrics_cpu"].mean()) if ("psi_metrics_cpu" in df.columns and not df["psi_metrics_cpu"].isna().all()) else 0.0
        psi_mem_some = float(df["psi_metrics_mem"].mean()) if ("psi_metrics_mem" in df.columns and not df["psi_metrics_mem"].isna().all()) else 0.0
        psi_io_some = float(df["psi_metrics_io"].mean()) if ("psi_metrics_io" in df.columns and not df["psi_metrics_io"].isna().all()) else 0.0

        # 20-22. Process detection binary indicators
        process_col = df["process_data"].fillna("").astype(str).str.lower() if "process_data" in df.columns else pd.Series([""])

        vscode_active = int(
            process_col.str.contains(
                "code|code-insiders|vsls-agent|antigravity|sublime|pycharm",
                regex=True,
            ).any()
        )

        # HARDCODED — always 0.
        # Chrome/Chromium processes in telemetry are exclusively the Streamlit
        # dashboard browser, not real user browser activity.  Including them in
        # the feature vector inflates the confidence score and corrupts workload
        # classification.  The exclusion is already applied upstream in
        # layer1_system.py, but we enforce it here as a second safety net.
        browser_active = 0

        def detect_compiler_active(data_df):
            compiler_names = {
                "gcc", "cc1", "cc1plus", "g++", "clang", "clang++",
                "rustc", "javac", "make", "ninja", "cargo", "ld",
                "as", "collect2", "cmake"
            }
            # HARDCODED — processes that belong to CogniOS infrastructure.
            # Python here is the daemon interpreter; Streamlit is the dashboard.
            # Neither represents a real user compiler workload.
            _infra_exclude = (
                "python", "python3", "cognios", "streamlit",
                "cognios_as_daemon",
            )
            if "process_data" not in data_df.columns:
                return 0

            for _, row in data_df.iterrows():
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
                        # Skip CogniOS infrastructure processes
                        if any(ex in name for ex in _infra_exclude):
                            continue
                        if any(comp in name for comp in compiler_names):
                            return 1
                        if "code" in name and cpu > 50:
                            return 1
                except (json.JSONDecodeError, ValueError, IndexError, TypeError):
                    continue
            return 0

        compiler_active = detect_compiler_active(df)

        # 10. UDP to TCP socket ratio (collected directly from layer1_system)
        if "udp_tcp_ratio" in df.columns and not df["udp_tcp_ratio"].isna().all():
            udp_tcp = float(df["udp_tcp_ratio"].mean())
        else:
            udp_tcp = 0.10  # Safe idle baseline if DB column is completely missing

        # Build feature dictionary matching FEATURE_COLUMNS exact order
        features = {
            "cpu_mean": cpu_mean,
            "cpu_max": cpu_max,
            "cpu_variance": cpu_variance,
            "ram_mean": ram_mean,
            "ram_growth_rate": ram_growth_rate,
            "swap_percent": swap_percent,
            "network_mean": net_mean,
            "network_symmetry": net_symmetry,
            "net_variance": net_var,
            "udp_tcp_ratio": udp_tcp,
            "disk_io_mean": disk_io_mean,
            "process_count_mean": process_count_mean,
            "thread_count_mean": thread_count_mean,
            "load_avg": load_avg,
            "ctx_switches_per_core": ctx_switches,
            "cpu_user_system_ratio": cpu_user_system_ratio,
            "psi_cpu_some": psi_cpu_some,
            "psi_mem_some": psi_mem_some,
            "psi_io_some": psi_io_some,
            "vscode_active": vscode_active,
            "browser_active": browser_active,
            "compiler_active": compiler_active,
        }

        features_df = pd.DataFrame([features], columns=FEATURE_COLUMNS)
        return features_df

    except Exception as e:
        print(f"Feature Extraction Error: {e}")
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
      
      
      
        







        