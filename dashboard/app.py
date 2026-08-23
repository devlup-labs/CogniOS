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

import dashboard.data_provider as dp
from dashboard.views import system_overview, focusos_view, blackbox_view, os_doctor_view, research_view
import config

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

    header[data-testid="stHeader"] {
        background: transparent !important;
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
        border: none !important;
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
        background: #0d121c !important;
        color: #94a3b8 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        text-align: left !important;
        width: 100% !important;
        margin-bottom: 6px !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 14px rgba(0,0,0,0.2) !important;
    }

    section[data-testid="stSidebar"] div.stButton > button:hover {
        background: #141c2b !important;
        color: #ffffff !important;
        border: none !important;
        transform: translateX(4px) !important;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35) !important;
    }

    /* Active Nav Item Highlighting */
    .nav-active div.stButton > button {
        background: linear-gradient(90deg, rgba(0, 245, 196, 0.18) 0%, rgba(0, 245, 196, 0.02) 100%) !important;
        color: #00f5c4 !important;
        border: none !important;
        border-left: 4px solid #00f5c4 !important;
        box-shadow: 0 0 20px rgba(0, 245, 196, 0.2) !important;
        font-weight: 700 !important;
    }

    .nav-active div.stButton > button span {
        color: #00f5c4 !important;
    }

    /* --- GLOBAL STREAMLIT MAIN CONTENT BUTTONS STYLING --- */
    div.stButton > button {
        background: #101725 !important;
        color: #e2e8f0 !important;
        border: 1px solid #1a2638 !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
    }

    div.stButton > button:hover {
        background: #172236 !important;
        color: #00f5c4 !important;
        border-color: #00f5c4 !important;
        box-shadow: 0 0 16px rgba(0, 245, 196, 0.35) !important;
        transform: translateY(-1px) !important;
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
    .sidebar-status-card {
        background: #0d121c;
        border: none !important;
        border-radius: 12px;
        padding: 16px;
        margin-top: 24px;
        box-shadow: 0 6px 24px rgba(0,0,0,0.3);
    }

    .top-status-pill {
        background: #0d121c;
        border: none !important;
        border-radius: 8px;
        padding: 7px 16px;
        font-size: 12px;
        font-family: 'JetBrains Mono', monospace;
        color: #cbd5e1;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    }

    .cognios-card {
        background: #0d121c;
        border: none !important;
        border-radius: 14px;
        padding: 22px;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
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
</style>
""", unsafe_allow_html=True)


def main():
    daemon_status = dp.get_daemon_status()

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
            ("focusos", "FocusOS Engine", ":material/visibility:"),
            ("blackbox", "BlackBox Recorder", ":material/inventory_2:"),
            ("os_doctor", "OS Doctor AI", ":material/medical_services:")
        ]

        for p_id, p_title, p_icon in obs_pages:
            is_active = (st.session_state["current_page"] == p_id)
            btn_class = "nav-active" if is_active else ""
            st.markdown(f'<div class="{btn_class}">', unsafe_allow_html=True)
            if st.button(p_title, icon=p_icon, key=f"nav_{p_id}"):
                st.session_state["current_page"] = p_id
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # Section 2: Research
        st.html('<div class="sidebar-category-header" style="margin-top:22px;">EXPERIMENTATION</div>')
        is_active = (st.session_state["current_page"] == "research")
        btn_class = "nav-active" if is_active else ""
        st.markdown(f'<div class="{btn_class}">', unsafe_allow_html=True)
        if st.button("Research Engine", icon=":material/science:", key="nav_research"):
            st.session_state["current_page"] = "research"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Bottom System Status Card
        status_bg = "rgba(0, 245, 196, 0.12)" if daemon_status["is_running"] else "rgba(100, 116, 139, 0.15)"
        status_fg = "#00f5c4" if daemon_status["is_running"] else "#cbd5e1"
        status_txt = "● DAEMON RUNNING" if daemon_status["is_running"] else "● SYSTEM IDLE"

        st.html(f"""
            <div class="sidebar-status-card">
                <div style="background:{status_bg}; color:{status_fg}; padding:8px 12px; border-radius:8px; text-align:center; font-weight:800; font-size:12px; font-family:'JetBrains Mono'; margin-bottom:12px; letter-spacing:0.5px;">
                    {status_txt}
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; font-family:'JetBrains Mono'; margin-bottom:14px; padding:0 4px;">
                    <span>PID: <strong style="color:#e2e8f0;">{daemon_status['pid'] or 'N/A'}</strong></span>
                    <span>MODE: <strong style="color:#00f5c4;">{daemon_status['db_mode']}</strong></span>
                </div>
                <div style="display:flex; gap:8px;">
                    <button style="flex:1; background:#141c2b; border:none; color:#cbd5e1; border-radius:6px; padding:7px; font-size:11px; font-weight:600; font-family:'JetBrains Mono'; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:5px;">
                        <i class="fa-solid fa-sliders" style="color:#00f5c4;"></i> Config
                    </button>
                    <button style="flex:1; background:#141c2b; border:none; color:#cbd5e1; border-radius:6px; padding:7px; font-size:11px; font-weight:600; font-family:'JetBrains Mono'; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:5px;">
                        <i class="fa-solid fa-headset" style="color:#38bdf8;"></i> Help
                    </button>
                </div>
            </div>
        """)

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

            st.success(f"🚨 EMERGENCY STOP ACTIVATED: Successfully terminated all active background telemetry & OS Doctor daemons.")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Main Page Routing ---
    curr = st.session_state["current_page"]

    if curr == "overview":
        system_overview.render()
    elif curr == "focusos":
        focusos_view.render()
    elif curr == "blackbox":
        blackbox_view.render()
    elif curr == "os_doctor":
        os_doctor_view.render()
    elif curr == "research":
        research_view.render()

    # --- Non-blocking Auto Refresh (browser-side timer) ---
    if HAS_AUTOREFRESH:
        refresh_interval_ms = int(getattr(config, 'AUTO_REFRESH', 2) * 1000)
        st_autorefresh(interval=refresh_interval_ms, key="dashboard_autorefresh")
    else:
        st.sidebar.warning("⚠️ `streamlit-autorefresh` missing. Run `pip install streamlit-autorefresh` for live updates.")


if __name__ == "__main__":
    main()
