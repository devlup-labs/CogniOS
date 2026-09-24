#!/usr/bin/env python3
"""
FocusOS Interactive Synthetic Workload Simulator & Model Evaluator
Allows simulating custom metric scenarios via presets, CLI arguments, or interactive prompts.
"""

import os
import sys
import argparse
import psutil
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from focusos.models.classifier import WorkloadPredictor, FEATURE_COLUMNS

def get_laptop_profile():
    return {
        "cores_logical": psutil.cpu_count(logical=True) or 16,
        "cores_physical": psutil.cpu_count(logical=False) or 8,
        "ram_gb": round(psutil.virtual_memory().total / (1024**3), 2)
    }

def simulate_synthetic_sample(
    workload_type="Coding",
    cpu_load_pct=25.0,
    ram_usage_pct=30.0,
    network_mb_s=0.01,
    net_symmetry=0.02,
    net_variance=None,
    udp_tcp_ratio=0.85,
    vscode_active=None,
    browser_active=None,
    compiler_active=None,
    video_call_active=None
):
    hw = get_laptop_profile()
    cores = hw["cores_logical"]

    wl = workload_type.lower()
    if "video" in wl:
        c_var = 10.0
        n_var = 0.09 if net_variance is None else float(net_variance)
        ram_growth = 0.20
        c_max = float(min(100.0, cpu_load_pct * 1.8 + 2.0))
        ctx_sw = 290.0
        u_s_ratio = 2.1
        load_a = cpu_load_pct / 35.0
        disk_io = 0.8
        vs = 0 if vscode_active is None else int(vscode_active)
        br = 1 if browser_active is None else int(browser_active)
        comp = 0 if compiler_active is None else int(compiler_active)
        vid = 1 if video_call_active is None else int(video_call_active)
    elif "browse" in wl or "browsing" in wl:
        c_var = 24.0
        n_var = 3.8 if net_variance is None else float(net_variance)
        ram_growth = 1.23
        c_max = float(min(100.0, cpu_load_pct * 2.5 + 4.0))
        ctx_sw = 180.0
        u_s_ratio = 4.2
        load_a = cpu_load_pct / 40.0
        disk_io = 1.6
        vs = 0 if vscode_active is None else int(vscode_active)
        br = 1 if browser_active is None else int(browser_active)
        comp = 0 if compiler_active is None else int(compiler_active)
        vid = 0 if video_call_active is None else int(video_call_active)
    elif "idle" in wl:
        c_var = 1.0
        n_var = 0.05 if net_variance is None else float(net_variance)
        ram_growth = 0.0
        c_max = float(min(100.0, cpu_load_pct * 2.2 + 0.5))
        ctx_sw = 25.0
        u_s_ratio = 2.5
        load_a = 0.02
        disk_io = 0.3
        vs = 0 if vscode_active is None else int(vscode_active)
        br = 0 if browser_active is None else int(browser_active)
        comp = 0 if compiler_active is None else int(compiler_active)
        vid = 0 if video_call_active is None else int(video_call_active)
    else:  # Coding / Compiling
        c_var = 18.0
        n_var = 1.20 if net_variance is None else float(net_variance)
        ram_growth = 1.78
        c_max = float(min(100.0, cpu_load_pct * 1.5 + 5.0))
        ctx_sw = 545.0
        u_s_ratio = 7.5
        load_a = cpu_load_pct / 20.0
        disk_io = 4.8
        vs = 1 if vscode_active is None else int(vscode_active)
        comp = (1 if cpu_load_pct > 25.0 else 0) if compiler_active is None else int(compiler_active)
        br = 1 if browser_active is None else int(browser_active)
        vid = 0 if video_call_active is None else int(video_call_active)

    sample = {
        "cpu_mean": float(cpu_load_pct),
        "cpu_max": c_max,
        "cpu_variance": c_var,
        "ram_mean": float(ram_usage_pct),
        "ram_growth_rate": ram_growth,
        "swap_percent": 0.5 if "coding" in wl else 0.0,
        "network_mean": float(network_mb_s),
        "network_symmetry": float(net_symmetry),
        "net_variance": n_var,
        "udp_tcp_ratio": float(udp_tcp_ratio),
        "disk_io_mean": disk_io,
        "process_count_mean": 425.0,
        "thread_count_mean": float(420.0 * 2.5 / cores),
        "load_avg": float(load_a),
        "ctx_switches_per_core": ctx_sw,
        "cpu_user_system_ratio": u_s_ratio,
        "psi_cpu_some": 4.5 if ("coding" in wl and cpu_load_pct > 35) else 0.0,
        "psi_mem_some": 0.0,
        "psi_io_some": 3.5 if "coding" in wl else 0.0,
        "vscode_active": vs,
        "browser_active": br,
        "compiler_active": comp
    }
    
    if "video_call_active" in FEATURE_COLUMNS:
        sample["video_call_active"] = vid

    ordered_sample = {col: sample.get(col, 0.0) for col in FEATURE_COLUMNS}
    return pd.DataFrame([ordered_sample])

