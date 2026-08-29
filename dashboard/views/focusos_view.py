"""FocusOS Workload Optimization Engine View matching Stitch design."""

import re
import streamlit as st
import dashboard.data_provider as dp
import config



def render():
    workload_data = dp.get_focusos_detected_workload()
    affinity_data = dp.get_processor_affinity_matrix()
    events = dp.get_focusos_events()
    state = dp.get_latest_focusos_state()

    # --- Derive Active Optimizations from ACTUAL applied actions in DB ---
    # state["actions"] is the ground truth written by log_optimization_result()
    # after apply_optimization() ran — NOT assumed from the workload label.
    actions = state.get("actions", []) if state else []

    nice_val = "N/A"
    io_val   = "N/A"
    tc_val   = "OFF"

    for action in actions:
        a = action.lower()
        # Parse nice value: look for "nice" keyword followed by a number
        if "nice" in a:
            m = re.search(r"nice[:\s]+(-?\d+)", a)
            if m:
                nice_val = m.group(1)
            elif "prioriti" in a:
                # fallback: map workload to expected nice from optimisation.py constants
                wl = workload_data["workload"].lower().replace("_", " ")
                nice_map = {"compiling": "-12", "gaming": "-10",
                            "coding": "-5", "video call": "-5", "browsing": "0"}
                nice_val = nice_map.get(wl, "0")

        # Parse I/O class
        if "idle io" in a or "ionice" in a:
            if "idle" in a:
                io_val = "Idle IO (class 3)"
            elif "realtime" in a or "rt" in a:
                io_val = "Realtime (class 1)"
            else:
                io_val = "Best Effort (class 2)"
        elif "best effort" in a or "ioclass" in a:
            io_val = "Best Effort (class 2)"

        # Parse network queue state
        if "fq_codel" in a or "tc " in a or "network" in a:
            tc_val = "ON"

    # If daemon has never run, state is None — be explicit about it
    if not state:
        nice_val = "N/A (daemon not run)"
        io_val   = "N/A (daemon not run)"
        tc_val   = "N/A"


    # AI Diagnostics Explanation HTML
    llm_html = ""
    if state and state.get("explanation"):
        raw_exp = state["explanation"]

        # Strip legacy source prefixes written by older versions of llm_explainer
        # e.g. "[Gemma 4 API] ...", "[Template Fallback] ...", "[Gemini API] ..."
        source_match = re.match(r'^\[(.*?)\]\s*', raw_exp)
        source_label = source_match.group(1) if source_match else None
        exp_clean    = re.sub(r'^\[.*?\]\s*', '', raw_exp).strip()


        # Build source badge only if a known source was detected
        source_badge = ""
        if source_label:
            badge_color = {
                "Gemma 4": "#a78bfa",   # purple
                "Gemma 4 API": "#a78bfa",
                "Gemini": "#38bdf8",    # sky blue
                "Gemini API": "#38bdf8",
                "Template": "#64748b",  # grey
                "Template Fallback": "#64748b",
            }.get(source_label, "#64748b")
            source_badge = (
                f'<span style="font-size:10px; color:{badge_color}; border:1px solid {badge_color}; '
                f'border-radius:4px; padding:1px 7px; font-family:\'JetBrains Mono\'; '
                f'font-weight:700; margin-left:8px; vertical-align:middle;">'
                f'{source_label}</span>'
            )

        llm_html = (
            f'<div style="margin-top:24px; padding:16px; '
            f'background:linear-gradient(180deg, rgba(0,245,196,0.1) 0%, rgba(0,0,0,0.2) 100%); '
            f'border-left:3px solid #00f5c4; border-radius:6px;">'
            f'<div style="font-size:11px; font-weight:800; color:#00f5c4; text-transform:uppercase; '
            f'margin-bottom:8px; font-family:\'JetBrains Mono\';">'
            f'<i class="fa-solid fa-sparkles"></i> AI Diagnostics Explanation{source_badge}'
            f'</div>'
            f'<div style="font-size:13px; color:#e2e8f0; line-height:1.5;">{exp_clean}</div>'
            f'</div>'
        )


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

