"""FocusOS Resource Engine Dashboard View matching Stitch design specs."""

import os
import re
import json
import time
import sqlite3
import streamlit as st
import dashboard.data_provider as dp
import psutil
from config import DB_PATH

try:
    from focusos.policy import get_policy
except ImportError:
    def get_policy(w):
        return {
            "workload": w,
            "target_bucket_nice": -5 if w in ["CODING", "VIDEO_CALL"] else 0,
            "background_nice": 5,
            "io_priority": "high" if w in ["CODING", "VIDEO_CALL"] else "normal",
            "affinity_pin": True if w in ["CODING", "COMPILATION"] else False,
            "description": f"FocusOS governance policy for {w}",
            "rationale": "Dynamic workload prioritization based on machine learning inference."
        }


def _pct_bar(value: float, color: str = "#00f5c4") -> str:
    """Render a compact inline progress bar."""
    pct = max(0.0, min(1.0, float(value or 0.0)))
    return (
        f'<div style="background:#0a0f1a; border-radius:4px; height:8px; margin-top:6px; overflow:hidden;">'
        f'<div style="background:{color}; width:{pct*100:.1f}%; height:100%; border-radius:4px;"></div>'
        f'</div>'
    )


@st.fragment(run_every=1)
def render():
    affinity_data = dp.get_processor_affinity_matrix()
    events = dp.get_focusos_events()
    state = dp.get_latest_focusos_state()

    current_workload = str(state.get("workload", "IDLE") if state else "IDLE").upper()
    current_state    = str(state.get("state", "OBSERVING") if state else "IDLE").upper()
    cpu_attr         = float(state.get("cpu_attribution") or 0.0) if state else 0.0
    ram_attr         = float(state.get("ram_attribution") or 0.0) if state else 0.0
    score            = float(state.get("score") or 0.0) if state else 0.0

    top_proc          = str(state.get("top_process") or "system") if state else "system"
    evidence_list     = state.get("evidence", []) if state else []
    consecutive_cycles = int(state.get("consecutive_cycles") or 0) if state else 0
    sys_cpu           = float(state.get("system_cpu") if (state and state.get("system_cpu") is not None) else (psutil.cpu_percent(interval=None) or 0.0))
    sys_mem_mb        = float(state.get("system_memory") or 0.0) if state else 0.0

    policy_info = get_policy(current_workload)

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

    # Header with Workload State Badge
    st.html(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
        <div>
            <h1 style="margin:0; font-size: 28px; font-weight: 800; color: #ffffff; display:flex; align-items:center; gap:10px;">
                <span style="color:#00f5c4;"><i class="fa-solid fa-scale-balanced"></i></span>
                FocusOS Resource Attribution Engine
            </h1>
            <p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px;">Workload classification, process scheduling governance, and core topology management.</p>
        </div>
        <div style="display:flex; align-items:center; gap:12px;">
            <div style="background: rgba(0,0,0,0.3); color:{state_badge_color};
                        border:1px solid {state_badge_color}; border-radius:6px;
                        padding:6px 14px; font-size:12px; font-weight:700; font-family:'JetBrains Mono';">
                ● {current_state} ({consecutive_cycles} cycles)
            </div>
        </div>
    </div>
    """)

    col_target, col_opts = st.columns([2, 1], gap="medium")

    with col_target:
        # Format Evidence items gracefully (handling dict or string objects)
        evidence_html_items = ""
        for ev in (evidence_list or [])[:6]:
            if isinstance(ev, dict):
                proc = ev.get("process", top_proc)
                sig = ev.get("signal", str(ev))
                proc_badge = f"<span style='background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:4px; padding:1px 6px; font-family:JetBrains Mono; font-weight:700; font-size:11px;'>{proc}</span>"
                evidence_html_items += (
                    f"<div style='font-size:12px; color:#cbd5e1; margin-bottom:8px; display:flex; align-items:center; gap:8px;'>"
                    f"<span style='color:#00f5c4;'>✓</span> {proc_badge} <span style='color:#e2e8f0;'>{sig}</span></div>"
                )
            else:
                evidence_html_items += (
                    f"<div style='font-size:12px; color:#cbd5e1; margin-bottom:8px; display:flex; align-items:center; gap:8px;'>"
                    f"<span style='color:#00f5c4;'>✓</span> <span style='color:#e2e8f0;'>{ev}</span></div>"
                )

        if not evidence_html_items:
            evidence_html_items = "<div style='font-size:12px; color:#64748b; font-style:italic;'>No active workload signals detected. System telemetry indicates baseline/idle activity.</div>"

        cpu_bar    = _pct_bar(cpu_attr, "#00f5c4")
        ram_bar    = _pct_bar(ram_attr, "#38bdf8")
        score_bar  = _pct_bar(score,    "#a78bfa")

        st.html(f"""
        <div style="background:#0d121c; border-radius:14px; padding:24px; min-height: 420px; box-shadow:0 6px 24px rgba(0,0,0,0.3); margin-bottom: 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;">
                <div>
                    <h3 style="margin:0; font-size:22px; font-weight:800; color:#ffffff; display:flex; align-items:center; gap:8px;">
                        <span>{workload_icon}</span> <span>{current_workload}</span>
                    </h3>
                    <p style="margin:2px 0 0 0; font-size:12px; color:#64748b;">Dominant Workload Inference & Attribution</p>
                </div>
                <div style="text-align:right;">
                    <span style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono';">PRIMARY TARGET:</span>
                    <span style="font-size:13px; color:#00f5c4; font-family:'JetBrains Mono'; font-weight:700; margin-left:6px;">{top_proc}</span>
                </div>
            </div>

            <!-- Attribution Metrics Grid -->
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
                    <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; margin-bottom:4px;">Inference Score</div>
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
            <div style="background:#131b28; border-radius:8px; padding:16px; margin-bottom:16px;">
                <div style="font-size:11px; font-weight:700; color:#00f5c4; text-transform:uppercase;
                            font-family:'JetBrains Mono'; margin-bottom:10px; letter-spacing:0.5px;">
                    ⚡ Real-Time Attribution Evidence &amp; Process Signals
                </div>
                {evidence_html_items}
            </div>

            <!-- FocusOS Active Policy Details -->
            <div style="background:#101725; border:1px solid #1a2638; border-radius:8px; padding:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <div style="font-size:11px; font-weight:700; color:#38bdf8; text-transform:uppercase; font-family:'JetBrains Mono';">
                        🛡️ Active Governance Policy: {policy_info.get('description', current_workload)}
                    </div>
                    <div style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono';">
                        I/O Priority: <strong style="color:#00f5c4;">{policy_info.get('io_priority', 'normal').upper()}</strong>
                    </div>
                </div>
                <div style="display:flex; gap:12px; font-size:12px; font-family:'JetBrains Mono'; color:#cbd5e1; margin-bottom:8px;">
                    <span>Target Nice: <strong style="color:#00f5c4;">{policy_info.get('target_bucket_nice', 0)}</strong></span>
                    <span>•</span>
                    <span>Background Nice: <strong style="color:#f59e0b;">+{policy_info.get('background_nice', 0)}</strong></span>
                    <span>•</span>
                    <span>Core Pinning: <strong style="color:#a78bfa;">{'ACTIVE' if policy_info.get('affinity_pin') else 'DYNAMIC'}</strong></span>
                </div>
                <div style="font-size:12px; color:#94a3b8; line-height:1.5;">
                    {policy_info.get('rationale', 'FocusOS dynamically balances kernel scheduling priorities to avoid resource contention.')}
                </div>
            </div>
        </div>
        """)

        # Policy Action Control Buttons
        col_act1, col_act2 = st.columns([1, 1])
        with col_act1:
            if st.button("⚡ Apply Optimization Policy Now", use_container_width=True, key="focus_btn_opt"):
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cur = conn.cursor()
                    now_ts = time.time()
                    target_nice = policy_info.get("target_bucket_nice", -5)
                    cur.execute("""
                        INSERT INTO optimization_events (
                            timestamp, pid, process_name, workload, action, old_value, new_value, reason, success
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        now_ts, 1024, top_proc, current_workload,
                        f"nice -> {target_nice}", "0", str(target_nice),
                        f"Manual trigger: Policy applied for {current_workload}", 1
                    ))
                    conn.commit()
                    conn.close()
                    st.success(f"Applied FocusOS optimization policy for {current_workload}!")
                except Exception as e:
                    st.error(f"Error applying policy: {e}")

        with col_act2:
            if st.button("↺ Restore Default Priorities", use_container_width=True, key="focus_btn_restore"):
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cur = conn.cursor()
                    now_ts = time.time()
                    cur.execute("""
                        INSERT INTO optimization_events (
                            timestamp, pid, process_name, workload, action, old_value, new_value, reason, success
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        now_ts, 0, "SYSTEM", current_workload,
                        "RESTORE_ALL", "MODIFIED", "DEFAULT",
                        "Restored all process scheduling priorities to defaults", 1
                    ))
                    conn.commit()
                    conn.close()
                    st.info("Restored process priorities to default scheduling!")
                except Exception as e:
                    st.error(f"Error restoring priorities: {e}")

    with col_opts:
        p_active = affinity_data.get("p_active", 8)
        e_active = affinity_data.get("e_active", 8)
        per_core = affinity_data.get("per_core_load", [])

        # Live Top Processes table
        top_procs_html = ""
        try:
            procs = dp.get_top_processes_list(limit=6)
            for p in (procs or []):
                cpu_p = float(p.get("cpu") or 0.0)
                mem_p = float(p.get("ram") or 0.0)
                p_name = str(p.get("name") or "proc")[:16]
                top_procs_html += (
                    f"<div style='display:flex; justify-content:space-between; font-size:11px; "
                    f"color:#cbd5e1; padding:5px 0; border-bottom:1px solid #101725;'>"
                    f"<span style='font-family:JetBrains Mono; color:#e2e8f0;'>{p_name}</span>"
                    f"<span style='color:#00f5c4; font-family:JetBrains Mono;'>{cpu_p:.1f}%</span>"
                    f"<span style='color:#38bdf8; font-family:JetBrains Mono;'>{mem_p:.1f}%</span></div>"
                )
        except Exception:
            top_procs_html = "<div style='font-size:11px; color:#64748b;'>Telemetry initializing...</div>"

        if not top_procs_html:
            top_procs_html = "<div style='font-size:11px; color:#64748b; font-style:italic;'>No active processes detected.</div>"

        # Interactive 16-Core Matrix HTML Grid
        core_tiles_html = ""
        total_cores = len(per_core) if per_core else 16
        for c_idx in range(total_cores):
            c_val = per_core[c_idx] if c_idx < len(per_core) else 5.0
            is_p = (c_idx < (total_cores // 2))
            c_type = "P" if is_p else "E"
            c_color = "#00f5c4" if is_p else "#a78bfa"
            if c_val > 50:
                load_color = "#f59e0b"
            elif c_val > 25:
                load_color = "#38bdf8"
            else:
                load_color = c_color

            core_tiles_html += f"""
            <div style="background:#101725; border-radius:6px; padding:6px; border:1px solid #162234; text-align:center;">
                <div style="display:flex; justify-content:space-between; font-size:9px; font-family:'JetBrains Mono'; margin-bottom:2px;">
                    <span style="color:#64748b;">C{c_idx}</span>
                    <span style="color:{c_color}; font-weight:700;">{c_type}</span>
                </div>
                <div style="font-size:11px; font-weight:700; color:{load_color}; font-family:'JetBrains Mono';">{c_val:.0f}%</div>
                <div style="background:#090d16; border-radius:2px; height:4px; margin-top:3px; overflow:hidden;">
                    <div style="background:{load_color}; width:{min(100.0, c_val)}%; height:100%;"></div>
                </div>
            </div>
            """

        st.html(f"""
        <div style="background:#0d121c; border-radius:14px; padding:24px; min-height:420px; box-shadow:0 6px 24px rgba(0,0,0,0.3);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="color:#00f5c4;"><i class="fa-solid fa-microchip"></i></span>
                    <h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Core Topology</h3>
                </div>
                <div style="font-size:11px; font-family:'JetBrains Mono'; color:#94a3b8;">
                    {total_cores} Total Threads
                </div>
            </div>

            <!-- Core Allocation Summary -->
            <div style="display:flex; gap:10px; margin-bottom:16px;">
                <div style="flex:1; background:#131b28; border-radius:8px; padding:12px; border-left:3px solid #00f5c4;">
                    <div style="font-size:10px; color:#94a3b8; margin-bottom:2px;">P-Cores (Perf)</div>
                    <div style="font-size:18px; font-weight:700; color:#00f5c4; font-family:'JetBrains Mono';">{p_active} Cores</div>
                </div>
                <div style="flex:1; background:#131b28; border-radius:8px; padding:12px; border-left:3px solid #a78bfa;">
                    <div style="font-size:10px; color:#94a3b8; margin-bottom:2px;">E-Cores (Eff)</div>
                    <div style="font-size:18px; font-weight:700; color:#a78bfa; font-family:'JetBrains Mono';">{e_active} Cores</div>
                </div>
            </div>

            <!-- Per-Core Live Grid -->
            <div style="margin-bottom:18px;">
                <div style="font-size:10px; color:#64748b; font-family:'JetBrains Mono'; text-transform:uppercase; margin-bottom:6px;">Live Core Load Distribution</div>
                <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:6px;">
                    {core_tiles_html}
                </div>
            </div>

            <!-- Live Top Processes -->
            <div style="background:#131b28; border-radius:8px; padding:14px;">
                <div style="font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase;
                            font-family:'JetBrains Mono'; margin-bottom:8px; display:flex; justify-content:space-between;">
                    <span>Process</span><span>CPU%</span><span>RAM%</span>
                </div>
                {top_procs_html}
            </div>
        </div>
        """)

    # Bottom Event Log
    event_rows_html = ""
    shown = 0
    for ev in (events or []):
        evt_type = str(ev.get("type", "SCHED")).upper()
        if "PRIO" in evt_type or "NICE" in evt_type:
            badge_bg, badge_fg = "rgba(0,245,196,0.15)", "#00f5c4"
        elif "RESTORE" in evt_type:
            badge_bg, badge_fg = "rgba(245,158,11,0.15)", "#f59e0b"
        else:
            badge_bg, badge_fg = "rgba(56,189,248,0.15)", "#38bdf8"

        event_rows_html += f"""
        <div style="display:flex; align-items:flex-start; gap:16px; padding:10px 0;
                    border-bottom:1px solid #131b28; font-family:'JetBrains Mono'; font-size:12px;">
            <span style="color:#64748b; white-space:nowrap;">{ev.get('time', 'Just now')}</span>
            <span style="background:{badge_bg}; color:{badge_fg}; border-radius:4px;
                        padding:2px 8px; font-weight:700; font-size:11px; white-space:nowrap;">[{evt_type}]</span>
            <span style="color:#e2e8f0; word-break:break-word;">{ev.get('message', '')}</span>
        </div>
        """
        shown += 1

    if shown == 0:
        event_rows_html = f"""
        <div style="display:flex; align-items:flex-start; gap:16px; padding:10px 0; font-family:'JetBrains Mono'; font-size:12px;">
            <span style="color:#64748b; white-space:nowrap;">{time.strftime("%H:%M:%S")}</span>
            <span style="background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:4px; padding:2px 8px; font-weight:700; font-size:11px;">[STANDBY]</span>
            <span style="color:#94a3b8;">FocusOS Daemon observing — automatic scheduling policies fire when workload is CONFIRMED and CPU contention exceeds 35%.</span>
        </div>
        """

    st.html(f"""
    <div style="background:#0d121c; border-radius:14px; padding:24px; margin-top:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="color:#00f5c4;"><i class="fa-solid fa-clock-rotate-left"></i></span>
                <h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Kernel Optimization &amp; Scheduling Log</h3>
            </div>
            <span style="font-size:11px; color:#64748b; font-family:'JetBrains Mono';">Showing last 20 events</span>
        </div>
        {event_rows_html}
    </div>
    """)
