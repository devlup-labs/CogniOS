"""FocusOS Deterministic Rule Engine Dashboard View."""

import re
import streamlit as st
import dashboard.data_provider as dp
import psutil


def _pct_bar(value: float, color: str = "#00f5c4") -> str:
    """Render a compact inline progress bar."""
    pct = max(0.0, min(1.0, value))
    return (
        f'<div style="background:#0a0f1a; border-radius:4px; height:8px; margin-top:6px;">'
        f'<div style="background:{color}; width:{pct*100:.1f}%; height:100%; border-radius:4px;"></div>'
        f'</div>'
    )


def render():
    workload_data = dp.get_focusos_detected_workload()
    affinity_data = dp.get_processor_affinity_matrix()
    events = dp.get_focusos_events()
    state = dp.get_latest_focusos_state()

    current_workload = workload_data.get("workload", "IDLE")
    current_state    = workload_data.get("state", "IDLE")
    cpu_attr         = workload_data.get("cpu_attribution", 0.0)
    ram_attr         = workload_data.get("ram_attribution", 0.0)
    score            = workload_data.get("score", 0.0)

    top_proc          = state.get("top_process", "N/A") if state else "N/A"
    evidence_list     = state.get("evidence", []) if state else []
    consecutive_cycles = state.get("consecutive_cycles", 0) if state else 0
    sys_cpu           = state.get("system_cpu", psutil.cpu_percent(interval=0.1)) if state else psutil.cpu_percent(interval=0.1)
    sys_mem_mb        = state.get("system_memory", 0.0) if state else 0.0

    state_badge_color = {
        "CONFIRMED":  "#00f5c4",
        "OPTIMIZED":  "#10b981",
        "OBSERVING":  "#38bdf8",
        "RESTORING":  "#f59e0b",
        "IDLE":       "#64748b",
        "UNKNOWN":    "#a78bfa",
    }.get(current_state, "#64748b")

    workload_icon = {
        "BROWSING":         "🌐",
        "COMPILATION":      "⚙️",
        "CODING":           "💻",
        "VIDEO_CALL":       "📹",
        "GAMING":           "🎮",
        "MEDIA_PROCESSING": "🎬",
        "IDLE":             "💤",
        "UNKNOWN":          "🔍",
    }.get(current_workload, "📊")

    # Header
    st.html("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
        <div>
            <h1 style="margin:0; font-size: 28px; font-weight: 800; color: #ffffff; display:flex; align-items:center; gap:10px;">
                <span style="color:#00f5c4;"><i class="fa-solid fa-scale-balanced"></i></span>
                Rule-Based Resource Attribution Engine
            </h1>
            <p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px; font-family: 'JetBrains Mono';">
                FocusOS Daemon // Deterministic Process Attribution &amp; Safety Guard
            </p>
        </div>
    </div>
    """)

    col_target, col_opts = st.columns([2, 1])

    with col_target:
        # Evidence HTML
        evidence_html_items = ""
        for ev in evidence_list[:6]:
            evidence_html_items += (
                f"<div style='font-size:12px; color:#cbd5e1; margin-bottom:5px; display:flex; align-items:flex-start; gap:6px;'>"
                f"<span style='color:#00f5c4; margin-top:2px;'>✓</span><span>{ev}</span></div>"
            )
        if not evidence_html_items:
            evidence_html_items = "<div style='font-size:12px; color:#64748b; font-style:italic;'>No active workload signals detected. System appears idle or unclassified.</div>"

        cpu_bar    = _pct_bar(cpu_attr, "#00f5c4")
        ram_bar    = _pct_bar(ram_attr, "#38bdf8")
        score_bar  = _pct_bar(score,    "#a78bfa")

        st.html(f"""
        <div style="background:#0d121c; border-radius:14px; padding:24px; min-height: 400px; box-shadow:0 6px 24px rgba(0,0,0,0.3);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;">
                <div>
                    <h3 style="margin:0; font-size:20px; font-weight:700; color:#ffffff;">
                        {workload_icon} {current_workload}
                    </h3>
                    <p style="margin:2px 0 0 0; font-size:12px; color:#64748b;">Deterministic process-to-workload attribution</p>
                </div>
                <div style="background: rgba(0,0,0,0.3); color:{state_badge_color};
                            border:1px solid {state_badge_color}; border-radius:6px;
                            padding:6px 14px; font-size:12px; font-weight:700; font-family:'JetBrains Mono';">
                    ● {current_state}
                </div>
            </div>

            <!-- Attribution Metrics -->
            <div style="display:flex; gap:14px; margin-bottom:20px;">
                <div style="flex:1; background:#131b28; border-radius:8px; padding:16px; border-top:2px solid #00f5c4;">
                    <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; margin-bottom:4px;">CPU Attribution</div>
                    <div style="font-size:24px; font-weight:700; color:#ffffff; font-family:'JetBrains Mono';">{cpu_attr:.0%}</div>
                    {cpu_bar}
                </div>
                <div style="flex:1; background:#131b28; border-radius:8px; padding:16px; border-top:2px solid #38bdf8;">
                    <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; margin-bottom:4px;">RAM Attribution</div>
                    <div style="font-size:24px; font-weight:700; color:#38bdf8; font-family:'JetBrains Mono';">{ram_attr:.0%}</div>
                    {ram_bar}
                </div>
                <div style="flex:1; background:#131b28; border-radius:8px; padding:16px; border-top:2px solid #a78bfa;">
                    <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; margin-bottom:4px;">Dominance Score</div>
                    <div style="font-size:24px; font-weight:700; color:#a78bfa; font-family:'JetBrains Mono';">{score:.3f}</div>
                    {score_bar}
                </div>
                <div style="flex:1; background:#131b28; border-radius:8px; padding:16px; border-top:2px solid #f59e0b;">
                    <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; margin-bottom:4px;">System CPU</div>
                    <div style="font-size:24px; font-weight:700; color:#f59e0b; font-family:'JetBrains Mono';">{sys_cpu:.1f}%</div>
                    {_pct_bar(sys_cpu / 100.0, "#f59e0b")}
                </div>
            </div>

            <!-- Evidence Panel -->
            <div style="background:#131b28; border-radius:8px; padding:16px;">
                <div style="font-size:11px; font-weight:700; color:#00f5c4; text-transform:uppercase;
                            font-family:'JetBrains Mono'; margin-bottom:10px; letter-spacing:0.5px;">
                    ⚡ Attribution Evidence &amp; Process Signals ({consecutive_cycles} persistent cycles)
                </div>
                {evidence_html_items}
            </div>
        </div>
        """)

    with col_opts:
        p_active = affinity_data.get("p_active", 0)
        e_active = affinity_data.get("e_active", 0)

        # Show live top processes from psutil as a direct fallback
        top_procs_html = ""
        try:
            procs = sorted(
                [p.info for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"])
                 if p.info.get("cpu_percent", 0) > 0.5],
                key=lambda x: x.get("cpu_percent", 0),
                reverse=True
            )[:5]
            for p in procs:
                cpu_p = p.get("cpu_percent", 0.0)
                mem_p = p.get("memory_percent", 0.0)
                top_procs_html += (
                    f"<div style='display:flex; justify-content:space-between; font-size:11px; "
                    f"color:#cbd5e1; padding:4px 0; border-bottom:1px solid #0d121c;'>"
                    f"<span style='font-family:JetBrains Mono; color:#e2e8f0;'>{p['name'][:18]}</span>"
                    f"<span style='color:#00f5c4;'>{cpu_p:.1f}%</span>"
                    f"<span style='color:#38bdf8;'>{mem_p:.1f}%</span></div>"
                )
        except Exception:
            top_procs_html = "<div style='font-size:11px; color:#64748b;'>N/A</div>"

        st.html(f"""
        <div style="background:#0d121c; border-radius:14px; padding:24px; min-height:400px; box-shadow:0 6px 24px rgba(0,0,0,0.3);">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:16px;">
                <span style="color:#94a3b8;"><i class="fa-solid fa-microchip"></i></span>
                <h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Core Allocation</h3>
            </div>

            <div style="background:#131b28; border-radius:8px; padding:14px; margin-bottom:10px;">
                <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; margin-bottom:4px;">Primary Process</div>
                <div style="font-size:14px; font-weight:700; color:#ffffff; font-family:'JetBrains Mono';">{top_proc}</div>
            </div>

            <div style="display:flex; gap:10px; margin-bottom:16px;">
                <div style="flex:1; background:#131b28; border-radius:8px; padding:12px;">
                    <div style="font-size:10px; color:#94a3b8; margin-bottom:2px;">P-Cores</div>
                    <div style="font-size:16px; font-weight:700; color:#00f5c4; font-family:'JetBrains Mono';">{p_active}</div>
                </div>
                <div style="flex:1; background:#131b28; border-radius:8px; padding:12px;">
                    <div style="font-size:10px; color:#94a3b8; margin-bottom:2px;">E-Cores</div>
                    <div style="font-size:16px; font-weight:700; color:#a78bfa; font-family:'JetBrains Mono';">{e_active}</div>
                </div>
            </div>

            <!-- Live Top Processes -->
            <div style="background:#131b28; border-radius:8px; padding:14px;">
                <div style="font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase;
                            font-family:'JetBrains Mono'; margin-bottom:8px; display:flex; justify-content:space-between;">
                    <span>Process</span><span>CPU</span><span>MEM</span>
                </div>
                {top_procs_html}
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

    shown = 0
    for ev in (events or []):
        badge_bg = "rgba(0,245,196,0.12)"  if ev["type"] == "SCHED" else "rgba(56,189,248,0.12)"
        badge_fg = "#00f5c4"               if ev["type"] == "SCHED" else "#38bdf8"
        st.html(f"""
        <div style="display:flex; align-items:flex-start; gap:16px; padding:10px 0;
                    border-bottom:1px solid #131b28; font-family:'JetBrains Mono'; font-size:12px;">
            <span style="color:#64748b; white-space:nowrap;">{ev['time']}</span>
            <span style="background:{badge_bg}; color:{badge_fg}; border-radius:4px;
                        padding:2px 8px; font-weight:700; font-size:11px; white-space:nowrap;">[{ev['type']}]</span>
            <span style="color:#e2e8f0; word-break:break-word;">{ev['message']}</span>
        </div>
        """)
        shown += 1

    if shown == 0:
        st.html("<div style='font-size:13px; color:#64748b; font-style:italic; padding:12px 0;'>No optimization events yet. Daemon is observing — policy actions fire when workload is CONFIRMED and CPU contention exceeds threshold.</div>")

    st.html("</div>")
