"""Streamlit Dashboard main entry point for CogniOS matching Stitch design specs."""
# Force Streamlit Hot-Reload
import os
import sys
import signal
import subprocess
import psutil

# Ensure workspace root is in sys.path to import check_requirements
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Auto-check & gracefully install missing requirements before importing dependent packages
try:
    from check_requirements import ensure_requirements
    ensure_requirements(auto_install=True, quiet=True)
except Exception:
    pass

import streamlit as st

st.set_page_config(
    page_title="CogniOS — System Observability & AI Diagnostics",
    page_icon="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/svgs/solid/terminal.svg",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False
    def st_autorefresh(*args, **kwargs):
        pass
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import time
import dashboard.data_provider as dp
from dashboard.views import system_overview, focusos_view, blackbox_view, os_doctor_view
import config

def _close_dialog():
    st.session_state["active_dialog"] = None


@st.dialog("CogniOS Configuration & Thresholds", width="large", on_dismiss=_close_dialog)
def render_config_dialog():
    st.markdown("Customize live operational thresholds and engine parameters. Changes are saved and applied immediately.")
    
    tab1, tab2, tab3 = st.tabs(["FocusOS Parameters", "BlackBox Alerts", "AI & LLM Settings"])
    
    with tab1:
        st.subheader("FocusOS Optimization & Attribution")
        c1, c2 = st.columns(2)
        with c1:
            contention = st.slider("CPU Contention Threshold (%)", min_value=15.0, max_value=85.0, value=float(getattr(config, "RULE_SYSTEM_CPU_CONTENTION", 35.0)), step=1.0, help="System CPU% before priority optimization kicks in")
            cpu_thresh = st.number_input("Process Active CPU Threshold (%)", min_value=0.5, max_value=20.0, value=float(getattr(config, "RULE_CPU_ACTIVE_THRESHOLD", 2.0)), step=0.5)
            ram_thresh = st.number_input("Process Active RAM Threshold (MB)", min_value=50.0, max_value=2000.0, value=float(getattr(config, "RULE_RAM_ACTIVE_THRESHOLD", 150.0)), step=25.0)
        with c2:
            persistence = st.number_input("Persistence Cycle Gate", min_value=1, max_value=10, value=int(getattr(config, "RULE_PERSISTENCE_COUNT", 3)), step=1, help="Consecutive evaluation cycles required before confirming a workload")
            cooldown = st.number_input("Policy Cooldown (seconds)", min_value=10, max_value=300, value=int(getattr(config, "RULE_COOLDOWN_SEC", 45)), step=5, help="Minimum seconds between automated scheduling priority adjustments")
            attribution_thresh = st.slider("Workload Attribution Threshold", min_value=0.10, max_value=0.90, value=float(getattr(config, "RULE_ATTRIBUTION_THRESHOLD", 0.40)), step=0.05)

    with tab2:
        st.subheader("BlackBox Critical Thresholds & Buffer")
        b1, b2 = st.columns(2)
        with b1:
            cpu_crit = st.slider("Critical CPU Alert Threshold (%)", min_value=50.0, max_value=99.0, value=float(getattr(config, "BLACKBOX_CPU_CRITICAL", 90.0)), step=1.0)
            mem_crit = st.slider("Critical Memory Alert Threshold (%)", min_value=50.0, max_value=99.0, value=float(getattr(config, "BLACKBOX_MEM_CRITICAL", 90.0)), step=1.0)
            temp_crit = st.slider("Critical Temperature Threshold (°C)", min_value=60.0, max_value=105.0, value=float(getattr(config, "BLACKBOX_TEMP_CRITICAL", 85.0)), step=1.0)
        with b2:
            zombie_lim = st.number_input("Zombie Process Limit", min_value=1, max_value=50, value=int(getattr(config, "BLACKBOX_ZOMBIE_LIMIT", 10)), step=1)
            cur_win = getattr(config, "BLACKBOX_WINDOW_SEC", 1800)
            win_opts = [900, 1800, 3600]
            win_idx = win_opts.index(cur_win) if cur_win in win_opts else 1
            window_sec = st.selectbox("Rolling Buffer Duration", options=win_opts, index=win_idx, format_func=lambda x: f"{x // 60} Minutes")
            cur_ref = getattr(config, "AUTO_REFRESH", 2)
            ref_opts = [1, 2, 5, 10]
            ref_idx = ref_opts.index(cur_ref) if cur_ref in ref_opts else 1
            refresh_rate = st.selectbox("Dashboard Auto-Refresh Rate", options=ref_opts, index=ref_idx, format_func=lambda x: f"{x} Seconds")

    with tab3:
        st.subheader("AI Explainability & Groq LLM API")
        model_name = st.text_input("Groq LLM Model", value=str(getattr(config, "GROQ_MODEL", "qwen/qwen3.8-27b")), help="e.g. qwen/qwen3.8-27b, llama-3.3-70b-versatile, mixtral-8x7b-32768")
        api_key = st.text_input("Groq API Key", value=str(getattr(config, "GROQ_API_KEY", "")), type="password", help="Enter your Groq API key (starts with gsk_...)")

    st.markdown("<hr style='border-color:#1e293b; margin:16px 0;'>", unsafe_allow_html=True)
    c_save, c_cancel = st.columns(2)
    with c_save:
        if st.button("Save Changes", type="primary", use_container_width=True):
            updates = {
                "RULE_SYSTEM_CPU_CONTENTION": float(contention),
                "RULE_CPU_ACTIVE_THRESHOLD": float(cpu_thresh),
                "RULE_RAM_ACTIVE_THRESHOLD": float(ram_thresh),
                "RULE_PERSISTENCE_COUNT": int(persistence),
                "RULE_COOLDOWN_SEC": int(cooldown),
                "RULE_ATTRIBUTION_THRESHOLD": float(attribution_thresh),
                "BLACKBOX_CPU_CRITICAL": float(cpu_crit),
                "BLACKBOX_MEM_CRITICAL": float(mem_crit),
                "BLACKBOX_TEMP_CRITICAL": float(temp_crit),
                "BLACKBOX_ZOMBIE_LIMIT": int(zombie_lim),
                "BLACKBOX_WINDOW_SEC": int(window_sec),
                "AUTO_REFRESH": int(refresh_rate),
                "GROQ_MODEL": model_name.strip(),
                "GROQ_API_KEY": api_key.strip(),
            }
            config.save_config_overrides(updates)
            st.session_state["active_dialog"] = None
            st.toast("Configuration saved successfully!", icon="✅")
            st.rerun()
    with c_cancel:
        if st.button("Close", use_container_width=True):
            st.session_state["active_dialog"] = None
            st.rerun()


@st.dialog("CogniOS — System Guide & Help", width="large", on_dismiss=_close_dialog)
def render_help_dialog():
    st.markdown("""
    ### 🧭 CogniOS Intelligent Observability Platform
    CogniOS operates directly in Linux user space without kernel patches, orchestrating telemetry gathering, anomaly detection, dynamic prioritization, and flight-recorder crash forensics.
    
    ---
    
    #### 📦 Observability Matrix
    - **System Overview**: 1-second system telemetry (CPU / RAM / Disk / Net / Temp) via `/proc` and `psutil`.
    - **OS Doctor AI**: Workload-specific Isolation Forest models detecting anomalous performance deviations with automated root-cause diagnosis.
    - **FocusOS Engine**: Deterministic rule engine and XGBoost ML workload classifier. When high CPU contention occurs, it boosts priority (`nice -10` to `-5`) of active toolchains and throttles background tasks (`nice +7`), with full automatic state rollback.
    - **BlackBox Recorder**: 30-minute circular rolling buffer in SQLite WAL mode. Automatically tracks daemon heartbeats and constructs causal event chains (CPU spikes, memory leaks, I/O storms) with Groq AI synthesis.
    
    ---
    
    #### ⚙️ CLI Quick Commands
    ```bash
    # Start all background telemetry, FocusOS & OS Doctor engines:
    python cognios_as_daemon.py

    # Launch Unified Dashboard in your browser:
    python main.py --ui browser

    # Launch native desktop Qt shell:
    python main.py --ui desktop
    ```

    ---
    
    #### 📊 Status Indicators
    - **● DAEMON RUNNING**: Indicates background collector loops are actively gathering data. Click to stop.
    - **● SYSTEM IDLE**: Indicates background daemon is stopped. Click to launch.
    - **PID**: The active operating system process ID of `cognios_as_daemon.py`.
    - **MODE (WAL)**: SQLite Write-Ahead Logging active for non-blocking concurrent transactions.
    - **Uptime**: Elapsed runtime of the active daemon session.
    - **Latency**: Real-time SQLite storage transaction latency.
    """)
    st.markdown("<hr style='border-color:#1e293b; margin:16px 0;'>", unsafe_allow_html=True)
    if st.button("Close Guide", type="primary", use_container_width=True):
        st.session_state["active_dialog"] = None
        st.rerun()


# Inject Font Awesome, Google Fonts and Custom Dark Cyberpunk Button/Card CSS
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important;
    }

    .stApp {
        background-color: #070a11 !important;
        color: #e2e8f0;
    }

    header[data-testid="stHeader"],
    .stAppHeader {
        background: transparent !important;
        z-index: 1000 !important;
        pointer-events: none !important;
    }

    div[data-testid="stToolbar"],
    .stAppToolbar {
        background: transparent !important;
        display: flex !important;
        visibility: visible !important;
        pointer-events: none !important;
    }

    /* Hide ONLY Deploy button, three-dots menu & toolbar actions on the right */
    .stAppDeployButton,
    div[data-testid="stAppDeployButton"],
    button[data-testid="stAppDeployButton"],
    div[data-testid="stDecoration"],
    div[data-testid="stHeaderActionElements"],
    header[data-testid="stHeader"] .stAppDeployButton,
    header[data-testid="stHeader"] [data-testid="stAppDeployButton"],
    header[data-testid="stHeader"] [data-testid="stToolbarActions"],
    header[data-testid="stHeader"] [data-testid="stStatusWidget"],
    header[data-testid="stHeader"] [data-testid="stActionMenu"],
    header[data-testid="stHeader"] #MainMenu,
    header[data-testid="stHeader"] [data-testid="manage-app-button"],
    header[data-testid="stHeader"] button[aria-label*="menu" i],
    header[data-testid="stHeader"] button[title*="menu" i],
    header[data-testid="stHeader"] button[title*="Deploy" i],
    header[data-testid="stHeader"] a[href*="streamlit.io" i],
    div[class*="e1yxiy6j6"],
    #MainMenu,
    footer {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        width: 0 !important;
        overflow: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* --- Collapsed Sidebar Toggle (Expand Sidebar Button) --- */
    button[data-testid="stExpandSidebarButton"],
    [data-testid="stExpandSidebarButton"],
    div[data-testid="stSidebarCollapsedControl"],
    button[data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: inline-flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        position: fixed !important;
        top: 12px !important;
        left: 14px !important;
        background: linear-gradient(135deg, rgba(0, 245, 196, 0.2) 0%, rgba(14, 21, 34, 0.95) 100%) !important;
        border: 1px solid rgba(0, 245, 196, 0.6) !important;
        border-radius: 10px !important;
        color: #00f5c4 !important;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.7), 0 0 16px rgba(0, 245, 196, 0.35) !important;
        padding: 6px 12px !important;
        cursor: pointer !important;
        z-index: 999999 !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    button[data-testid="stExpandSidebarButton"]:hover,
    [data-testid="stExpandSidebarButton"]:hover,
    div[data-testid="stSidebarCollapsedControl"]:hover,
    button[data-testid="stSidebarCollapsedControl"]:hover,
    [data-testid="collapsedControl"]:hover {
        background: rgba(0, 245, 196, 0.3) !important;
        border-color: #00f5c4 !important;
        box-shadow: 0 0 24px rgba(0, 245, 196, 0.6) !important;
        transform: scale(1.08) !important;
    }

    button[data-testid="stExpandSidebarButton"] svg,
    button[data-testid="stExpandSidebarButton"] span,
    div[data-testid="stSidebarCollapsedControl"] svg,
    button[data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="collapsedControl"] svg {
        fill: #00f5c4 !important;
        color: #00f5c4 !important;
    }

    /* Inside-sidebar collapse toggle */
    [data-testid="stSidebarCollapseButton"] button {
        background: rgba(255, 255, 255, 0.04) !important;
        color: #94a3b8 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stSidebarCollapseButton"] button:hover {
        background: rgba(0, 245, 196, 0.15) !important;
        color: #00f5c4 !important;
        border-color: rgba(0, 245, 196, 0.4) !important;
    }
    [data-testid="stSidebarCollapseButton"] button svg {
        fill: #00f5c4 !important;
    }

    /* Main Viewport & Block Container Spacing */
    div.block-container,
    div[data-testid="stMainBlockContainer"] {
        padding-top: 2rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 2.2rem !important;
        padding-right: 2.2rem !important;
        max-width: 100% !important;
    }

    /* Headings & Typography */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        letter-spacing: -0.5px !important;
    }

    /* --- Sidebar Container Styling --- */
    section[data-testid="stSidebar"] {
        background: #05080e !important;
        border-right: none !important;
    }
    
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 1.2rem;
        padding-left: 1.1rem;
        padding-right: 1.1rem;
    }

    /* --- Brand Header Card --- */
    .sidebar-brand-card {
        background: linear-gradient(135deg, rgba(0, 245, 196, 0.12) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(0, 245, 196, 0.25) !important;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 14px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    }

    .sidebar-logo-box {
        background: #00f5c4;
        color: #05080e;
        width: 46px;
        height: 46px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        box-shadow: 0 0 20px rgba(0, 245, 196, 0.4);
    }

    .sidebar-brand-title {
        font-size: 24px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.8px;
        line-height: 1.1;
    }

    .sidebar-brand-sub {
        font-size: 11px;
        color: #00f5c4;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 1.2px;
        margin-top: 4px;
        display: flex;
        align-items: center;
        gap: 6px;
        font-weight: 700;
    }

    /* Live Pulsing Dot */
    @keyframes pulse-ring {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 245, 196, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 7px rgba(0, 245, 196, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 245, 196, 0); }
    }
    .pulse-green {
        width: 8px;
        height: 8px;
        background-color: #00f5c4;
        border-radius: 50%;
        display: inline-block;
        animation: pulse-ring 2s infinite;
    }

    /* --- Sidebar Category Dividers --- */
    .sidebar-category-header {
        font-size: 10px;
        font-weight: 800;
        color: #475569;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin: 20px 0 10px 6px;
    }

    /* --- Sidebar Navigation Buttons --- */
    section[data-testid="stSidebar"] div.stButton > button {
        background: linear-gradient(180deg, #0e1524 0%, #080c14 100%) !important;
        color: #cbd5e1 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        font-size: 13.5px !important;
        font-weight: 600 !important;
        text-align: left !important;
        width: 100% !important;
        margin-bottom: 8px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 14px rgba(0,0,0,0.3) !important;
    }

    section[data-testid="stSidebar"] div.stButton > button:hover {
        background: #141f32 !important;
        color: #ffffff !important;
        border: 1px solid rgba(0, 245, 196, 0.5) !important;
        transform: translateX(3px) !important;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4), 0 0 14px rgba(0, 245, 196, 0.2) !important;
    }

    /* Active Nav Item Highlighting */
    .nav-active div.stButton > button {
        background: linear-gradient(90deg, rgba(0, 245, 196, 0.16) 0%, rgba(0, 245, 196, 0.02) 100%) !important;
        color: #00f5c4 !important;
        border: 1px solid rgba(0, 245, 196, 0.55) !important;
        border-left: 4px solid #00f5c4 !important;
        box-shadow: 0 0 20px rgba(0, 245, 196, 0.22) !important;
        font-weight: 700 !important;
    }

    .nav-active div.stButton > button span {
        color: #00f5c4 !important;
    }

    /* --- GLOBAL STREAMLIT MAIN CONTENT BUTTONS STYLING --- */
    div.stButton > button {
        background: linear-gradient(180deg, #101726 0%, #0a0f19 100%) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35) !important;
    }

    div.stButton > button:hover {
        background: #17243a !important;
        color: #00f5c4 !important;
        border: 1px solid rgba(0, 245, 196, 0.5) !important;
        box-shadow: 0 0 16px rgba(0, 245, 196, 0.35) !important;
        transform: translateY(-1px) !important;
    }

    /* Primary Action Buttons */
    button[kind="primary"],
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, rgba(0, 245, 196, 0.22) 0%, rgba(14, 165, 233, 0.18) 100%) !important;
        color: #00f5c4 !important;
        border: 1px solid rgba(0, 245, 196, 0.5) !important;
        box-shadow: 0 4px 18px rgba(0, 245, 196, 0.15) !important;
        font-weight: 700 !important;
    }
    button[kind="primary"]:hover,
    div.stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, rgba(0, 245, 196, 0.35) 0%, rgba(14, 165, 233, 0.28) 100%) !important;
        color: #ffffff !important;
        border-color: #00f5c4 !important;
        box-shadow: 0 0 22px rgba(0, 245, 196, 0.45) !important;
    }

    /* Emergency Stop Button Wrapper */
    .emergency-btn-box div.stButton > button {
        background: rgba(239, 68, 68, 0.15) !important;
        color: #ef4444 !important;
        border: 1px solid rgba(239, 68, 68, 0.4) !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
    }
    .emergency-btn-box div.stButton > button:hover {
        background: rgba(239, 68, 68, 0.3) !important;
        color: #ffffff !important;
        border-color: #ef4444 !important;
        box-shadow: 0 0 20px rgba(239, 68, 68, 0.5) !important;
    }

    /* Synthesize Diagnosis Button Wrapper */
    .synth-btn-box div.stButton > button {
        background: linear-gradient(135deg, rgba(0, 245, 196, 0.2) 0%, rgba(14, 165, 233, 0.15) 100%) !important;
        color: #00f5c4 !important;
        border: 1px solid rgba(0, 245, 196, 0.4) !important;
        font-weight: 700 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    .synth-btn-box div.stButton > button:hover {
        background: linear-gradient(135deg, rgba(0, 245, 196, 0.35) 0%, rgba(14, 165, 233, 0.28) 100%) !important;
        color: #ffffff !important;
        border-color: #00f5c4 !important;
        box-shadow: 0 0 20px rgba(0, 245, 196, 0.4) !important;
    }

    /* --- AI Response Terminal Container Styling --- */
    .ai-response-container {
        background: linear-gradient(180deg, #090f19 0%, #060a12 100%) !important;
        border: 1px solid #162336 !important;
        border-radius: 12px !important;
        padding: 20px 22px !important;
        font-size: 13.5px !important;
        line-height: 1.7 !important;
        color: #cbd5e1 !important;
        max-height: 280px !important;
        overflow-y: auto !important;
        box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.5) !important;
        margin-bottom: 18px !important;
        scrollbar-width: thin !important;
        scrollbar-color: #1f2d42 rgba(14, 21, 34, 0.5) !important;
        resize: none !important;
    }

    .forensic-chain-container {
        scrollbar-width: thin !important;
        scrollbar-color: #1f2d42 rgba(14, 21, 34, 0.5) !important;
        resize: none !important;
    }

    .ai-response-container h1, 
    .ai-response-container h2, 
    .ai-response-container h3, 
    .ai-response-container h4 {
        color: #00f5c4 !important;
        font-size: 13px !important;
        font-weight: 800 !important;
        font-family: 'JetBrains Mono', monospace !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        margin-top: 16px !important;
        margin-bottom: 8px !important;
        border-bottom: 1px solid rgba(0, 245, 196, 0.15) !important;
        padding-bottom: 4px !important;
    }

    .ai-response-container h1:first-child, 
    .ai-response-container h2:first-child, 
    .ai-response-container h3:first-child {
        margin-top: 0 !important;
    }

    .ai-response-container strong {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    .ai-response-container ul, .ai-response-container ol {
        padding-left: 20px !important;
        margin-top: 6px !important;
        margin-bottom: 10px !important;
    }

    .ai-response-container li {
        margin-bottom: 6px !important;
        color: #e2e8f0 !important;
    }

    .ai-response-container p {
        margin-bottom: 10px !important;
    }

    /* PID Heatmap Tile Buttons in OS Doctor */
    .pid-tile-box div.stButton > button {
        background: #0e1522 !important;
        color: #00f5c4 !important;
        border: 1px solid #1a273b !important;
        border-radius: 8px !important;
        padding: 10px 4px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25) !important;
    }
    .pid-tile-box div.stButton > button:hover {
        background: #162134 !important;
        border-color: #00f5c4 !important;
        box-shadow: 0 0 14px rgba(0, 245, 196, 0.4) !important;
    }

    /* Status Card Footer */
    div[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(180deg, #0e1524 0%, #080c14 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 14px !important;
        padding: 14px !important;
        margin-top: 18px !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45) !important;
    }

    .top-status-pill {
        background: linear-gradient(180deg, #0e1524 0%, #080c14 100%);
        border: 1px solid rgba(255, 255, 255, 0.07) !important;
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 11.5px;
        font-family: 'JetBrains Mono', monospace;
        color: #cbd5e1;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.3);
        transition: all 0.2s ease;
    }
    .top-status-pill:hover {
        border-color: rgba(0, 245, 196, 0.3) !important;
        color: #f8fafc;
    }

    .cognios-card {
        background: linear-gradient(180deg, #0e1524 0%, #080c14 100%);
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        border-top: 1px solid rgba(0, 245, 196, 0.25) !important;
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.45);
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
        position: relative;
        overflow: hidden;
    }
    .cognios-card:hover {
        transform: translateY(-2px);
        border-color: rgba(0, 245, 196, 0.35) !important;
        box-shadow: 0 12px 35px rgba(0, 245, 196, 0.08), 0 8px 24px rgba(0, 0, 0, 0.5);
    }
    .cognios-metric-val {
        font-size: 40px;
        font-weight: 800;
        color: #00f5c4;
        font-family: 'JetBrains Mono', monospace;
        line-height: 1.1;
        letter-spacing: -1px;
    }
    .cognios-badge {
        background: rgba(0, 245, 196, 0.12);
        color: #00f5c4;
        border: none !important;
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 0.5px;
    }

    /* Form Inputs */
    .stTextInput > div > div > input {
        background-color: #0e1522 !important;
        color: #ffffff !important;
        border: 1px solid #1a273b !important;
        border-radius: 8px !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 14px !important;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.3) !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #00f5c4 !important;
        box-shadow: 0 0 12px rgba(0, 245, 196, 0.3) !important;
    }

    /* Streamlit Bordered Container Styling to match CogniOS Cards */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #0d121c !important;
        border: 1px solid #162336 !important;
        border-radius: 14px !important;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35) !important;
        padding: 20px 22px !important;
        margin-bottom: 18px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: #1f334d !important;
    }

    /* Slider track & thumb styling */
    div[data-baseweb="slider"] {
        margin: 6px 0 !important;
    }
    div[data-baseweb="slider"] div[role="slider"] {
        background-color: #00f5c4 !important;
        border: 2px solid #070a11 !important;
        box-shadow: 0 0 12px rgba(0, 245, 196, 0.6) !important;
    }
    div[data-baseweb="slider"] > div > div {
        background: #151e2d !important;
    }
    div[data-baseweb="slider"] > div > div > div {
        background: #00f5c4 !important;
    }

    /* Clean button styling with sleek hover effect */
    .stButton > button {
        background-color: #0f1624 !important;
        color: #e2e8f0 !important;
        border: 1px solid #1c2a3d !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        padding: 6px 12px !important;
        height: auto !important;
        min-height: 36px !important;
        max-height: 42px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    .stButton > button p,
    .stButton > button span {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        margin: 0 !important;
    }
    /* Primary & Form Submit Buttons (e.g. Synthesize button) */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"],
    button[data-testid="stBaseButton-primaryFormSubmit"],
    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stFormSubmitButton"] button {
        background: #00f5c4 !important;
        border: 1px solid #00f5c4 !important;
        color: #070a11 !important;
        font-weight: 800 !important;
        box-shadow: 0 0 18px rgba(0, 245, 196, 0.4) !important;
        height: auto !important;
        min-height: 38px !important;
        max-height: 42px !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover,
    button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
    div[data-testid="stFormSubmitButton"] > button:hover,
    div[data-testid="stFormSubmitButton"] button:hover {
        background: #00dfb2 !important;
        border-color: #00dfb2 !important;
        color: #000000 !important;
        box-shadow: 0 0 24px rgba(0, 245, 196, 0.65) !important;
    }
    .stButton > button[kind="primary"] *,
    .stButton > button[data-testid="stBaseButton-primary"] *,
    button[data-testid="stBaseButton-primaryFormSubmit"] *,
    div[data-testid="stFormSubmitButton"] button *,
    div[data-testid="stFormSubmitButton"] button p,
    div[data-testid="stFormSubmitButton"] button span {
        color: #070a11 !important;
        fill: #070a11 !important;
        font-weight: 800 !important;
    }
    .stButton > button[kind="primary"]:hover *,
    .stButton > button[data-testid="stBaseButton-primary"]:hover *,
    button[data-testid="stBaseButton-primaryFormSubmit"]:hover *,
    div[data-testid="stFormSubmitButton"] button:hover *,
    div[data-testid="stFormSubmitButton"] button:hover p,
    div[data-testid="stFormSubmitButton"] button:hover span {
        color: #000000 !important;
        fill: #000000 !important;
    }
    .stButton > button[kind="primary"]:focus *,
    .stButton > button[kind="primary"]:active *,
    button[data-testid="stBaseButton-primaryFormSubmit"]:focus *,
    button[data-testid="stBaseButton-primaryFormSubmit"]:active *,
    div[data-testid="stFormSubmitButton"] button:focus *,
    div[data-testid="stFormSubmitButton"] button:active * {
        color: #000000 !important;
        fill: #000000 !important;
    }
    .stButton > button:hover {
        border-color: #00f5c4 !important;
        color: #00f5c4 !important;
        background-color: rgba(0, 245, 196, 0.08) !important;
        box-shadow: 0 0 12px rgba(0, 245, 196, 0.2) !important;
    }

    /* Daemon status button styling in sidebar */
    div.st-key-btn_daemon_toggle button {
        background: rgba(0, 245, 196, 0.12) !important;
        border: 1px solid rgba(0, 245, 196, 0.3) !important;
        color: #00f5c4 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11.5px !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
        padding: 8px 12px !important;
        border-radius: 8px !important;
        box-shadow: 0 0 10px rgba(0, 245, 196, 0.15) !important;
    }
    div.st-key-btn_daemon_toggle button:hover {
        background: rgba(0, 245, 196, 0.22) !important;
        border-color: #00f5c4 !important;
        box-shadow: 0 0 16px rgba(0, 245, 196, 0.4) !important;
        transform: scale(1.02) !important;
    }

    div.st-key-btn_daemon_toggle_idle button {
        background: rgba(100, 116, 139, 0.15) !important;
        border: 1px solid rgba(100, 116, 139, 0.35) !important;
        color: #cbd5e1 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11.5px !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
        padding: 8px 12px !important;
        border-radius: 8px !important;
    }
    div.st-key-btn_daemon_toggle_idle button:hover {
        background: rgba(0, 245, 196, 0.15) !important;
        border-color: #00f5c4 !important;
        color: #00f5c4 !important;
    }

    div.st-key-btn_open_config button, div.st-key-btn_open_help button {
        background: #141c2b !important;
        border: 1px solid #1f2d42 !important;
        color: #cbd5e1 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        padding: 6px 10px !important;
        border-radius: 6px !important;
    }
    div.st-key-btn_open_config button:hover {
        border-color: #00f5c4 !important;
        color: #00f5c4 !important;
        background: #1a2538 !important;
    }
    div.st-key-btn_open_help button:hover {
        border-color: #38bdf8 !important;
        color: #38bdf8 !important;
        background: #1a2538 !important;
    }

    /* ==========================================================================
       RESPONSIVE DESIGN & MEDIA QUERIES (Mobile, Tablet, Desktop)
       ========================================================================== */

    /* --- Responsive Header Banner System --- */
    .cognios-header-banner {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 22px;
        gap: 14px;
        flex-wrap: wrap;
    }
    .cognios-header-title {
        margin: 0 !important;
        font-size: 26px !important;
        font-weight: 800 !important;
        color: #ffffff !important;
        display: flex !important;
        align-items: center !important;
        gap: 10px !important;
        letter-spacing: -0.5px !important;
    }
    .cognios-header-sub {
        margin: 4px 0 0 0 !important;
        color: #64748b !important;
        font-size: 13px !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    .cognios-header-badges {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }
    .cognios-badge-pill {
        background: rgba(0, 245, 196, 0.1);
        color: #00f5c4;
        border: 1px solid rgba(0, 245, 196, 0.25);
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 11.5px;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 0 16px rgba(0, 245, 196, 0.15);
    }

    /* --- Responsive Horizontal Scroll Table Container --- */
    .cognios-table-container {
        width: 100%;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
        scrollbar-color: #1a273b rgba(10, 15, 25, 0.5);
        margin: 4px 0;
    }
    .cognios-table-container::-webkit-scrollbar {
        height: 6px;
    }
    .cognios-table-container::-webkit-scrollbar-track {
        background: rgba(10, 15, 25, 0.5);
        border-radius: 3px;
    }
    .cognios-table-container::-webkit-scrollbar-thumb {
        background: #1a273b;
        border-radius: 3px;
    }
    .cognios-table-container::-webkit-scrollbar-thumb:hover {
        background: #00f5c4;
    }

    /* --- Responsive Plotly Charts --- */
    div.js-plotly-plot, div.plot-container {
        width: 100% !important;
        max-width: 100% !important;
    }

    /* --- Card inner flex rows wrap instead of overflowing (value + badge, label rows) --- */
    .cognios-card > div {
        flex-wrap: wrap;
        gap: 6px;
    }

    /* All Streamlit columns can shrink below intrinsic content size */
    div[data-testid="stColumn"] {
        min-width: 0 !important;
    }

    /* Plotly charts fit container width dynamically */
    div.js-plotly-plot,
    div.plot-container,
    .plotly,
    svg.main-svg {
        max-width: 100% !important;
        width: 100% !important;
    }

    /* FocusOS & Metrics 4-quad grid */
    .cognios-metrics-quad {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
    }

    /* ==========================================================================
       CONTAINER QUERIES on main content block (reacts to sidebar open/close)
       ========================================================================== */
    div[data-testid="stMainBlockContainer"] {
        container-type: inline-size;
        container-name: cogmain;
    }

    /* At medium container width (< 980px): wrap 2-column, 3-column and 4-column blocks */
    @container cogmain (max-width: 980px) {
        /* 2-column major dashboard splits wrap onto stacked rows */
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(2):last-child) {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 16px !important;
        }
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(2):last-child) > div[data-testid="stColumn"] {
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }

        /* 3-column decks wrap into 2 + 1 */
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(3):last-child) {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 12px !important;
        }
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(3):last-child) > div[data-testid="stColumn"] {
            width: calc(50% - 8px) !important;
            min-width: calc(50% - 8px) !important;
            flex: 1 1 calc(50% - 8px) !important;
        }
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(3):last-child) > div[data-testid="stColumn"]:last-child {
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }

        /* 4-column KPI decks -> 2x2 grid */
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(4)) {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 12px !important;
        }
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(4)) > div[data-testid="stColumn"] {
            width: calc(50% - 8px) !important;
            min-width: calc(50% - 8px) !important;
            flex: 1 1 calc(50% - 8px) !important;
        }

        /* Keep nested horizontal blocks inside columns/forms/cards on a single row */
        div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"],
        div[data-testid="stForm"] div[data-testid="stHorizontalBlock"],
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            align-items: center !important;
            gap: 8px !important;
        }
        div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            width: auto !important;
            min-width: 0 !important;
            flex: 1 1 0% !important;
        }

        .cognios-metrics-quad {
            grid-template-columns: repeat(2, 1fr) !important;
        }
    }

    /* Narrow container width (< 680px): all top-level columns stack 100% */
    @container cogmain (max-width: 680px) {
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 12px !important;
        }
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }
        div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            width: auto !important;
            min-width: 0 !important;
            flex: 1 1 0% !important;
        }
        .cognios-metric-val { font-size: 24px !important; }
        .cognios-card { padding: 12px !important; }
    }

    /* ==========================================================================
       VIEWPORT MEDIA QUERIES (Window-Level Fallbacks & Global Typography)
       ========================================================================== */
    @media screen and (max-width: 1180px) {
        /* Fallback for 2-column major dashboard cards */
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(2):last-child) {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 16px !important;
        }
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(2):last-child) > div[data-testid="stColumn"] {
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }

        /* Fallback for 4-column KPI cards -> 2x2 */
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(4)) {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 12px !important;
        }
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(4)) > div[data-testid="stColumn"] {
            width: calc(50% - 8px) !important;
            min-width: calc(50% - 8px) !important;
            flex: 1 1 calc(50% - 8px) !important;
        }

        /* Fallback for 3-column subsystem cards */
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(3):last-child) {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 12px !important;
        }
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(3):last-child) > div[data-testid="stColumn"] {
            width: calc(50% - 8px) !important;
            min-width: calc(50% - 8px) !important;
            flex: 1 1 calc(50% - 8px) !important;
        }
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(3):last-child) > div[data-testid="stColumn"]:last-child {
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }

        /* Keep nested horizontal blocks inside columns/forms/cards on a single row */
        div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"],
        div[data-testid="stForm"] div[data-testid="stHorizontalBlock"],
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            align-items: center !important;
            gap: 8px !important;
        }
        div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            width: auto !important;
            min-width: 0 !important;
            flex: 1 1 0% !important;
        }

        .cognios-metrics-quad {
            grid-template-columns: repeat(2, 1fr) !important;
        }
    }

    @media screen and (max-width: 1024px) {
        div.block-container,
        div[data-testid="stMainBlockContainer"] {
            padding-left: 1.4rem !important;
            padding-right: 1.4rem !important;
        }
        .cognios-metric-val {
            font-size: 30px !important;
        }
    }

    @media screen and (max-width: 768px) {
        div.block-container,
        div[data-testid="stMainBlockContainer"] {
            padding-top: 3.8rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
            padding-bottom: 2rem !important;
        }

        .cognios-header-banner {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 10px !important;
            margin-bottom: 16px !important;
        }
        .cognios-header-title {
            font-size: 20px !important;
        }
        .cognios-header-sub {
            font-size: 11.5px !important;
        }
        .cognios-header-badges {
            width: 100% !important;
            justify-content: flex-start !important;
        }

        .cognios-card {
            padding: 14px !important;
            margin-bottom: 10px !important;
        }
        .cognios-metric-val {
            font-size: 26px !important;
        }

        .ai-response-container {
            padding: 14px !important;
            font-size: 12.5px !important;
            max-height: 240px !important;
        }

        .forensic-chain-container > div {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 4px !important;
            padding: 10px 12px !important;
        }

        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 12px !important;
        }
        div[data-testid="stMainBlockContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }
        div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            width: auto !important;
            min-width: 0 !important;
            flex: 1 1 0% !important;
        }
    }

    @media screen and (max-width: 480px) {
        div.block-container,
        div[data-testid="stMainBlockContainer"] {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            padding-top: 3.5rem !important;
        }
        .cognios-header-title {
            font-size: 18px !important;
        }
        .cognios-metric-val {
            font-size: 22px !important;
        }
        .cognios-metrics-quad {
            grid-template-columns: 1fr !important;
        }
    }
