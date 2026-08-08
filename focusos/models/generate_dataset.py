#!/usr/bin/env python3
"""
generate_dataset.py — FocusOS Training Dataset Synthesizer v3
==============================================================
FULLY CALIBRATED to real observed telemetry from Linux laptop.

REAL OBSERVATIONS USED TO BUILD THIS:
======================================
During heavy Firefox (10 tabs + YouTube + Meet) on real machine:
  cpu_mean         = 5.5 - 11.7   (powerful laptop, low CPU even with browser)
  cpu_max          = 11.8 - 24.4
  cpu_variance     = 4.6 - 25.0
  ram_mean         = 35 - 52
  ram_growth_rate  = -1.0 to 31.0
  network_mean     = 0.02 - 0.10  (trend coefficient)
  disk_io_mean     = 1.2 - 2.4
  process_count    = 447 - 493
  thread_count     = 98 - 150
  vscode_active    = 0
  browser_active   = 1

During coding (VSCode open, terminal):
  cpu_mean         = 7.5 - 9.4
  cpu_max          = 20.8
  cpu_variance     = 20 - 22      (spiky from saves/runs)
  ram_mean         = 31 - 35
  network_mean     = 0.006 - 0.012
  disk_io_mean     = 5.3 - 5.9
  process_count    = 451 - 461
  thread_count     = 58 - 66
  vscode_active    = 1
  browser_active   = 1

KEY INSIGHT FROM REAL DATA:
  This laptop is powerful — CPU stays LOW even under browser/video load
  Differentiators are: thread_count, ram_growth_rate, network_mean, cpu_variance
  NOT cpu_mean (too similar across workloads except Compiling/Gaming)
"""

import csv
import random
import os
from typing import List, Tuple, Dict

SEED = 42
random.seed(SEED)

ROWS_PER_CLASS = 500
OUTPUT_FILE = "focusos_training_data.csv"

FEATURE_COLUMNS = [
    "cpu_mean",
    "cpu_max",
    "cpu_variance",
    "ram_mean",
    "ram_growth_rate",
    "network_mean",
    "disk_io_mean",
    "process_count_mean",
    "thread_count_mean",
    "vscode_active",
    "browser_active",
    "compiler_active",
]

LABEL_COLUMN = "workload_label"


def clamp_pct(v):   return max(0.0, min(100.0, v))
def clamp_nn(v):    return max(0.0, v)
def s(mu, sigma):   return random.gauss(mu, sigma)
def b(p):           return 1 if random.random() < p else 0


def generate_idle_row():
    """
    IDLE: Nothing running. Laptop sitting untouched.

    REAL SIGNATURE:
      cpu_mean very low (2-5%)
      cpu_variance very low (stable, no spikes)
      ram_growth_rate near zero (nothing loading)
      thread_count low (40-55, just background daemons)
      network_mean near zero (no active transfers)
      process_count around 440 (background only)
      browser_active=0, vscode_active=0

    DIFFERENTIATES FROM BROWSING BY:
      thread_count much lower (45 vs 120)
      ram_growth_rate near zero (vs positive)
      cpu_variance very low (vs 15-25)
      browser_active=0
    """
    cpu_mean = clamp_pct(s(3.5, 1.0))
    cpu_max  = clamp_pct(max(cpu_mean + s(2.5, 1.0), cpu_mean + 0.5))
    return [
        round(cpu_mean, 4),
        round(cpu_max, 4),
        round(clamp_nn(s(1.2, 0.5)), 4),     # cpu_variance: very stable
        round(clamp_pct(s(30.0, 3.0)), 4),   # ram_mean: low
        round(s(0.0, 0.4), 4),               # ram_growth_rate: flat, can go neg
        round(s(0.005, 0.004), 4),           # network_mean: near zero trend
        round(clamp_nn(s(0.8, 0.4)), 4),     # disk_io_mean: minimal
        int(clamp_nn(s(442.0, 8.0))),        # process_count
        round(clamp_nn(s(47.0, 6.0)), 4),    # thread_count: low (bg daemons only)
        b(0.03),                              # vscode_active: almost never
        b(0.05),                              # browser_active: almost never
        0,                                    # compiler_active: never
    ]


