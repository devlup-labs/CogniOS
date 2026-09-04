"""FocusOS Deterministic Rule Engine Dashboard View."""

import re
import streamlit as st
import dashboard.data_provider as dp


def render():
    workload_data = dp.get_focusos_detected_workload()
    affinity_data = dp.get_processor_affinity_matrix()
    events = dp.get_focusos_events()
    state = dp.get_latest_focusos_state()

    current_workload = workload_data.get("workload", "IDLE")
    current_state = workload_data.get("state", "IDLE")
    cpu_attr = workload_data.get("cpu_attribution", 0.0)
    ram_attr = workload_data.get("ram_attribution", 0.0)
    score = workload_data.get("score", 0.0)

    top_proc = state.get("top_process", "N/A") if state else "N/A"
    evidence_list = state.get("evidence", []) if state else []
    consecutive_cycles = state.get("consecutive_cycles", 0) if state else 0

    state_badge_color = {
        "CONFIRMED": "#00f5c4",
        "OPTIMIZED": "#10b981",
        "OBSERVING": "#38bdf8",
        "RESTORING": "#f59e0b",
        "IDLE": "#64748b",
    }.get(current_state, "#64748b")

    # Header
    st.html("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
        <div>
            <h1 style="margin:0; font-size: 28px; font-weight: 800; color: #ffffff; display:flex; align-items:center; gap:10px;">
                <span style="color:#00f5c4;"><i class="fa-solid fa-scale-balanced"></i></span> Rule-Based Resource Attribution Engine
            </h1>
            <p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px; font-family: 'JetBrains Mono';">
                FocusOS Daemon // Deterministic Process Attribution & Safety Guard
            </p>
        </div>
    </div>
    """)

    col_target, col_opts = st.columns([2, 1])

    with col_target:
        # Rule Engine Evidence HTML
        evidence_html_items = ""
        for ev in evidence_list[:5]:
            evidence_html_items += f"<div style='font-size:12px; color:#cbd5e1; margin-bottom:4px;'><i class='fa-solid fa-check' style='color:#00f5c4; margin-right:6px;'></i> {ev}</div>"
        
        if not evidence_html_items:
            evidence_html_items = "<div style='font-size:12px; color:#64748b;'>No active resource contention detected.</div>"

        st.html(f"""
        <div style="background:#0d121c; border-radius:14px; padding:24px; min-height: 380px; box-shadow:0 6px 24px rgba(0,0,0,0.3);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <div>
                    <h3 style="margin:0; font-size:20px; font-weight:700; color:#ffffff;">Attributed Workload</h3>
                    <p style="margin:2px 0 0 0; font-size:12px; color:#64748b;">Deterministic process-to-workload attribution</p>
                </div>
                <div style="background: rgba(0, 245, 196, 0.12); color:{state_badge_color}; border-radius:6px; padding:6px 14px; font-size:12px; font-weight:700; font-family:'JetBrains Mono';">
                    ● STATE: {current_state} ({current_workload})
                </div>
            </div>

            <!-- Metrics Grid -->
            <div style="display:flex; gap: 16px; margin-top:16px; margin-bottom: 20px;">
                <div style="flex: 1; background: #131b28; border-radius: 8px; padding: 16px; border-top: 2px solid #00f5c4;">
                    <div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase;">CPU Attribution</div>
                    <div style="font-size: 22px; font-weight: 700; color: #ffffff; font-family: 'JetBrains Mono';">{cpu_attr:.0%}</div>
                </div>
                <div style="flex: 1; background: #131b28; border-radius: 8px; padding: 16px; border-top: 2px solid #38bdf8;">
                    <div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase;">RAM Attribution</div>
                    <div style="font-size: 22px; font-weight: 700; color: #38bdf8; font-family: 'JetBrains Mono';">{ram_attr:.0%}</div>
                </div>
                <div style="flex: 1; background: #131b28; border-radius: 8px; padding: 16px; border-top: 2px solid #a78bfa;">
                    <div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase;">Dominance Score</div>
                    <div style="font-size: 22px; font-weight: 700; color: #a78bfa; font-family: 'JetBrains Mono';">{score:.2f}</div>
                </div>
            </div>

            <!-- Process Signals & Evidence -->
            <div style="background:#131b28; border-radius:8px; padding:16px;">
                <div style="font-size:11px; font-weight:700; color:#00f5c4; text-transform:uppercase; font-family:'JetBrains Mono'; margin-bottom:8px;">
                    Attribution Evidence & Process Signals ({consecutive_cycles} persistent cycles)
                </div>
                {evidence_html_items}
            </div>
        </div>
        """)

    with col_opts:
        p_active = affinity_data.get("p_active", 0)
        e_active = affinity_data.get("e_active", 0)

        st.html(f"""
        <div style="background:#0d121c; border-radius:14px; padding:24px; min-height: 380px; box-shadow:0 6px 24px rgba(0,0,0,0.3);">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:20px;">
                <span style="color:#94a3b8;"><i class="fa-solid fa-gears"></i></span>
                <h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Core Allocation & Guard</h3>
            </div>
            
            <div style="background:#131b28; border-radius:8px; padding:14px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-size:12px; color:#94a3b8;">Primary Process</div>
                    <div style="font-size:15px; font-weight:700; color:#ffffff; font-family:'JetBrains Mono'; margin-top:2px;">{top_proc}</div>
                </div>
                <div style="background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:bold;">
                    <i class="fa-solid fa-check"></i>
                </div>
            </div>

            <div style="background:#131b28; border-radius:8px; padding:14px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-size:12px; color:#94a3b8;">Foreground P-Cores</div>
                    <div style="font-size:15px; font-weight:700; color:#ffffff; font-family:'JetBrains Mono'; margin-top:2px;">{p_active} Cores Active</div>
                </div>
                <div style="background:rgba(56,189,248,0.15); color:#38bdf8; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:bold;">
                    <i class="fa-solid fa-microchip"></i>
                </div>
            </div>

            <div style="background:#131b28; border-radius:8px; padding:14px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-size:12px; color:#94a3b8;">Background E-Cores</div>
                    <div style="font-size:15px; font-weight:700; color:#ffffff; font-family:'JetBrains Mono'; margin-top:2px;">{e_active} Cores Active</div>
                </div>
                <div style="background:rgba(167,139,250,0.15); color:#a78bfa; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:bold;">
                    <i class="fa-solid fa-leaf"></i>
                </div>
            </div>
        </div>
        """)

    # Bottom Event Log
    st.html("""
    <div style="background:#0d121c; border-radius:14px; padding:24px; margin-top:24px; box-shadow:0 6px 24px rgba(0,0,0,0.3);">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:16px;">
            <span style="color:#94a3b8;"><i class="fa-solid fa-clock-rotate-left"></i></span>
            <h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Deterministic Optimization Event Log</h3>
        </div>
    """)

    for ev in (events or []):
        badge_bg = "rgba(0,245,196,0.12)" if ev['type'] == "SCHED" else "rgba(56,189,248,0.12)"
        badge_fg = "#00f5c4" if ev['type'] == "SCHED" else "#38bdf8"

        st.html(f"""
        <div style="display:flex; align-items:center; gap:16px; padding:10px 0; border-bottom:1px solid #131b28; font-family:'JetBrains Mono'; font-size:13px;">
            <span style="color:#64748b;">{ev['time']}</span>
            <span style="background:{badge_bg}; color:{badge_fg}; border-radius:4px; padding:2px 8px; font-weight:700; font-size:11px;">[{ev['type']}]</span>
            <span style="color:#e2e8f0;">{ev['message']}</span>
        </div>
        """)

    st.html("</div>")