</style>
""", unsafe_allow_html=True)


def main():
    daemon_status = dp.get_daemon_status()

    if "active_dialog" not in st.session_state:
        st.session_state["active_dialog"] = None

    # Render active modal dialog if requested
    if st.session_state.get("active_dialog") == "config":
        render_config_dialog()
    elif st.session_state.get("active_dialog") == "help":
        render_help_dialog()

    # --- Sidebar Navigation ---
    with st.sidebar:
        st.html("""
            <div class="sidebar-brand-card">
                <div class="sidebar-logo-box">
                    <i class="fa-solid fa-terminal"></i>
                </div>
                <div>
                    <div class="sidebar-brand-title">CogniOS</div>
                    <div class="sidebar-brand-sub">
                        <span class="pulse-green"></span> DAEMON ONLINE
                    </div>
                </div>
            </div>
        """)

        if "current_page" not in st.session_state:
            st.session_state["current_page"] = "overview"

        # Section 1: Observability
        st.html('<div class="sidebar-category-header">OBSERVABILITY MATRIX</div>')

        obs_pages = [
            ("overview", "System Overview", ":material/dashboard:"),
            ("os_doctor", "OS Doctor AI", ":material/medical_services:"),
            ("focusos", "FocusOS Engine", ":material/visibility:"),
            ("blackbox", "BlackBox Recorder", ":material/inventory_2:")
        ]

        for p_id, p_title, p_icon in obs_pages:
            is_active = (st.session_state["current_page"] == p_id)
            btn_class = "nav-active" if is_active else ""
            st.markdown(f'<div class="{btn_class}">', unsafe_allow_html=True)
            if st.button(p_title, icon=p_icon, key=f"nav_{p_id}"):
                st.session_state["current_page"] = p_id
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Bottom System Status Card
        with st.container(border=True):
            if daemon_status["is_running"]:
                if st.button("● DAEMON RUNNING", key="btn_daemon_toggle", use_container_width=True, help="Daemon is actively running. Click to terminate."):
                    ok, msg = dp.stop_daemon_process()
                    if ok:
                        st.toast(msg, icon="🛑")
                    time.sleep(0.5)
                    st.rerun()
            else:
                if st.button("● SYSTEM IDLE (Click to Start)", key="btn_daemon_toggle_idle", use_container_width=True, help="Daemon is stopped. Click to launch background telemetry."):
                    ok, msg = dp.start_daemon_process()
                    if ok:
                        st.toast(msg, icon="🚀")
                    time.sleep(0.5)
                    st.rerun()

            st.html(f"""
                <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; font-family:'JetBrains Mono'; margin: 10px 0 12px 0; padding:0 4px;">
                    <span>PID: <strong style="color:#e2e8f0;">{daemon_status['pid'] or 'N/A'}</strong></span>
                    <span>MODE: <strong style="color:#00f5c4;">{daemon_status['db_mode']}</strong></span>
                </div>
            """)

            col_cfg, col_hlp = st.columns(2)
            with col_cfg:
                if st.button("Config", icon=":material/tune:", key="btn_open_config", use_container_width=True):
                    st.session_state["active_dialog"] = "config"
                    st.rerun()
            with col_hlp:
                if st.button("Help", icon=":material/help:", key="btn_open_help", use_container_width=True):
                    st.session_state["active_dialog"] = "help"
                    st.rerun()

    # --- Top Navigation Bar ---
    t1, t2 = st.columns([3, 1])

    with t1:
        st.html(f"""
            <div style="display:flex; gap:12px; align-items:center; margin-bottom: 16px;">
                <span class="top-status-pill"><i class="fa-solid fa-circle" style="color:#00f5c4; font-size:8px;"></i> Uptime: {daemon_status.get('uptime_str', 'N/A')}</span>
                <span class="top-status-pill"><i class="fa-solid fa-database" style="color:#38bdf8;"></i> DB: {daemon_status['db_mode']}</span>
                <span class="top-status-pill"><i class="fa-solid fa-bolt" style="color:#f59e0b;"></i> Latency: {daemon_status['latency_ms']}ms</span>
            </div>
        """)

    with t2:
        st.markdown('<div class="emergency-btn-box">', unsafe_allow_html=True)
        if st.button("Emergency Stop", key="emergency_stop", use_container_width=True):
            # Rollback any modified process priorities before killing daemons
            restored_count = 0
            try:
                from focusos.process_state import restore_all
                restored_count = restore_all()
            except Exception:
                pass

            killed_count = 0
            current_pid = os.getpid()
            for proc in psutil.process_iter():
                if proc.pid == current_pid:
                    continue
                try:
                    cmd = " ".join(proc.cmdline())
                    if any(target in cmd for target in ["cognios_as_daemon.py", "test.py", "i_forest_predict"]):
                        proc.kill()  # Cross-platform kill (Windows, macOS, Linux)
                        killed_count += 1
                except Exception:
                    pass

            # OS-Aware CLI Fallback
            try:
                if os.name == "nt":  # Windows
                    subprocess.run(["taskkill", "/F", "/FI", "COMMANDLINE eq *test.py*"], capture_output=True)
                    subprocess.run(["taskkill", "/F", "/FI", "COMMANDLINE eq *cognios_as_daemon.py*"], capture_output=True)
                else:  # macOS / Linux
                    subprocess.run(["pkill", "-9", "-f", "test.py"], capture_output=True)
                    subprocess.run(["pkill", "-9", "-f", "cognios_as_daemon.py"], capture_output=True)
            except Exception:
                pass

            restore_msg = f" and restored {restored_count} process priorities" if restored_count > 0 else ""
            st.success(f"🚨 EMERGENCY STOP ACTIVATED: Successfully terminated all active background telemetry & OS Doctor daemons{restore_msg}.")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Main Page Routing ---
    curr = st.session_state["current_page"]

    if curr == "overview":
        system_overview.render()
    elif curr == "os_doctor":
        os_doctor_view.render()
    elif curr == "focusos":
        focusos_view.render()
    elif curr == "blackbox":
        blackbox_view.render()

    # --- Non-blocking Auto Refresh (browser-side timer) ---
    # Only fire a full-page rerun for views that do NOT have @st.fragment(run_every=N).
    # Fragment-based views (overview, focusos, blackbox) self-refresh internally —
    # adding st_autorefresh on top causes a second, uncoordinated full-page rerun that
    # produces the visible "blink" effect every 2 seconds.
    FRAGMENT_VIEWS = {"overview", "os_doctor", "focusos", "blackbox"}
    if curr not in FRAGMENT_VIEWS and not st.session_state.get("active_dialog"):
        if HAS_AUTOREFRESH:
            refresh_interval_ms = int(getattr(config, 'AUTO_REFRESH', 2) * 1000)
            st_autorefresh(interval=refresh_interval_ms, key="dashboard_autorefresh")
        else:
            st.sidebar.warning("⚠️ `streamlit-autorefresh` missing. Run `pip install streamlit-autorefresh` for live updates.")


if __name__ == "__main__":
    main()
