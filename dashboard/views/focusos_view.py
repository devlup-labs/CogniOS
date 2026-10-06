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


@st.fragment(run_every=2)
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
    ml_confidence     = float(state.get("ml_confidence") or 0.0) if state else 0.0
    ml_workload       = str(state.get("ml_workload") or "IDLE") if state else "IDLE"
    live_sys          = dp.get_live_system_metrics()
    sys_cpu           = float(live_sys.get("cpu_pct", 0.0))
    sys_mem_mb        = float(live_sys.get("memory_used_gb", 0.0) * 1024)

    # --- Fingerprint guard: skip re-rendering heavy HTML if data hasn't changed ---
    # Round noisy floats to 1dp to avoid triggering re-renders on tiny fluctuations
    _fingerprint = (
        current_workload, current_state, consecutive_cycles,
        round(cpu_attr, 1), round(ram_attr, 1), round(score, 2),
        top_proc, round(sys_cpu, 1), ml_workload,
        len(events),
    )
    if st.session_state.get("_focusos_fp") == _fingerprint:
        return   # Nothing meaningful changed — skip the full DOM repaint (no blink)
    st.session_state["_focusos_fp"] = _fingerprint

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

    sim = dp.get_active_simulation()
    is_simulated = bool(sim)
    mode_badge_html = (
        '<div style="background:rgba(245,158,11,0.2); color:#f59e0b; border:1px solid #f59e0b; border-radius:6px; padding:6px 14px; font-size:12px; font-weight:700; font-family:\'JetBrains Mono\';">⚠️ SIMULATED (DEMO)</div>'
        if is_simulated else
        '<div style="background:rgba(0,245,196,0.15); color:#00f5c4; border:1px solid #00f5c4; border-radius:6px; padding:6px 14px; font-size:12px; font-weight:700; font-family:\'JetBrains Mono\';">● LIVE TELEMETRY</div>'
    )

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
            {mode_badge_html}
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
        # Format Evidence items gracefully with rich categorised cards
        evidence_html_items = ""
        for ev in (evidence_list or [])[:8]:
            if isinstance(ev, dict):
                proc = ev.get("process", top_proc)
                sig = ev.get("signal", str(ev))
                evidence_html_items += (
                    f'<div style="display:flex; justify-content:space-between; align-items:center; padding:8px 12px; '
                    f'background:rgba(255,255,255,0.02); border:1px solid #162030; border-radius:6px; margin-bottom:6px; font-family:\'JetBrains Mono\';">'
                    f'<div style="display:flex; align-items:center; gap:8px;">'
                    f'<span style="background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); border-radius:4px; padding:2px 6px; font-size:10px; font-weight:700;">SIMULATED</span>'
                    f'<span style="color:#ffffff; font-weight:700; font-size:12px;">{proc}</span>'
                    f'</div>'
                    f'<span style="color:#cbd5e1; font-size:11px;">{sig}</span>'
                    f'</div>'
                )
                continue

            text = str(ev).strip()

            # Process-level signals: e.g. "python (PID 15045) — CPU: 23.5%, RAM: 1420 MB"
            proc_match = re.match(r"^([a-zA-Z0-9_\-\.]+)\s*\(PID\s*(\d+)\)\s*—\s*CPU:\s*([0-9\.]+)%?,\s*RAM:\s*([0-9\.]+\s*[a-zA-Z]+)", text)
            if proc_match:
                p_name, pid, cpu_val, ram_val = proc_match.groups()
                cpu_float = float(cpu_val)
                num_cores = max(1, psutil.cpu_count() or 1)
                if cpu_float > 100.0:
                    cpu_float = round(cpu_float / num_cores, 1)
                cpu_display = f"{cpu_float:.1f}%"
                evidence_html_items += (
                    f'<div style="display:flex; justify-content:space-between; align-items:center; padding:8px 12px; '
                    f'background:rgba(255,255,255,0.015); border:1px solid #162030; border-radius:6px; margin-bottom:6px; font-family:\'JetBrains Mono\';">'
                    f'<div style="display:flex; align-items:center; gap:8px;">'
                    f'<span style="background:rgba(0,245,196,0.12); color:#00f5c4; border:1px solid rgba(0,245,196,0.25); border-radius:4px; padding:2px 6px; font-size:10px; font-weight:700;">PROCESS</span>'
                    f'<span style="color:#ffffff; font-weight:700; font-size:12px;">{p_name}</span>'
                    f'<span style="background:rgba(255,255,255,0.06); color:#94a3b8; font-size:10px; padding:1px 5px; border-radius:3px;">PID {pid}</span>'
                    f'</div>'
                    f'<div style="display:flex; align-items:center; gap:12px; font-size:11px;">'
                    f'<span style="color:#00f5c4; font-weight:600;"><i class="fa-solid fa-bolt" style="font-size:9px; margin-right:4px;"></i>{cpu_display} CPU</span>'
                    f'<span style="color:#38bdf8; font-weight:600;"><i class="fa-solid fa-memory" style="font-size:9px; margin-right:4px;"></i>{ram_val}</span>'
                    f'</div>'
                    f'</div>'
                )
                continue

            # Model telemetry: XGBoost
            if text.startswith("XGBoost"):
                is_override = "overridden" in text.lower()
                badge_color = "#f59e0b" if is_override else "#a78bfa"
                badge_bg = "rgba(245,158,11,0.15)" if is_override else "rgba(167,139,250,0.15)"
                badge_border = "rgba(245,158,11,0.3)" if is_override else "rgba(167,139,250,0.3)"
                tag = "AI TELEMETRY" if is_override else "AI CLASSIFIER"
                cleaned = text.replace('XGBoost Classifier: ', '').replace('XGBoost Network Signature: ', '')
                evidence_html_items += (
                    f'<div style="display:flex; justify-content:space-between; align-items:center; padding:8px 12px; '
                    f'background:rgba(255,255,255,0.015); border:1px solid #162030; border-radius:6px; margin-bottom:6px; font-family:\'JetBrains Mono\';">'
                    f'<div style="display:flex; align-items:center; gap:8px;">'
                    f'<span style="background:{badge_bg}; color:{badge_color}; border:1px solid {badge_border}; border-radius:4px; padding:2px 6px; font-size:10px; font-weight:700;">{tag}</span>'
                    f'<span style="color:#e2e8f0; font-size:12px;">{cleaned}</span>'
                    f'</div>'
                    f'<span style="color:{badge_color}; font-size:10px; font-weight:700; letter-spacing:0.5px;">XGBOOST</span>'
                    f'</div>'
                )
                continue

            # Aggregate attribution line
            if "attributed" in text:
                evidence_html_items += (
                    f'<div style="display:flex; justify-content:space-between; align-items:center; padding:8px 12px; '
                    f'background:rgba(0,245,196,0.03); border:1px solid rgba(0,245,196,0.15); border-radius:6px; margin-bottom:6px; font-family:\'JetBrains Mono\';">'
                    f'<div style="display:flex; align-items:center; gap:8px;">'
                    f'<span style="background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:4px; padding:2px 6px; font-size:10px; font-weight:700;">ATTRIBUTION</span>'
                    f'<span style="color:#ffffff; font-size:12px; font-weight:600;">{text}</span>'
                    f'</div>'
                    f'<span style="color:#00f5c4; font-size:11px; font-weight:700;">✓ COMPUTED</span>'
                    f'</div>'
                )
                continue

            # Temporal stability
            if "sustained" in text.lower() or "cycles" in text.lower():
                evidence_html_items += (
                    f'<div style="display:flex; justify-content:space-between; align-items:center; padding:8px 12px; '
                    f'background:rgba(56,189,248,0.03); border:1px solid rgba(56,189,248,0.15); border-radius:6px; margin-bottom:6px; font-family:\'JetBrains Mono\';">'
                    f'<div style="display:flex; align-items:center; gap:8px;">'
                    f'<span style="background:rgba(56,189,248,0.15); color:#38bdf8; border-radius:4px; padding:2px 6px; font-size:10px; font-weight:700;">STABILITY</span>'
                    f'<span style="color:#e2e8f0; font-size:12px;">{text}</span>'
                    f'</div>'
                    f'<span style="color:#38bdf8; font-size:11px; font-weight:700;">DEBOUNCED</span>'
                    f'</div>'
                )
                continue

            # CPU Contention
            if "contention" in text.lower():
                evidence_html_items += (
                    f'<div style="display:flex; justify-content:space-between; align-items:center; padding:8px 12px; '
                    f'background:rgba(245,158,11,0.04); border:1px solid rgba(245,158,11,0.2); border-radius:6px; margin-bottom:6px; font-family:\'JetBrains Mono\';">'
                    f'<div style="display:flex; align-items:center; gap:8px;">'
                    f'<span style="background:rgba(245,158,11,0.15); color:#f59e0b; border-radius:4px; padding:2px 6px; font-size:10px; font-weight:700;">CONTENTION</span>'
                    f'<span style="color:#fbbf24; font-size:12px;">{text}</span>'
                    f'</div>'
                    f'<span style="color:#f59e0b; font-size:11px; font-weight:700;">TRIGGER READY</span>'
                    f'</div>'
                )
                continue

            # Fallback item
            evidence_html_items += (
                f'<div style="display:flex; align-items:center; gap:8px; padding:8px 12px; '
                f'background:rgba(255,255,255,0.015); border:1px solid #162030; border-radius:6px; margin-bottom:6px; font-family:\'JetBrains Mono\'; font-size:12px; color:#cbd5e1;">'
                f'<span style="color:#00f5c4; font-weight:700;">✓</span>'
                f'<span>{text}</span>'
                f'</div>'
            )

        if not evidence_html_items:
            evidence_html_items = "<div style='font-size:12px; color:#64748b; font-style:italic; padding:12px;'>No active workload signals detected. System telemetry indicates baseline/idle activity.</div>"

        cpu_bar    = _pct_bar(cpu_attr, "#00f5c4")
        ram_bar    = _pct_bar(ram_attr, "#38bdf8")
        score_bar  = _pct_bar(score,    "#a78bfa")

        sig_count = len(evidence_list) if evidence_list else 0

        st.html(f"""
        <div style="background:#0d121c; border-radius:14px; padding:24px; min-height: 420px; box-shadow:0 6px 24px rgba(0,0,0,0.3); margin-bottom: 20px; border:1px solid #162030;">
            <!-- Header bar with icon and primary target -->
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; padding-bottom:16px; border-bottom:1px solid #162030;">
                <div style="display:flex; align-items:center; gap:14px;">
                    <div style="font-size:26px; width:48px; height:48px; border-radius:10px; background:#101725; border:1px solid #1a2638; display:flex; align-items:center; justify-content:center;">
                        {workload_icon}
                    </div>
                    <div>
                        <div style="display:flex; align-items:center; gap:8px;">
                            <h3 style="margin:0; font-size:22px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono';">{current_workload}</h3>
                            <span style="background:{state_badge_color}22; color:{state_badge_color}; border:1px solid {state_badge_color}55; border-radius:4px; padding:2px 8px; font-size:10px; font-weight:700; font-family:'JetBrains Mono';">● {current_state}</span>
                        </div>
                        <p style="margin:3px 0 0 0; font-size:12px; color:#64748b;">Dominant Workload Inference &amp; Real-Time Attribution</p>
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:10px; color:#94a3b8; font-family:'JetBrains Mono'; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Primary Target Process</div>
                    <div style="display:inline-flex; align-items:center; gap:6px; background:#101725; border:1px solid rgba(0,245,196,0.3); border-radius:6px; padding:4px 10px; margin-top:4px;">
                        <span style="color:#00f5c4; font-size:8px;">●</span>
                        <span style="font-size:13px; color:#00f5c4; font-family:'JetBrains Mono'; font-weight:700;">{top_proc}</span>
                    </div>
                </div>
            </div>

            <!-- Attribution Metrics Grid -->
            <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin-bottom:20px;">
                <div style="background:#101725; border:1px solid #162030; border-radius:10px; padding:16px; border-top:3px solid #00f5c4;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-family:'JetBrains Mono'; font-weight:600; letter-spacing:0.5px;">CPU Attribution</span>
                        <span style="color:#00f5c4; font-size:12px;"><i class="fa-solid fa-microchip"></i></span>
                    </div>
                    <div style="font-size:26px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono'; letter-spacing:-0.5px;">{cpu_attr:.0%}</div>
                    <div style="font-size:10px; color:#64748b; margin-top:2px; margin-bottom:8px;">Share of Active Host Load</div>
                    {cpu_bar}
                </div>
                <div style="background:#101725; border:1px solid #162030; border-radius:10px; padding:16px; border-top:3px solid #38bdf8;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-family:'JetBrains Mono'; font-weight:600; letter-spacing:0.5px;">RAM Attribution</span>
                        <span style="color:#38bdf8; font-size:12px;"><i class="fa-solid fa-memory"></i></span>
                    </div>
                    <div style="font-size:26px; font-weight:800; color:#38bdf8; font-family:'JetBrains Mono'; letter-spacing:-0.5px;">{ram_attr:.0%}</div>
                    <div style="font-size:10px; color:#64748b; margin-top:2px; margin-bottom:8px;">Share of Used Host RAM</div>
                    {ram_bar}
                </div>
                <div style="background:#101725; border:1px solid #162030; border-radius:10px; padding:16px; border-top:3px solid #a78bfa;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-family:'JetBrains Mono'; font-weight:600; letter-spacing:0.5px;">Inference Score</span>
                        <span style="color:#a78bfa; font-size:12px;"><i class="fa-solid fa-brain"></i></span>
                    </div>
                    <div style="font-size:26px; font-weight:800; color:#a78bfa; font-family:'JetBrains Mono'; letter-spacing:-0.5px;">{score:.3f}</div>
                    <div style="font-size:10px; color:#64748b; margin-top:2px; margin-bottom:8px;">{("XGBoost Confidence" if ml_confidence >= score and ml_confidence > 0 else "Rule Engine Score")}</div>
                    {score_bar}
                </div>
                <div style="background:#101725; border:1px solid #162030; border-radius:10px; padding:16px; border-top:3px solid #f59e0b;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-family:'JetBrains Mono'; font-weight:600; letter-spacing:0.5px;">System CPU</span>
                        <span style="color:#f59e0b; font-size:12px;"><i class="fa-solid fa-gauge-high"></i></span>
                    </div>
                    <div style="font-size:26px; font-weight:800; color:#f59e0b; font-family:'JetBrains Mono'; letter-spacing:-0.5px;">{sys_cpu:.1f}%</div>
                    <div style="font-size:10px; color:#64748b; margin-top:2px; margin-bottom:8px;">Host Machine Utilization</div>
                    {_pct_bar(sys_cpu / 100.0, "#f59e0b")}
                </div>
            </div>

            <!-- Evidence & Signals Panel -->
            <div style="background:#101725; border:1px solid #162030; border-radius:10px; padding:18px; margin-bottom:18px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="color:#00f5c4; font-size:13px;"><i class="fa-solid fa-bolt"></i></span>
                        <span style="font-size:11px; font-weight:700; color:#00f5c4; text-transform:uppercase; font-family:'JetBrains Mono'; letter-spacing:0.5px;">
                            Real-Time Attribution Evidence &amp; Process Signals
                        </span>
                    </div>
                    <span style="background:rgba(0,245,196,0.12); color:#00f5c4; border:1px solid rgba(0,245,196,0.25); border-radius:4px; padding:2px 8px; font-size:10px; font-weight:700; font-family:'JetBrains Mono';">
                        ● {sig_count} SIGNALS CORRELATED
                    </span>
                </div>
                <div style="max-height: 240px; overflow-y: auto; padding-right: 4px;">
                    {evidence_html_items}
                </div>
            </div>

            <!-- FocusOS Active Policy Details -->
            <div style="background:#101725; border:1px solid #162030; border-radius:10px; padding:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="color:#38bdf8;"><i class="fa-solid fa-shield-halved"></i></span>
                        <div style="font-size:11px; font-weight:700; color:#38bdf8; text-transform:uppercase; font-family:'JetBrains Mono';">
                            Active Governance Policy: {policy_info.get('description', current_workload)}
                        </div>
                    </div>
                    <div style="background:rgba(0,245,196,0.1); border:1px solid rgba(0,245,196,0.25); border-radius:4px; padding:2px 8px; font-size:10px; font-family:'JetBrains Mono'; color:#00f5c4; font-weight:700;">
                        I/O: {policy_info.get('io_priority', 'normal').upper()}
                    </div>
                </div>
                <div style="display:flex; gap:16px; font-size:12px; font-family:'JetBrains Mono'; color:#cbd5e1; margin-bottom:10px; background:rgba(255,255,255,0.02); padding:8px 12px; border-radius:6px; border:1px solid #162030;">
                    <span>Target Nice: <strong style="color:#00f5c4;">{policy_info.get('target_bucket_nice', 0)}</strong></span>
                    <span style="color:#475569;">•</span>
                    <span>Background Nice: <strong style="color:#f59e0b;">+{policy_info.get('background_nice', 0)}</strong></span>
                    <span style="color:#475569;">•</span>
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
                    from focusos.optimisation import apply_policy
                    conn = sqlite3.connect(DB_PATH, timeout=5.0)
                    actions = apply_policy(policy_info, state or {}, conn=conn)
                    conn.close()
                    if actions:
                        st.success(f"Applied FocusOS optimization policy for {current_workload} to {len(actions)} process(es)!")
                    else:
                        st.info(f"Policy evaluated for {current_workload}: No non-protected active processes required adjustments.")
                except Exception as e:
                    st.error(f"Error applying policy: {e}")

        with col_act2:
            if st.button("↺ Restore Default Priorities", use_container_width=True, key="focus_btn_restore"):
                try:
                    from focusos.optimisation import restore_workload_state
                    conn = sqlite3.connect(DB_PATH, timeout=5.0)
                    restored = restore_workload_state(conn=conn)
                    conn.close()
                    if restored > 0:
                        st.success(f"Restored {restored} process(es) to default scheduling priorities!")
                    else:
                        st.info("All processes are currently at default priority states.")
                except Exception as e:
                    st.error(f"Error restoring priorities: {e}")

    with col_opts:
        is_hybrid = affinity_data.get("is_hybrid", False)
        p_active = affinity_data.get("p_active", 8)
        e_active = affinity_data.get("e_active", 8)
        p_cores_set = set(affinity_data.get("p_cores", []))
        e_cores_set = set(affinity_data.get("e_cores", []))
        per_core = affinity_data.get("per_core_load", [])
        physical_cores = affinity_data.get("physical_cores") or 8
        arch_type = affinity_data.get("architecture_type") or "HOMOGENEOUS"
        cpu_model = affinity_data.get("model_name") or "Host CPU"

        # Live Top Processes table
        top_procs_html = f"""
        <div style='display:flex; justify-content:space-between; font-size:9px; font-weight:700; color:#64748b; text-transform:uppercase; border-bottom:1px solid #1e293b; padding-bottom:4px; margin-bottom:4px;'>
            <span style='width:35%;'>Process (PID)</span>
            <span style='width:15%; text-align:right;'>State</span>
            <span style='width:15%; text-align:right;'>Nice</span>
            <span style='width:15%; text-align:right;'>CPU</span>
            <span style='width:20%; text-align:right;'>RAM</span>
        </div>
        """
        try:
            procs = dp.get_top_processes_list(limit=6)
            num_cores = max(1, psutil.cpu_count() or 1)
            for p in (procs or []):
                raw_cpu = float(p.get("cpu_normalized") if p.get("cpu_normalized") is not None else (p.get("cpu") or 0.0))
                cpu_p = round(raw_cpu / num_cores if raw_cpu > 100.0 else raw_cpu, 1)
                p_name = str(p.get("name") or "proc")[:14]
                pid = p.get("pid", "")
                nice = p.get("nice", 0)
                status = str(p.get("status", "run"))[:3].upper()
                mem_p = float(p.get("ram") or 0.0)
                rss_str = str(p.get("rss_human") or f"{mem_p:.1f}%")
                
                # Highlight negative nice (high priority) and positive nice (low priority)
                nice_color = "#f59e0b" if nice > 0 else ("#00f5c4" if nice < 0 else "#64748b")
                
                top_procs_html += (
                    f"<div style='display:flex; justify-content:space-between; font-size:11px; "
                    f"color:#cbd5e1; padding:6px 0; border-bottom:1px solid #101725;'>"
                    f"<span style='font-family:JetBrains Mono; color:#e2e8f0; width:35%; overflow:hidden; text-overflow:ellipsis;'>{p_name} <span style='color:#64748b; font-size:9px;'>{pid}</span></span>"
                    f"<span style='color:#94a3b8; font-family:JetBrains Mono; font-size:10px; width:15%; text-align:right;'>{status}</span>"
                    f"<span style='color:{nice_color}; font-family:JetBrains Mono; width:15%; text-align:right;'>{nice}</span>"
                    f"<span style='color:#00f5c4; font-family:JetBrains Mono; width:15%; text-align:right;'>{cpu_p:.1f}%</span>"
                    f"<span style='color:#38bdf8; font-family:JetBrains Mono; width:20%; text-align:right;'>{rss_str}</span></div>"
                )
        except Exception:
            top_procs_html += "<div style='font-size:11px; color:#64748b;'>Telemetry initializing...</div>"

        if not procs:
            top_procs_html += "<div style='font-size:11px; color:#64748b; font-style:italic;'>No active processes detected.</div>"

        # Interactive Matrix HTML Grid
        core_tiles_html = ""
        total_cores = len(per_core) if per_core else (affinity_data.get("total_cores") or 16)
        for c_idx in range(total_cores):
            c_val = per_core[c_idx] if c_idx < len(per_core) else 0.0
            if is_hybrid:
                is_p = c_idx in p_cores_set
                c_type = "P" if is_p else "E"
                c_color = "#00f5c4" if is_p else "#a78bfa"
            else:
                c_type = "T"
                c_color = "#00f5c4"

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

        if is_hybrid:
            summary_cards_html = f"""
            <div style="flex:1; background:#131b28; border-radius:8px; padding:12px; border-left:3px solid #00f5c4;">
                <div style="font-size:10px; color:#94a3b8; margin-bottom:2px;">P-Cores (Perf)</div>
                <div style="font-size:18px; font-weight:700; color:#00f5c4; font-family:'JetBrains Mono';">{p_active} Cores</div>
            </div>
            <div style="flex:1; background:#131b28; border-radius:8px; padding:12px; border-left:3px solid #a78bfa;">
                <div style="font-size:10px; color:#94a3b8; margin-bottom:2px;">E-Cores (Eff)</div>
                <div style="font-size:18px; font-weight:700; color:#a78bfa; font-family:'JetBrains Mono';">{e_active} Cores</div>
            </div>
            """
        else:
            summary_cards_html = f"""
            <div style="flex:1; background:#131b28; border-radius:8px; padding:12px; border-left:3px solid #00f5c4;">
                <div style="font-size:10px; color:#94a3b8; margin-bottom:2px;">Physical Cores</div>
                <div style="font-size:18px; font-weight:700; color:#00f5c4; font-family:'JetBrains Mono';">{physical_cores} Cores ({total_cores}T)</div>
            </div>
            <div style="flex:1; background:#131b28; border-radius:8px; padding:12px; border-left:3px solid #38bdf8;">
                <div style="font-size:10px; color:#94a3b8; margin-bottom:2px;">Architecture</div>
                <div style="font-size:13px; font-weight:700; color:#38bdf8; font-family:'JetBrains Mono'; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{cpu_model}">{cpu_model}</div>
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
                    {physical_cores} Physical • {total_cores} Logical
                </div>
            </div>

            <!-- Core Allocation Summary -->
            <div style="display:flex; gap:10px; margin-bottom:16px;">
                {summary_cards_html}
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
                    <span style="width:45%;">PROCESS</span><span style="width:25%; text-align:right;">CPU (1C=100%)</span><span style="width:30%; text-align:right;">RAM (RSS)</span>
                </div>
                {top_procs_html}
            </div>
        </div>
        """)

    # Bottom Event Log — Upgraded High-Density Observability Console
    event_rows_html = ""
    shown = 0
    for ev in (events or []):
        ts = ev.get('time', 'Just now')
        p_name = ev.get('process_name') or "System"
        pid = ev.get('pid')
        workload = str(ev.get('workload') or 'SYSTEM').upper()
        act = str(ev.get('action') or '')
        old_v = str(ev.get('old_value') or '')
        new_v = str(ev.get('new_value') or '')
        reason = str(ev.get('reason') or '')
        success = ev.get('success', True)
        
        # If legacy message string exists without structured fields
        if p_name == "System" and ev.get('message') and not reason:
            reason = ev.get('message')

        # Workload badge style
        wl_badge_style = {
            "CODING": ("💻", "rgba(0,245,196,0.12)", "#00f5c4"),
            "BROWSING": ("🌐", "rgba(56,189,248,0.12)", "#38bdf8"),
            "VIDEO_CALL": ("📹", "rgba(167,139,250,0.12)", "#a78bfa"),
            "COMPILATION": ("⚙️", "rgba(245,158,11,0.12)", "#f59e0b"),
            "GAMING": ("🎮", "rgba(236,72,153,0.12)", "#ec4899"),
            "MEDIA_PROCESSING": ("🎬", "rgba(244,63,94,0.12)", "#f43f5e"),
            "RESTORE_ALL": ("↺", "rgba(56,189,248,0.12)", "#38bdf8"),
        }.get(workload, ("📊", "rgba(148,163,184,0.12)", "#94a3b8"))
        
        # Action badge style
        if "restore" in act.lower() or "restore" in workload.lower():
            act_badge = '<span style="background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.3); border-radius:4px; padding:2px 8px; font-weight:700; font-size:11px;">↺ RESTORED</span>'
        elif "nice" in act.lower():
            try:
                new_nice_int = int(new_v)
                old_nice_int = int(old_v)
                if new_nice_int < old_nice_int:
                    act_badge = f'<span style="background:rgba(0,245,196,0.15); color:#00f5c4; border:1px solid rgba(0,245,196,0.3); border-radius:4px; padding:2px 8px; font-weight:700; font-size:11px;">nice {old_nice_int} → {new_nice_int} (Boost)</span>'
                else:
                    act_badge = f'<span style="background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); border-radius:4px; padding:2px 8px; font-weight:700; font-size:11px;">nice {old_nice_int} → +{new_nice_int} (Depress)</span>'
            except Exception:
                act_badge = f'<span style="background:rgba(245,158,11,0.15); color:#f59e0b; border-radius:4px; padding:2px 8px; font-weight:700; font-size:11px;">{act} [{old_v}→{new_v}]</span>'
        else:
            act_badge = f'<span style="background:rgba(148,163,184,0.15); color:#cbd5e1; border-radius:4px; padding:2px 8px; font-weight:700; font-size:11px;">{act or "EXEC"}</span>'

        status_icon = '<span style="color:#00f5c4; font-weight:700; margin-right:6px;">✓</span>' if success else '<span style="color:#ef4444; font-weight:700; margin-right:6px;">✕</span>'
        pid_display = f'<span style="background:rgba(255,255,255,0.06); color:#94a3b8; font-size:10px; padding:1px 5px; border-radius:3px; margin-left:6px; font-weight:500;">PID {pid}</span>' if pid and pid != 0 else ''
        row_bg = 'rgba(255,255,255,0.015)' if shown % 2 == 0 else 'transparent'

        event_rows_html += f"""
        <div style="display:grid; grid-template-columns: 85px 190px 140px 190px 1fr; align-items:center; gap:12px; padding:9px 14px;
                    border-bottom:1px solid #141d2b; font-family:'JetBrains Mono'; font-size:12px; background:{row_bg}; border-radius:4px;">
            <span style="color:#64748b; font-size:11px;">{ts}</span>
            <div style="display:flex; align-items:center; overflow:hidden;">
                <span style="color:#ffffff; font-weight:700; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">{p_name}</span>
                {pid_display}
            </div>
            <div>
                <span style="background:{wl_badge_style[1]}; color:{wl_badge_style[2]}; border-radius:4px; padding:2px 7px; font-size:11px; font-weight:700; display:inline-flex; align-items:center; gap:4px;">
                    <span>{wl_badge_style[0]}</span> <span>{workload}</span>
                </span>
            </div>
            <div>{act_badge}</div>
            <div style="color:#cbd5e1; font-size:11px; display:flex; align-items:center; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                {status_icon}
                <span style="overflow:hidden; text-overflow:ellipsis;" title="{reason}">{reason}</span>
            </div>
        </div>
        """
        shown += 1

    if shown == 0:
        event_rows_html = f"""
        <div style="display:flex; align-items:center; justify-content:space-between; padding:20px; background:#101725; border-radius:8px; border:1px dashed #1a2638; font-family:'JetBrains Mono';">
            <div style="display:flex; align-items:center; gap:12px;">
                <span style="background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:4px; padding:3px 10px; font-weight:700; font-size:11px;">● STANDBY</span>
                <span style="color:#94a3b8; font-size:12px;">Autonomous FocusOS Daemon observing — automatic scheduling triggers when workload is CONFIRMED and CPU contention > 35%.</span>
            </div>
            <span style="color:#64748b; font-size:11px;">{time.strftime("%H:%M:%S")}</span>
        </div>
        """
    else:
        # Wrap with column header and scrollable container
        event_rows_html = f"""
        <div style="display:grid; grid-template-columns: 85px 190px 140px 190px 1fr; gap:12px; padding:8px 14px; background:#101725; border-radius:6px; margin-bottom:8px; font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase; font-family:'JetBrains Mono'; letter-spacing:0.5px;">
            <span>Time</span>
            <span>Target Process</span>
            <span>Workload</span>
            <span>Policy Action</span>
            <span>Rationale / Outcome</span>
        </div>
        <div style="max-height: 420px; overflow-y: auto; padding-right: 2px;">
            {event_rows_html}
        </div>
        """

    st.html(f"""
    <div style="background:#0d121c; border-radius:14px; padding:24px; margin-top:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3); border:1px solid #162030;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="color:#00f5c4; font-size:16px;"><i class="fa-solid fa-clock-rotate-left"></i></span>
                <div>
                    <h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Kernel Optimization &amp; Scheduling Log</h3>
                    <p style="margin:2px 0 0 0; font-size:11px; color:#64748b;">Audited Linux process niceness, CPU affinity, and I/O scheduling adjustments</p>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:rgba(0,245,196,0.12); color:#00f5c4; border:1px solid rgba(0,245,196,0.25); border-radius:4px; padding:3px 10px; font-size:11px; font-weight:700; font-family:'JetBrains Mono';">● LIVE AUDIT</span>
                <span style="font-size:11px; color:#64748b; font-family:'JetBrains Mono';">Showing last {shown} events</span>
            </div>
        </div>
        {event_rows_html}
    </div>
    """)