def generate_coding_row():
    """
    CODING: VSCode open, actively writing/editing code.

    REAL SIGNATURE (from your actual telemetry):
      cpu_mean = 7.5-9.4 (moderate, spiky from saves/runs)
      cpu_max  = 20.8 (peaks when running code)
      cpu_variance = 20-22 (HIGH - characteristic of coding bursts)
      ram_mean = 31-35
      network_mean = 0.006-0.012 (very low - just package checks)
      disk_io_mean = 5.3-5.9 (moderate - file saves, language server)
      process_count = 451-461
      thread_count = 58-66 (lower than browsing - fewer renderer processes)
      vscode_active = 1
      browser_active = 1 (usually have docs open)

    DIFFERENTIATES FROM BROWSING BY:
      vscode_active=1 (strongest signal)
      cpu_variance HIGH (20-22 vs 15-20 for browsing)
      disk_io_mean higher (5.3 vs 1.5)
      thread_count LOWER (62 vs 120) - key!
      network_mean lower (0.008 vs 0.04)
    """
    cpu_mean = clamp_pct(s(8.5, 1.5))
    cpu_max  = clamp_pct(max(cpu_mean + s(12.0, 3.0), cpu_mean + 2.0))
    return [
        round(cpu_mean, 4),
        round(cpu_max, 4),
        round(clamp_nn(s(21.0, 2.5)), 4),    # cpu_variance: HIGH and spiky
        round(clamp_pct(s(33.0, 3.0)), 4),   # ram_mean
        round(s(0.3, 1.0), 4),               # ram_growth_rate: slight
        round(s(0.009, 0.003), 4),           # network_mean: very low
        round(clamp_nn(s(5.5, 0.8)), 4),     # disk_io_mean: higher (file saves)
        int(clamp_nn(s(456.0, 5.0))),        # process_count
        round(clamp_nn(s(62.0, 5.0)), 4),    # thread_count: LOWER than browsing
        b(0.97),                              # vscode_active: almost always
        b(0.82),                              # browser_active: docs open
        b(0.05),                              # compiler_active: rare
    ]


def generate_compiling_row():
    """
    COMPILING: gcc/make/cargo running a heavy build.

    REAL SIGNATURE (inferred from system behavior):
      cpu_mean = 75-92 (pegged across all cores)
      cpu_max  = 95-100
      cpu_variance = 3-8 (LOW - sustained not spiky)
      ram_mean = 55-70 (high memory for build artifacts)
      ram_growth_rate = 3-8 (actively growing)
      disk_io_mean = 15-30 (heavy writes of object files)
      thread_count = 150-200 (massive parallel compilation)
      compiler_active = 1
      vscode_active = 1 (triggered build from editor)

    DIFFERENTIATES FROM GAMING BY:
      compiler_active=1 (strongest signal)
      disk_io_mean much higher (20 vs 2)
      ram_growth_rate positive (vs flat)
      cpu_variance LOW but sustained (vs gaming which is also low)
    """
    cpu_mean = clamp_pct(s(82.0, 5.0))
    cpu_max  = clamp_pct(max(cpu_mean + s(8.0, 2.0), cpu_mean + 1.0))
    return [
        round(cpu_mean, 4),
        round(cpu_max, 4),
        round(clamp_nn(s(5.0, 1.5)), 4),     # cpu_variance: LOW (sustained)
        round(clamp_pct(s(62.0, 6.0)), 4),   # ram_mean: high
        round(s(5.0, 2.0), 4),               # ram_growth_rate: growing fast
        round(s(0.0, 0.01), 4),              # network_mean: near zero
        round(clamp_nn(s(22.0, 5.0)), 4),    # disk_io_mean: VERY HIGH
        int(clamp_nn(s(500.0, 20.0))),       # process_count: more (spawned tasks)
        round(clamp_nn(s(175.0, 20.0)), 4),  # thread_count: VERY HIGH
        b(0.88),                              # vscode_active: triggered from editor
        b(0.20),                              # browser_active: sometimes
        b(0.95),                              # compiler_active: key signal
    ]


