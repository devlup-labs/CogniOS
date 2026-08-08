#!/usr/bin/env python3
"""
generate_dataset_v5.py — FocusOS Hardware-Agnostic Dataset Synthesizer
========================================================================
Fixes Shortcut Learning by introducing overlapping continuous noise across
3 hardware tiers (Powerful, Mid-range, Budget). Forces XGBoost to prioritize
contextual binary flags (compiler_active, vscode_active, browser_active)
and dimensionless network ratios over raw hardware-dependent spikes.
"""

import csv
import random
import os

SEED = 42
random.seed(SEED)

ROWS_PER_CLASS = 600  # 100 rows per tier x 2 tiers/sub-states
OUTPUT_FILE = "focusos_training_data_v5.csv"

FEATURE_COLUMNS = [
    "cpu_mean",
    "cpu_max",
    "cpu_variance",
    "ram_mean",
    "ram_growth_rate",
    "swap_percent",
    "network_mean",
    "net_symmetry_ratio",
    "net_variance",
    "udp_tcp_socket_ratio",
    "disk_io_mean",
    "process_count_mean",
    "thread_count_mean",
    "load_1m_per_core",
    "ctx_switches_per_core",
    "cpu_user_system_ratio",
    "psi_cpu_some",
    "psi_mem_some",
    "psi_io_some",
    "vscode_active",
    "browser_active",
    "compiler_active",
]

LABEL_COLUMN = "workload_label"


def clamp_pct(v):   return max(0.0, min(100.0, v))
def clamp_nn(v):    return max(0.0, v)
def s(mu, sigma):   return random.gauss(mu, sigma)
def b(p):           return 1 if random.random() < p else 0

# NOISY CONTINUOUS GENERATOR (Creates feature overlap to disable shortcut learning)
def noisy_continuous_base(hw_tier):
    # Tier 1: Powerful (16 cores), Tier 2: Mid-range (8 cores), Tier 3: Budget (4 cores)
    if hw_tier == 1:
        procs = s(480.0, 10.0)
        threads = s(160.0, 15.0)
        load = s(0.2, 0.1)
    elif hw_tier == 2:
        procs = s(450.0, 10.0)
        threads = s(110.0, 10.0)
        load = s(0.4, 0.1)
    else:
        procs = s(420.0, 10.0)
        threads = s(65.0, 8.0)
        load = s(0.7, 0.15)
        
    return int(clamp_nn(procs)), round(clamp_nn(threads), 4), round(clamp_nn(load), 4)


def generate_idle(hw_tier):
    procs, threads, load = noisy_continuous_base(hw_tier)
    cpu = clamp_pct(s(3.5, 1.5))
    return [
        round(cpu, 4),
        round(clamp_pct(cpu + s(3.0, 1.0)), 4),
        round(clamp_nn(s(1.5, 0.8)), 4),     # cpu_variance
        round(clamp_pct(s(32.0, 5.0)), 4),   # ram_mean
        round(s(0.0, 0.2), 4),               # ram_growth_rate
        round(clamp_pct(s(4.0, 1.0)), 4),    # swap_percent
        round(s(0.003, 0.002), 4),           # network_mean
        round(clamp_nn(s(0.04, 0.02)), 4),   # net_symmetry_ratio
        round(clamp_nn(s(0.10, 0.05)), 4),   # net_variance
        round(clamp_nn(s(0.12, 0.04)), 4),   # udp_tcp_socket_ratio
        round(clamp_nn(s(0.5, 0.3)), 4),     # disk_io_mean (Overlaps with Coding/Browsing)
        procs, threads, load,
        round(clamp_nn(s(150.0, 30.0)), 4),  # ctx_switches
        round(clamp_nn(s(3.0, 0.5)), 4),     # cpu_user_system_ratio
        round(clamp_pct(s(0.0, 0.05)), 4),   # psi_cpu
        round(clamp_pct(s(0.0, 0.01)), 4),   # psi_mem
        round(clamp_pct(s(0.0, 0.01)), 4),   # psi_io
        b(0.02), b(0.05), 0                  # Probabilistic flags
    ]