def test_preset(predictor, name, **kwargs):
    df_sample = simulate_synthetic_sample(**kwargs)
    result = predictor.predict(df_sample)
    print(f"\n[+] Scenario: {name}")
    print(f"    Inputs  : CPU={kwargs.get('cpu_load_pct', 0)}%, RAM={kwargs.get('ram_usage_pct', 0)}%, VSCode={kwargs.get('vscode_active', 0)}, Browser={kwargs.get('browser_active', 0)}, Compiler={kwargs.get('compiler_active', 0)}, Video={kwargs.get('video_call_active', 0)}")
    print(f"    Output  : Predicted -> \033[1;32m{result['workload'].upper()}\033[0m (Confidence: {result['confidence']}%)")
    print("    Class Probabilities:")
    for cls_name, prob in result['probabilities'].items():
        bar = "█" * int(prob / 5)
        print(f"      - {cls_name:<12}: {prob:>6.2f}% | {bar}")
    return result

def run_all_presets(predictor):
    print("\n--- RUNNING STANDARD BENCHMARK PRESETS ---")
    test_preset(predictor, "1. Clean Coding (VS Code active, typing)", 
                workload_type="Coding", cpu_load_pct=18.0, ram_usage_pct=26.0, vscode_active=1)

    test_preset(predictor, "2. Heavy Code Compilation (GCC/Clang build)", 
                workload_type="Coding", cpu_load_pct=85.0, ram_usage_pct=45.0, vscode_active=1, compiler_active=1)

    test_preset(predictor, "3. Video Meeting (Zoom/Teams active, high UDP)", 
                workload_type="Video Call", cpu_load_pct=32.0, ram_usage_pct=35.0, 
                network_mb_s=0.25, net_symmetry=0.82, udp_tcp_ratio=1.8, video_call_active=1)

    test_preset(predictor, "4. Web Browsing (Chrome/Firefox multiple tabs)", 
                workload_type="Browsing", cpu_load_pct=14.0, ram_usage_pct=38.0, 
                network_mb_s=0.15, net_symmetry=0.03, net_variance=0.8, udp_tcp_ratio=0.35, browser_active=1)

    test_preset(predictor, "5. System Idle (Background services only)", 
                workload_type="Idle", cpu_load_pct=2.5, ram_usage_pct=15.0, 
                network_mb_s=0.002, vscode_active=0, browser_active=0)

def main():
    hw = get_laptop_profile()
    parser = argparse.ArgumentParser(description="FocusOS Synthetic Workload Simulator")
    parser.add_argument("--cpu", type=float, default=None, help="Synthetic CPU load percentage (0-100)")
    parser.add_argument("--ram", type=float, default=None, help="Synthetic RAM usage percentage (0-100)")
    parser.add_argument("--vscode", type=int, choices=[0, 1], default=0, help="VSCode active flag (0 or 1)")
    parser.add_argument("--browser", type=int, choices=[0, 1], default=0, help="Browser active flag (0 or 1)")
    parser.add_argument("--compiler", type=int, choices=[0, 1], default=0, help="Compiler active flag (0 or 1)")
    parser.add_argument("--video", type=int, choices=[0, 1], default=0, help="Video call active flag (0 or 1)")
    parser.add_argument("--net-mb", type=float, default=0.05, help="Network transfer rate in MB/s")
    parser.add_argument("--net-symmetry", type=float, default=0.03, help="Network symmetry ratio (0.0 - 1.0)")
    parser.add_argument("--udp-ratio", type=float, default=0.5, help="UDP to TCP socket ratio")

    args = parser.parse_args()

    print("=" * 65)
    print(f"  FOCUSOS SYNTHETIC HARDWARE SIMULATOR & TESTER")
    print(f"  Detected Hardware: {hw['cores_logical']} Cores | {hw['ram_gb']} GB RAM")
    print("=" * 65)

    try:
        predictor = WorkloadPredictor()
    except Exception as e:
        print(f"[!] Error loading model: {e}")
        sys.exit(1)

    if args.cpu is not None or args.ram is not None:
        cpu = args.cpu if args.cpu is not None else 10.0
        ram = args.ram if args.ram is not None else 25.0
        test_preset(
            predictor, 
            "Custom User Simulation",
            cpu_load_pct=cpu,
            ram_usage_pct=ram,
            network_mb_s=args.net_mb,
            net_symmetry=args.net_symmetry,
            udp_tcp_ratio=args.udp_ratio,
            vscode_active=args.vscode,
            browser_active=args.browser,
            compiler_active=args.compiler,
            video_call_active=args.video
        )
    else:
        run_all_presets(predictor)

    print("\n" + "=" * 65)
    print("Tip: Run with custom values, e.g.:")
    print("  python3 simulate_laptop_workload.py --cpu 75 --ram 50 --vscode 1 --compiler 1")
    print("=" * 65)

if __name__ == "__main__":
    main()