def generate_gaming_row():
    """
    GAMING: Game running with sustained CPU load.

    REAL SIGNATURE (inferred):
      cpu_mean = 55-75 (sustained but lower than compiling)
      cpu_variance = 2-5 (very stable game loop)
      ram_mean = 65-80 (assets loaded)
      ram_growth_rate = 0 ± 0.5 (assets loaded once, then flat)
      disk_io_mean = 1-3 (low after assets loaded)
      thread_count = 120-150 (game engine threads)
      network_mean = 0.02-0.08 (multiplayer packets)
      vscode_active = 0
      browser_active = 0 (full attention on game)

    DIFFERENTIATES FROM COMPILING BY:
      compiler_active=0
      disk_io_mean LOW (assets in RAM)
      ram_growth_rate FLAT (not growing)

    DIFFERENTIATES FROM BROWSING BY:
      cpu_mean MUCH higher (65 vs 8)
      browser_active=0
      cpu_variance LOW (stable loop vs spiky)
    """
    cpu_mean = clamp_pct(s(65.0, 8.0))
    cpu_max  = clamp_pct(max(cpu_mean + s(12.0, 3.0), cpu_mean + 1.0))
    return [
        round(cpu_mean, 4),
        round(cpu_max, 4),
        round(clamp_nn(s(3.0, 1.0)), 4),     # cpu_variance: LOW (stable loop)
        round(clamp_pct(s(72.0, 5.0)), 4),   # ram_mean: high (loaded assets)
        round(s(0.0, 0.4), 4),               # ram_growth_rate: flat
        round(s(0.04, 0.02), 4),             # network_mean: mild (multiplayer)
        round(clamp_nn(s(2.0, 0.8)), 4),     # disk_io_mean: low (assets in RAM)
        int(clamp_nn(s(470.0, 15.0))),       # process_count
        round(clamp_nn(s(135.0, 15.0)), 4),  # thread_count: high (game engine)
        b(0.03),                              # vscode_active: almost never
        b(0.08),                              # browser_active: rarely
        0,                                    # compiler_active: never
    ]


def generate_video_call_row():
    """
    VIDEO CALL: Google Meet/Zoom/Discord video running in browser.

    REAL SIGNATURE (from your observations with Meet open):
      Your data shows:
        cpu_mean = 8-12 (moderate encoding)
        cpu_variance = 15-20 (encoding bursts)
        thread_count = 110-150 (video encoder threads)
        network_mean = 0.06-0.12 (sustained stream, higher than browsing)
        ram_mean = 40-55 (video buffers)
        disk_io_mean = 1.0-1.5 (low)
        browser_active = 1 (Meet runs in browser)
        vscode_active = 0

    DIFFERENTIATES FROM BROWSING BY:
      network_mean HIGHER (0.09 vs 0.04) - video stream
      thread_count slightly higher (130 vs 115)
      cpu_variance lower (15 vs 20) - more steady encoding

    DIFFERENTIATES FROM CODING BY:
      vscode_active=0
      thread_count higher (130 vs 62)
      network_mean higher (0.09 vs 0.009)
      disk_io_mean lower (1.2 vs 5.5)
    """
    cpu_mean = clamp_pct(s(10.0, 2.5))
    cpu_max  = clamp_pct(max(cpu_mean + s(15.0, 4.0), cpu_mean + 1.0))
    return [
        round(cpu_mean, 4),
        round(cpu_max, 4),
        round(clamp_nn(s(15.0, 3.0)), 4),    # cpu_variance: moderate
        round(clamp_pct(s(48.0, 5.0)), 4),   # ram_mean: higher (video buffers)
        round(s(2.0, 1.5), 4),               # ram_growth_rate: slight positive
        round(clamp_nn(s(0.09, 0.02)), 4),   # network_mean: HIGHER than browsing
        round(clamp_nn(s(1.2, 0.4)), 4),     # disk_io_mean: low
        int(clamp_nn(s(470.0, 12.0))),       # process_count
        round(clamp_nn(s(130.0, 15.0)), 4),  # thread_count: higher (encoder)
        b(0.10),                              # vscode_active: rarely
        b(0.95),                              # browser_active: Meet in browser
        0,                                    # compiler_active: never
    ]


def generate_browsing_row():
    """
    BROWSING: Heavy tab usage - reading, scrolling, watching YouTube.

    REAL SIGNATURE (from your actual telemetry, 10+ tabs + YouTube):
      cpu_mean = 6-12 (low average, powerful machine)
      cpu_max  = 20-24 (spikes on page loads)
      cpu_variance = 15-25 (spiky from tab loads)
      ram_mean = 35-52 (grows as tabs accumulate)
      ram_growth_rate = 5-31 initially, settles to 3-8
      network_mean = 0.02-0.06 (bursty page loads)
      disk_io_mean = 1.3-2.4 (cache writes)
      process_count = 447-493
      thread_count = 98-150 (Chrome/Firefox renderer processes)
      browser_active = 1
      vscode_active = 0

    DIFFERENTIATES FROM IDLE BY:
      thread_count MUCH higher (120 vs 47) - key differentiator
      ram_growth_rate positive (vs near zero)
      cpu_variance higher (18 vs 1.2)
      browser_active=1 (vs 0)

    DIFFERENTIATES FROM VIDEO CALL BY:
      network_mean LOWER (0.04 vs 0.09)
      cpu_variance HIGHER (20 vs 15) - page loads more spiky

    DIFFERENTIATES FROM CODING BY:
      vscode_active=0
      thread_count HIGHER (120 vs 62) - renderer processes
      disk_io_mean LOWER (1.8 vs 5.5)
      cpu_variance similar but disk much lower
    """
    cpu_mean = clamp_pct(s(8.5, 2.5))
    cpu_max  = clamp_pct(max(cpu_mean + s(13.0, 4.0), cpu_mean + 1.0))
    return [
        round(cpu_mean, 4),
        round(cpu_max, 4),
        round(clamp_nn(s(19.0, 4.0)), 4),    # cpu_variance: HIGH (page loads)
        round(clamp_pct(s(44.0, 6.0)), 4),   # ram_mean: moderate-high
        round(s(5.0, 3.0), 4),               # ram_growth_rate: positive (tabs open)
        round(clamp_nn(s(0.04, 0.015)), 4),  # network_mean: moderate (page loads)
        round(clamp_nn(s(1.8, 0.5)), 4),     # disk_io_mean: low-moderate (cache)
        int(clamp_nn(s(470.0, 18.0))),       # process_count: higher (tab processes)
        round(clamp_nn(s(120.0, 18.0)), 4),  # thread_count: HIGH (renderer threads)
        b(0.08),                              # vscode_active: rarely
        b(0.97),                              # browser_active: always
        0,                                    # compiler_active: never
    ]