def generate_coding(hw_tier):
    procs, threads, load = noisy_continuous_base(hw_tier)
    cpu = clamp_pct(s(12.0, 4.0)) if hw_tier == 1 else clamp_pct(s(22.0, 6.0))
    return [
        round(cpu, 4),
        round(clamp_pct(cpu + s(15.0, 5.0)), 4),
        round(clamp_nn(s(22.0, 5.0)), 4),    # cpu_variance: HIGH
        round(clamp_pct(s(38.0, 6.0)), 4),   # ram_mean
        round(s(0.5, 0.3), 4),               # ram_growth_rate
        round(clamp_pct(s(6.0, 2.0)), 4),    # swap_percent
        round(s(0.008, 0.004), 4),           # network_mean
        round(clamp_nn(s(0.02, 0.01)), 4),   # net_symmetry_ratio: LOW
        round(clamp_nn(s(1.8, 0.5)), 4),     # net_variance
        round(clamp_nn(s(0.10, 0.03)), 4),   # udp_tcp_socket_ratio
        round(clamp_nn(s(1.8, 0.8)), 4),     # disk_io_mean (Overlaps with Browsing)
        procs, threads, load,
        round(clamp_nn(s(480.0, 60.0)), 4),
        round(clamp_nn(s(4.2, 0.8)), 4),
        round(clamp_pct(s(0.3, 0.1)), 4),
        round(clamp_pct(s(0.0, 0.01)), 4),
        round(clamp_pct(s(0.4, 0.2)), 4),
        b(0.97), b(0.78), b(0.06)             # Probabilistic variation
    ]


def generate_compiling(hw_tier):
    procs, threads, load = noisy_continuous_base(hw_tier)
    # Tier 1 (16 cores): Compiling uses only 15% overall CPU!
    # Tier 3 (4 cores): Compiling uses 88% CPU!
    cpu = clamp_pct(s(15.0, 5.0)) if hw_tier == 1 else (clamp_pct(s(55.0, 10.0)) if hw_tier == 2 else clamp_pct(s(88.0, 5.0)))
    return [
        round(cpu, 4),
        round(clamp_pct(cpu + s(10.0, 3.0)), 4),
        round(clamp_nn(s(6.0, 2.0)), 4),     # cpu_variance
        round(clamp_pct(s(58.0, 8.0)), 4),   # ram_mean
        round(s(4.5, 1.5), 4),               # ram_growth_rate
        round(clamp_pct(s(12.0, 3.0)), 4),   # swap_percent
        round(s(0.005, 0.003), 4),           # network_mean
        round(clamp_nn(s(0.01, 0.005)), 4),  # net_symmetry_ratio
        round(clamp_nn(s(0.08, 0.03)), 4),   # net_variance
        round(clamp_nn(s(0.05, 0.02)), 4),   # udp_tcp_socket_ratio
        round(clamp_nn(s(3.5, 1.5)), 4),     # disk_io_mean: OVERLAPS WITH BROWSING
        procs, threads + 30, load + 1.2,
        round(clamp_nn(s(2200.0, 400.0)), 4),
        round(clamp_nn(s(7.5, 1.5)), 4),
        round(clamp_pct(s(18.0, 5.0)), 4),   # psi_cpu
        round(clamp_pct(s(2.0, 0.8)), 4),
        round(clamp_pct(s(14.0, 4.0)), 4),   # psi_io
        b(0.88), b(0.12), b(0.97)             # Primary indicator: compiler_active
    ]


def generate_gaming(hw_tier):
    procs, threads, load = noisy_continuous_base(hw_tier)
    cpu = clamp_pct(s(45.0, 8.0)) if hw_tier == 1 else clamp_pct(s(75.0, 8.0))
    return [
        round(cpu, 4),
        round(clamp_pct(cpu + s(10.0, 3.0)), 4),
        round(clamp_nn(s(2.5, 0.8)), 4),     # cpu_variance: LOW
        round(clamp_pct(s(68.0, 6.0)), 4),   # ram_mean
        round(s(0.0, 0.2), 4),               # ram_growth_rate
        round(clamp_pct(s(10.0, 2.0)), 4),   # swap_percent
        round(s(0.04, 0.015), 4),            # network_mean
        round(clamp_nn(s(0.25, 0.05)), 4),   # net_symmetry_ratio
        round(clamp_nn(s(0.18, 0.05)), 4),   # net_variance
        round(clamp_nn(s(0.45, 0.08)), 4),   # udp_tcp_socket_ratio: ELEVATED UDP
        round(clamp_nn(s(1.5, 0.6)), 4),     # disk_io_mean
        procs, threads, load,
        round(clamp_nn(s(1600.0, 200.0)), 4),
        round(clamp_nn(s(5.5, 1.0)), 4),
        round(clamp_pct(s(6.0, 2.0)), 4),
        round(clamp_pct(s(0.4, 0.2)), 4),
        round(clamp_pct(s(0.8, 0.3)), 4),
        b(0.02), b(0.06), 0
    ]


