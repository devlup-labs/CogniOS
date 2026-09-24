import os
import sys
import time
import json
import sqlite3
from datetime import datetime, timezone
import streamlit as st
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import DB_PATH
from focusos.models.classifier import WorkloadPredictor, FEATURE_COLUMNS
from simulate_laptop_workload import get_laptop_profile, simulate_synthetic_sample

SIMULATION_STATE_PATH = os.path.join(BASE_DIR, "simulation_state.json")

st.set_page_config(
    page_title="CogniOS Synthetic Test Controller",
    page_icon="🧪",
    layout="wide"
)

# Custom Minimalist CSS
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1.5rem; max-width: 1250px; }
    h1, h2, h3 { font-family: monospace; }
    div[data-testid="stMetricValue"] { font-family: monospace; font-size: 26px; }
    .status-banner-active {
        background: rgba(0, 245, 196, 0.12);
        border: 1px solid #00f5c4;
        border-radius: 8px;
        padding: 10px 14px;
        color: #00f5c4;
        font-family: monospace;
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 16px;
    }
    .status-banner-inactive {
        background: rgba(148, 163, 184, 0.12);
        border: 1px solid #64748b;
        border-radius: 8px;
        padding: 10px 14px;
        color: #94a3b8;
        font-family: monospace;
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 16px;
    }
    .workspace-pill {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 6px;
        padding: 6px 12px;
        color: #93c5fd;
        font-family: monospace;
        font-size: 12px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

hw = get_laptop_profile()

st.title("🧪 CogniOS Synthetic Workload Testing Console")
st.caption(f"Hardware Target: {hw['cores_logical']} Cores | {hw['ram_gb']} GB RAM | Synchronizing directly with: {DB_PATH}")

# Top Sync Toggle
col_sync, col_status = st.columns([1, 2])
with col_sync:
    is_currently_active = False
    if os.path.exists(SIMULATION_STATE_PATH):
        try:
            with open(SIMULATION_STATE_PATH, "r") as f:
                is_currently_active = json.load(f).get("active", False)
        except Exception:
            pass

    sync_active = st.toggle("🟢 Real-Time Sync to Main Dashboard (8501)", value=is_currently_active)

with col_status:
    if sync_active:
        st.markdown('<div class="status-banner-active">● SYNC ACTIVE — Main Dashboard (http://localhost:8501) is mirroring this simulation live</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-banner-inactive">○ SYNC PAUSED — Main Dashboard (http://localhost:8501) is displaying live host telemetry</div>', unsafe_allow_html=True)

# ── MATHEMATICALLY CALIBRATED WORKSPACE BOUNDARIES (from focusos_training_data_ideapad.csv) ──
CALIBRATED_CONFIG = {
    "Coding": {
        "bounds": {
            "cpu": (7.0, 65.0, 0.5),
            "ram": (15.0, 48.0, 0.5),
            "net": (0.000, 0.025, 0.001),
            "udp": (0.40, 1.40, 0.05),
            "sym": (0.000, 0.050, 0.005),
            "var": (0.30, 2.20, 0.05)
        },
        "presets": {
            "Light":  {"cpu": 15.0, "ram": 20.0, "net": 0.004, "udp": 0.65, "sym": 0.015, "var": 0.70, "vs": 1, "comp": 0, "br": 0, "vid": 0},
            "Medium": {"cpu": 28.0, "ram": 28.0, "net": 0.008, "udp": 0.85, "sym": 0.020, "var": 1.20, "vs": 1, "comp": 1, "br": 1, "vid": 0},
            "Heavy":  {"cpu": 55.0, "ram": 40.0, "net": 0.015, "udp": 1.10, "sym": 0.030, "var": 1.80, "vs": 1, "comp": 1, "br": 1, "vid": 0},
        }
    },
    "Browsing": {
        "bounds": {
            "cpu": (2.0, 20.0, 0.5),
            "ram": (15.0, 36.0, 0.5),
            "net": (0.010, 0.090, 0.002),
            "udp": (0.20, 0.70, 0.02),
            "sym": (0.005, 0.055, 0.005),
            "var": (2.00, 5.80, 0.10)
        },
        "presets": {
            "Light":  {"cpu": 5.0,  "ram": 18.0, "net": 0.025, "udp": 0.30, "sym": 0.015, "var": 2.80, "vs": 0, "comp": 0, "br": 1, "vid": 0},
            "Medium": {"cpu": 9.5,  "ram": 24.0, "net": 0.045, "udp": 0.45, "sym": 0.030, "var": 3.80, "vs": 0, "comp": 0, "br": 1, "vid": 0},
            "Heavy":  {"cpu": 16.0, "ram": 32.0, "net": 0.075, "udp": 0.60, "sym": 0.045, "var": 4.80, "vs": 0, "comp": 0, "br": 1, "vid": 0},
        }
    },
    "Video Call": {
        "bounds": {
            "cpu": (6.0, 25.0, 0.5),
            "ram": (15.0, 32.0, 0.5),
            "net": (0.050, 0.130, 0.002),
            "udp": (1.10, 2.30, 0.05),
            "sym": (0.500, 0.950, 0.01),
            "var": (0.04, 0.14, 0.005)
        },
        "presets": {
            "Light":  {"cpu": 9.0,  "ram": 18.0, "net": 0.065, "udp": 1.35, "sym": 0.65, "var": 0.06, "vs": 0, "comp": 0, "br": 1, "vid": 1},
            "Medium": {"cpu": 14.0, "ram": 22.0, "net": 0.085, "udp": 1.65, "sym": 0.75, "var": 0.09, "vs": 0, "comp": 0, "br": 1, "vid": 1},
            "Heavy":  {"cpu": 21.0, "ram": 27.0, "net": 0.115, "udp": 2.00, "sym": 0.88, "var": 0.12, "vs": 0, "comp": 0, "br": 1, "vid": 1},
        }
    },
    "Idle": {
        "bounds": {
            "cpu": (0.2, 5.0, 0.1),
            "ram": (10.5, 17.0, 0.2),
            "net": (0.000, 0.005, 0.0005),
            "udp": (0.95, 1.75, 0.02),
            "sym": (0.000, 0.090, 0.005),
            "var": (0.005, 0.10, 0.005)
        },
        "presets": {
            "Light":  {"cpu": 0.8, "ram": 11.5, "net": 0.001, "udp": 1.15, "sym": 0.02, "var": 0.02, "vs": 0, "comp": 0, "br": 0, "vid": 0},
            "Medium": {"cpu": 1.8, "ram": 13.5, "net": 0.002, "udp": 1.35, "sym": 0.04, "var": 0.05, "vs": 0, "comp": 0, "br": 0, "vid": 0},
            "Heavy":  {"cpu": 3.8, "ram": 15.5, "net": 0.003, "udp": 1.55, "sym": 0.06, "var": 0.08, "vs": 0, "comp": 0, "br": 0, "vid": 0},
        }
    }
}

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Configure Synthetic Workload")
    workload = st.selectbox("Workload Category", list(CALIBRATED_CONFIG.keys()), index=0)
    intensity = st.radio("Intensity Level", ["Light", "Medium", "Heavy"], index=1, horizontal=True)

    cfg = CALIBRATED_CONFIG[workload]
    base = cfg["presets"][intensity]
    b = cfg["bounds"]

    st.markdown(
        f'<div class="workspace-pill">Calibrated Workspace: CPU [{b["cpu"][0]}% - {b["cpu"][1]}%] | RAM [{b["ram"][0]}% - {b["ram"][1]}%]</div>',
        unsafe_allow_html=True
    )

    st.write("---")
    st.caption("Fine-tune Calibrated Sliders (Constrained to Workload Boundary):")

    # Dynamic clamped sliders respecting workload limits
    cpu_val = st.slider("CPU Usage (%)", b["cpu"][0], b["cpu"][1], float(base["cpu"]), step=b["cpu"][2])
    ram_val = st.slider("RAM Usage (%)", b["ram"][0], b["ram"][1], float(base["ram"]), step=b["ram"][2])
    net_val = st.slider("Network Transfer Rate (MB/s)", b["net"][0], b["net"][1], float(base["net"]), step=b["net"][2], format="%.4f")
    udp_val = st.slider("UDP / TCP Socket Ratio", b["udp"][0], b["udp"][1], float(base["udp"]), step=b["udp"][2])
    sym_val = st.slider("Network Symmetry (Upload/Download Balance)", b["sym"][0], b["sym"][1], float(base["sym"]), step=b["sym"][2], format="%.3f")
    var_val = st.slider("Network Variance (Traffic Burstiness)", b["var"][0], b["var"][1], float(base["var"]), step=b["var"][2], format="%.3f")

    st.write("---")
    st.caption("Context Indicators (Auto-configured per workload):")
    c_flag1, c_flag2, c_flag3 = st.columns(3)
    vs_flag = c_flag1.checkbox("VSCode Active", value=bool(base["vs"]))
    br_flag = c_flag2.checkbox("Browser Active", value=bool(base["br"]))
    comp_flag = c_flag3.checkbox("Compiler Active", value=bool(base["comp"]))
    vid_flag = st.checkbox("Video Call Active (Camera/Mic Flag)", value=bool(base["vid"]))

with col2:
    st.subheader("2. Model Prediction & Real-Time Sync")
    
    # Generate feature dataframe with calibrated workspace parameters
    df_sample = simulate_synthetic_sample(
        workload_type=workload,
        cpu_load_pct=cpu_val,
        ram_usage_pct=ram_val,
        network_mb_s=net_val,
        net_symmetry=sym_val,
        net_variance=var_val,
        udp_tcp_ratio=udp_val,
        vscode_active=int(vs_flag),
        browser_active=int(br_flag),
        compiler_active=int(comp_flag),
        video_call_active=int(vid_flag)
    )

    try:
        predictor = WorkloadPredictor()
        result = predictor.predict(df_sample)
    except Exception as e:
        st.error(f"Error loading model: {e}")
        result = None

    predicted_workload = result["workload"].upper() if result else workload.upper()

    if result:
        st.metric("Predicted Workload", predicted_workload, f"{result['confidence']}% Confidence")
        
        prob_df = pd.DataFrame([result["probabilities"]]).T
        prob_df.columns = ["Probability (%)"]
        st.bar_chart(prob_df)

    # Prepare top process and process table
    top_proc = "code" if vs_flag else ("gcc" if comp_flag else ("chrome" if br_flag else ("zoom" if vid_flag else "systemd")))
    procs_list = []
    if vs_flag: procs_list.append({"pid": 1024, "name": "code", "cpu": round(cpu_val * 0.45, 1), "ram": round(ram_val * 0.35, 1)})
    if comp_flag: procs_list.append({"pid": 1025, "name": "gcc", "cpu": round(cpu_val * 0.50, 1), "ram": round(ram_val * 0.30, 1)})
    if br_flag: procs_list.append({"pid": 1030, "name": "chrome", "cpu": round(cpu_val * 0.40, 1), "ram": round(ram_val * 0.45, 1)})
    if vid_flag: procs_list.append({"pid": 1040, "name": "zoom", "cpu": round(cpu_val * 0.50, 1), "ram": round(ram_val * 0.40, 1)})
    procs_list.append({"pid": 1, "name": "systemd", "cpu": 0.1, "ram": 0.4})
    procs_list.append({"pid": 512, "name": "dbus-daemon", "cpu": 0.2, "ram": 0.6})

    evidence_list = [
        {"process": top_proc, "signal": f"{top_proc} running ({cpu_val:.1f}% CPU)"},
        {"signal": f"Calibrated synthetic simulation ({intensity} {workload})"}
    ]

    # Handle Synchronous Broadcast State
    if sync_active:
        sim_payload = {
            "active": True,
            "workload": predicted_workload,
            "intensity": intensity,
            "confidence": result["confidence"] if result else 95.0,
            "state": "CONFIRMED",
            "cpu_pct": cpu_val,
            "memory_pct": ram_val,
            "disk_read_mb": round(2.5 if comp_flag else 0.2, 1),
            "disk_write_mb": round(4.8 if comp_flag else 0.5, 1),
            "net_in_mb": round(net_val * sym_val, 3),
            "net_out_mb": round(net_val * (1.0 - sym_val), 3),
            "top_process": top_proc,
            "processes": procs_list,
            "evidence": evidence_list,
            "probabilities": result["probabilities"] if result else {},
            "updated_at": time.time()
        }
        with open(SIMULATION_STATE_PATH, "w") as f:
            json.dump(sim_payload, f, indent=2)

        # Also write fresh row to DB
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO workload_events (
                    timestamp, workload, state, cpu_attribution, ram_attribution,
                    workload_score, system_cpu, system_memory, top_process, evidence_json, persistence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                time.time(), predicted_workload, "CONFIRMED", 0.85, 0.75,
                (result["confidence"]/100.0) if result else 0.95,
                cpu_val, ram_val * 240.0, top_proc, json.dumps(evidence_list), 5
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass

    else:
        if os.path.exists(SIMULATION_STATE_PATH):
            with open(SIMULATION_STATE_PATH, "w") as f:
                json.dump({"active": False}, f)

    st.write("---")
    st.caption("Active Status: " + ("Broadcasting calibrated state to Port 8501" if sync_active else "Standby (Host telemetry active)"))