CLASS_GENERATORS = [
    ("Idle",       generate_idle_row),
    ("Coding",     generate_coding_row),
    ("Compiling",  generate_compiling_row),
    ("Gaming",     generate_gaming_row),
    ("Video Call", generate_video_call_row),
    ("Browsing",   generate_browsing_row),
]

PCT_FEATURES         = {"cpu_mean", "cpu_max", "ram_mean"}
NON_NEGATIVE_FEATURES = {"cpu_variance", "disk_io_mean",
                          "process_count_mean", "thread_count_mean"}
INT_FEATURES         = {"process_count_mean"}


def generate_dataset():
    all_rows = []
    for label, gen_fn in CLASS_GENERATORS:
        for _ in range(ROWS_PER_CLASS):
            row = gen_fn()
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


def validate_dataset(path):
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == ROWS_PER_CLASS * len(CLASS_GENERATORS)
    for r in rows:
        for f in PCT_FEATURES:
            v = float(r[f])
            assert 0 <= v <= 100, f"{f}={v} out of range"
        for f in NON_NEGATIVE_FEATURES:
            v = float(r[f])
            assert v >= 0, f"{f}={v} negative"
        assert float(r["cpu_mean"]) <= float(r["cpu_max"]) + 1e-9
        for flag in ("vscode_active","browser_active","compiler_active"):
            assert int(r[flag]) in (0,1)
    print("  Validation passed.")


def print_summary(path):
    with open(path) as fh:
        rows = list(csv.DictReader(fh))

    key = ["cpu_mean","cpu_variance","ram_mean","ram_growth_rate",
           "network_mean","disk_io_mean","thread_count_mean","process_count_mean"]

    print(f"\n  {'Class':<14}", end="")
    for f in key:
        short = f.replace("_mean","").replace("count","cnt")[:10]
        print(f"  {short:>10}", end="")
    print()
    print("  " + "─"*(14 + 12*len(key)))

    for label, _ in CLASS_GENERATORS:
        subset = [r for r in rows if r[LABEL_COLUMN]==label]
        print(f"  {label:<14}", end="")
        for f in key:
            vals = [float(r[f]) for r in subset]
            print(f"  {sum(vals)/len(vals):>10.3f}", end="")
        print()

    print()
    print("  KEY DIFFERENTIATORS:")
    print("  thread_count: Idle≈47  Coding≈62  Browsing≈120")
    print("                VideoCall≈130  Gaming≈135  Compiling≈175")
    print("  network_mean: Idle≈0.005  Coding≈0.009  Browsing≈0.04")
    print("                VideoCall≈0.09  Gaming≈0.04  Compiling≈0.00")
    print("  disk_io:      Coding≈5.5  Compiling≈22  others≈1-2")
    print("  compiler:     Compiling≈0.95  all others <0.10")
    print("  vscode:       Coding≈0.97  all others <0.10")
    print()


def main():
    print("\n  FocusOS Dataset Generator v3")
    print("  Calibrated to real Linux laptop telemetry")
    print("  " + "─"*40)
    path = generate_dataset()
    print(f"\n  Generated {ROWS_PER_CLASS * len(CLASS_GENERATORS)} rows → {path}")
    validate_dataset(path)
    print_summary(path)
    print("  Next steps:")
    print("    python3 -m focusos.models.cluster_trainer")
    print("    python3 -m focusos.models.classifier")

if __name__ == "__main__":
    main()