def generate_video_call(hw_tier):
    procs, threads, load = noisy_continuous_base(hw_tier)
    cpu = clamp_pct(s(12.0, 3.0)) if hw_tier == 1 else clamp_pct(s(25.0, 5.0))
    return [
        round(cpu, 4),
        round(clamp_pct(cpu + s(12.0, 3.0)), 4),
        round(clamp_nn(s(11.0, 3.0)), 4),    # cpu_variance: MODERATE
        round(clamp_pct(s(45.0, 5.0)), 4),   # ram_mean
        round(s(1.2, 0.8), 4),               # ram_growth_rate
        round(clamp_pct(s(8.0, 2.0)), 4),    # swap_percent
        round(clamp_nn(s(0.085, 0.015)), 4), # network_mean: SUSTAINED TREND
        round(clamp_nn(s(0.72, 0.08)), 4),   # net_symmetry_ratio: HIGH UPLOAD/DOWNLOAD (~0.72)
        round(clamp_nn(s(0.08, 0.02)), 4),   # net_variance: LOW (STEADY WEBRTC STREAM)
        round(clamp_nn(s(0.82, 0.10)), 4),   # udp_tcp_socket_ratio: HIGH UDP
        round(clamp_nn(s(1.2, 0.4)), 4),     # disk_io_mean
        procs, threads, load,
        round(clamp_nn(s(800.0, 100.0)), 4),
        round(clamp_nn(s(2.2, 0.4)), 4),     # cpu_user_system_ratio: LOWER (SYSTEM SOCKET INTERRUPTS)
        round(clamp_pct(s(1.2, 0.4)), 4),
        round(clamp_pct(s(0.1, 0.05)), 4),
        round(clamp_pct(s(0.2, 0.08)), 4),
        b(0.08), b(0.96), 0                  # Primary indicator: browser_active
    ]


def generate_browsing(hw_tier):
    procs, threads, load = noisy_continuous_base(hw_tier)
    cpu = clamp_pct(s(10.0, 3.0)) if hw_tier == 1 else clamp_pct(s(20.0, 5.0))
    return [
        round(cpu, 4),
        round(clamp_pct(cpu + s(15.0, 5.0)), 4),
        round(clamp_nn(s(24.0, 5.0)), 4),    # cpu_variance: VERY HIGH (SPIKY PAGE LOADS)
        round(clamp_pct(s(42.0, 5.0)), 4),   # ram_mean
        round(s(3.5, 2.0), 4),               # ram_growth_rate
        round(clamp_pct(s(10.0, 2.0)), 4),   # swap_percent
        round(clamp_nn(s(0.042, 0.012)), 4), # network_mean: BURSTY TREND
        round(clamp_nn(s(0.03, 0.01)), 4),   # net_symmetry_ratio: LOW (DOWNLOAD HEAVY)
        round(clamp_nn(s(3.6, 0.7)), 4),     # net_variance: HIGH BURSTINESS
        round(clamp_nn(s(0.12, 0.03)), 4),   # udp_tcp_socket_ratio: LOW (MOSTLY TCP)
        round(clamp_nn(s(1.8, 0.5)), 4),     # disk_io_mean
        procs, threads, load,
        round(clamp_nn(s(520.0, 70.0)), 4),
        round(clamp_nn(s(4.1, 0.6)), 4),
        round(clamp_pct(s(0.8, 0.3)), 4),
        round(clamp_pct(s(0.2, 0.08)), 4),
        round(clamp_pct(s(0.8, 0.3)), 4),
        b(0.06), b(0.98), 0                  # Primary indicator: browser_active
    ]


CLASS_GENERATORS = [
    ("Idle",       generate_idle),
    ("Coding",     generate_coding),
    ("Compiling",  generate_compiling),
    ("Gaming",     generate_gaming),
    ("Video_Call", generate_video_call),
    ("Browsing",   generate_browsing),
]


def generate_dataset():
    all_rows = []
    # Loop across 3 Hardware Tiers (1=Powerful, 2=Mid, 3=Budget)
    for label, gen_fn in CLASS_GENERATORS:
        for hw_tier in (1, 2, 3):
            for _ in range(ROWS_PER_CLASS // 3):
                row = gen_fn(hw_tier)
                row.append(label)
                all_rows.append(row)

    random.shuffle(all_rows)
    header = FEATURE_COLUMNS + [LABEL_COLUMN]
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), OUTPUT_FILE
    )
    with open(output_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(all_rows)
    return output_path


def main():
    print("\n  FocusOS Dataset Generator v5 (Hardware-Agnostic Calibration)")
    print("  " + "─"*58)
    path = generate_dataset()
    print(f"  Generated {ROWS_PER_CLASS * len(CLASS_GENERATORS)} rows across 3 Hardware Tiers → {path}\n")

if __name__ == "__main__":
    main()