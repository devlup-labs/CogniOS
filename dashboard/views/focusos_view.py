"""FocusOS Workload Optimization Engine View matching Stitch design."""

import streamlit as st
import dashboard.data_provider as dp


def render():
    workload_data = dp.get_focusos_detected_workload()
    affinity_data = dp.get_processor_affinity_matrix()
    events = dp.get_focusos_events()
    state = dp.get_latest_focusos_state()

    # Determine dynamic active optimizations based on workload
    w_clean = workload_data["workload"].lower().replace("_", " ")
    
    nice_val = "0"
    io_val = "Best Effort (b7)"
    tc_val = "OFF"
    
    if w_clean == "compiling":
        nice_val = "-12"
        io_val = "Idle IO (background)"
    elif w_clean == "gaming":
        nice_val = "-10"
        io_val = "Best Effort (b1)"
    elif w_clean == "coding":
        nice_val = "-5"
        io_val = "Best Effort (b7)"
    elif w_clean == "video call":
        nice_val = "-5"
        tc_val = "ON"
        io_val = "Best Effort (b7)"
    elif w_clean == "browsing":
        nice_val = "0"
        io_val = "Idle IO (background)"

    # AI Diagnostics Explanation HTML
    llm_html = ""
    if state and state.get("explanation"):
        exp = state["explanation"]
        llm_html = f"""<div style="margin-top:24px; padding:16px; background:linear-gradient(180deg, rgba(0, 245, 196, 0.1) 0%, rgba(0, 0, 0, 0.2) 100%); border-left:3px solid #00f5c4; border-radius:6px;"><div style="font-size:11px; font-weight:800; color:#00f5c4; text-transform:uppercase; margin-bottom:8px; font-family:'JetBrains Mono';"><i class="fa-solid fa-sparkles"></i> AI Diagnostics Explanation</div><div style="font-size:13px; color:#e2e8f0; line-height:1.5;">{exp}</div></div>"""

    # Model Inference UI
    w_detected = workload_data['workload']
    w_conf = workload_data['confidence']
    
    inference_html = f"""
    <div style="margin-top:16px; margin-bottom: 24px;">
        <div style="font-size:12px; font-weight:700; color:#64748b; font-family:'JetBrains Mono'; text-transform:uppercase; margin-bottom:12px;">Model Inference</div>
        <div style="display:flex; gap: 16px;">
            <div style="flex: 1; background: #131b28; border-radius: 8px; padding: 16px; border-top: 2px solid #3b82f6;">
                <div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase;">Detected Workload</div>
                <div style="font-size: 18px; font-weight: 700; color: #ffffff; font-family: 'JetBrains Mono';">{w_detected}</div>
            </div>
            <div style="flex: 1; background: #131b28; border-radius: 8px; padding: 16px; border-top: 2px solid #10b981;">
                <div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase;">Confidence Score</div>
                <div style="font-size: 18px; font-weight: 700; color: #10b981; font-family: 'JetBrains Mono';">{w_conf}%</div>
            </div>
        </div>
    </div>
    """

    st.html(f"""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;"><div><h1 style="margin:0; font-size: 28px; font-weight: 800; color: #ffffff; display:flex; align-items:center; gap:10px;"><span style="color:#00f5c4;"><i class="fa-solid fa-eye"></i></span> Workload Optimization Engine</h1><p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px; font-family: 'JetBrains Mono';">FocusOS Daemon // Process Affinity & Scheduling Control</p></div></div>""")

    col_target, col_opts = st.columns([2, 1])

    with col_target:
        st.html(f"""<div style="background:#0d121c; border-radius:14px; padding:24px; min-height: 380px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;"><div><h3 style="margin:0; font-size:20px; font-weight:700; color:#ffffff;">Target Workload</h3><p style="margin:2px 0 0 0; font-size:12px; color:#64748b;">Real-time resource allocation</p></div><div style="background: rgba(0, 245, 196, 0.12); color:#00f5c4; border-radius:6px; padding:6px 14px; font-size:12px; font-weight:700; font-family:\'JetBrains Mono\';">● ACTIVE STATE: {workload_data['workload']} ({workload_data['confidence']}% CONF)</div></div>{inference_html}{llm_html}</div>""")

    with col_opts:
        st.html(f"""<div style="background:#0d121c; border-radius:14px; padding:24px; min-height: 380px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; align-items:center; gap:8px; margin-bottom:20px;"><span style="color:#94a3b8;"><i class="fa-solid fa-gears"></i></span><h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Active Optimizations</h3></div><div style="background:#131b28; border-radius:8px; padding:14px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;"><div><div style="font-size:12px; color:#94a3b8;">CPU Scheduler</div><div style="font-size:15px; font-weight:700; color:#ffffff; font-family:\'JetBrains Mono\'; margin-top:2px;">nice: {nice_val}</div></div><div style="background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:bold;"><i class="fa-solid fa-check"></i></div></div><div style="background:#131b28; border-radius:8px; padding:14px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;"><div><div style="font-size:12px; color:#94a3b8;">I/O Priority</div><div style="font-size:15px; font-weight:700; color:#ffffff; font-family:\'JetBrains Mono\'; margin-top:2px;">ionice: {io_val}</div></div><div style="background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:bold;"><i class="fa-solid fa-check"></i></div></div><div style="background:#131b28; border-radius:8px; padding:14px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;"><div><div style="font-size:12px; color:#94a3b8;">Network Queue</div><div style="font-size:15px; font-weight:700; color:#ffffff; font-family:\'JetBrains Mono\'; margin-top:2px;">tc fq_codel: {tc_val}</div></div><div style="background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:bold;"><i class="fa-solid fa-check"></i></div></div></div>""")
        if st.button("Override Settings", key="override_settings_btn", use_container_width=True):
            st.info("Override settings panel opened.")

    # Bottom Event Log
    st.html("""<div style="background:#0d121c; border-radius:14px; padding:24px; margin-top:24px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; align-items:center; gap:8px; margin-bottom:16px;"><span style="color:#94a3b8;"><i class="fa-solid fa-clock-rotate-left"></i></span><h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Optimization Event Log</h3></div>""")

    for ev in (events or []):
        badge_bg = "rgba(0,245,196,0.12)" if ev['type'] == "SCHED" else ("rgba(56,189,248,0.12)" if ev['type'] == "PRIO" else "rgba(245,158,11,0.12)")
        badge_fg = "#00f5c4" if ev['type'] == "SCHED" else ("#38bdf8" if ev['type'] == "PRIO" else "#f59e0b")

        st.html(f"""<div style="display:flex; align-items:center; gap:16px; padding:10px 0; border-bottom:1px solid #131b28; font-family:\'JetBrains Mono\'; font-size:13px;"><span style="color:#64748b;">{ev['time']}</span><span style="background:{badge_bg}; color:{badge_fg}; border-radius:4px; padding:2px 8px; font-weight:700; font-size:11px;">[{ev['type']}]</span><span style="color:#e2e8f0;">{ev['message']}</span></div>""")

    st.html("</div>")

