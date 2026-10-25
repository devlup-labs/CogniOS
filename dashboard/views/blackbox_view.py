"""BlackBox System Flight Recorder View matching CogniOS Stitch design."""

import os
import time
import pandas as pd
import streamlit as st
import dashboard.data_provider as dp
import config

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


def _on_scrub_preset(offset_minutes: int):
    st.session_state["bb_scrub_val"] = offset_minutes


@st.fragment(run_every=2)
def render():
    # Enhanced CSS for better UI
    st.markdown("""
        <style>
        /* Button styling */
        div[data-testid="stButton"] button[kind="secondary"] {
            background: linear-gradient(180deg, #101726 0%, #0a0f19 100%) !important;
            color: #e2e8f0 !important;
            border: 1px solid rgba(255, 255, 255, 0.14) !important;
            border-radius: 8px !important;
            transition: all 0.2s ease;
        }
        div[data-testid="stButton"] button[kind="secondary"] * {
            color: inherit !important;
        }
        div[data-testid="stButton"] button[kind="secondary"]:hover {
            background: #17243a !important;
            color: #00f5c4 !important;
            border-color: #00f5c4 !important;
            box-shadow: 0 0 16px rgba(0, 245, 196, 0.35) !important;
        }
        div[data-testid="stButton"] button[kind="primary"] {
            background: linear-gradient(135deg, #00f5c4 0%, #00d4aa 100%) !important;
            color: #05080e !important;
            border: 1px solid rgba(0, 245, 196, 0.6) !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            transition: all 0.2s ease;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover {
            box-shadow: 0 0 20px rgba(0, 245, 196, 0.5) !important;
            transform: translateY(-1px);
        }

        /* Text input styling */
        div[data-testid="stTextInput"] input {
            background: #0a0f1a !important;
            border: 1px solid #1a2638 !important;
            color: #e2e8f0 !important;
            transition: all 0.2s ease;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: #00f5c4 !important;
            box-shadow: 0 0 0 2px rgba(0, 245, 196, 0.15) !important;
        }

        /* Card hover effects */
        .cognios-card {
            transition: all 0.3s ease;
            border: 1px solid #1a2638;
        }
        .cognios-card:hover {
            border-color: #00f5c4;
            box-shadow: 0 8px 32px rgba(0, 245, 196, 0.08);
            transform: translateY(-2px);
        }

        /* Badge animations */
        .cognios-badge {
            transition: all 0.2s ease;
            animation: pulse-glow 2s ease-in-out infinite;
        }
        .cognios-badge.critical {
            animation: pulse-critical 1s ease-in-out infinite;
        }
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 0 5px currentColor; }
            50% { box-shadow: 0 0 15px currentColor; }
        }
        @keyframes pulse-critical {
            0%, 100% { box-shadow: 0 0 5px #ef4444; background: rgba(239, 68, 68, 0.1); }
            50% { box-shadow: 0 0 20px #ef4444; background: rgba(239, 68, 68, 0.2); }
        }

        /* AI response formatting */
        .ai-response-container h4 {
            color: #00f5c4 !important;
            font-size: 12px !important;
            font-weight: 800 !important;
            font-family: 'JetBrains Mono', monospace !important;
            text-transform: uppercase !important;
            letter-spacing: 1px !important;
            margin-top: 12px !important;
            margin-bottom: 6px !important;
            border-bottom: 1px solid rgba(0, 245, 196, 0.15) !important;
            padding-bottom: 4px !important;
        }
        .ai-response-container ul, .ai-response-container ol {
            margin: 4px 0 10px 0 !important;
            padding-left: 18px !important;
        }
        .ai-response-container li {
            margin-bottom: 4px !important;
            color: #e2e8f0 !important;
            font-size: 12px !important;
            line-height: 1.5 !important;
        }
        .ai-response-container strong { color: #ffffff !important; }
        .ai-response-container code {
            background: rgba(0, 245, 196, 0.1) !important;
            color: #00f5c4 !important;
            padding: 2px 6px !important;
            border-radius: 4px !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 11px !important;
        }
        .ai-response-container pre {
            background: #0a0f1a !important;
            border: 1px solid #1a2638 !important;
            border-radius: 6px !important;
            padding: 10px !important;
            overflow-x: auto !important;
            margin: 8px 0 !important;
        }
        .ai-response-container pre code {
            background: transparent !important;
            color: #e2e8f0 !important;
            padding: 0 !important;
            font-size: 11px !important;
        }

        /* Suggestion chips */
        .suggestion-chip {
            display: inline-block;
            padding: 6px 12px;
            margin: 4px 6px 4px 0;
            background: rgba(0, 245, 196, 0.08);
            border: 1px solid rgba(0, 245, 196, 0.2);
            border-radius: 20px;
            color: #00f5c4;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .suggestion-chip:hover {
            background: rgba(0, 245, 196, 0.2);
            border-color: #00f5c4;
            transform: translateY(-1px);
        }

        /* Loading animation */
        @keyframes shimmer {
            0% { background-position: -200% 0; }
            100% { background-position: 200% 0; }
        }
        .loading-skeleton {
            background: linear-gradient(90deg, #101725 25%, #172236 50%, #101725 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 6px;
            height: 16px;
            margin: 8px 0;
        }

        /* Status indicator pulse */
        .status-pulse {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            animation: status-blink 1.5s ease-in-out infinite;
        }
        .status-pulse.active { background: #00f5c4; }
        .status-pulse.warning { background: #f59e0b; }
        .status-pulse.critical { background: #ef4444; }
        @keyframes status-blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        /* Event chain item hover */
        .forensic-chain-container > div {
            transition: all 0.2s ease;
        }
        .forensic-chain-container > div:hover {
            background: #141d2b !important;
            transform: translateX(4px);
        }

        /* Query suggestion container */
        .query-suggestions {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 8px;
            padding: 8px;
            background: rgba(0, 245, 196, 0.04);
            border: 1px solid rgba(0, 245, 196, 0.1);
            border-radius: 8px;
        }
        </style>
    """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # 1. State Management & Data Fetching
    # ---------------------------------------------------------
    if "bb_scrub_val" not in st.session_state:
        st.session_state["bb_scrub_val"] = 0

    scrub_val = st.session_state["bb_scrub_val"]

    # Fetch fresh subsystem data
    hb = dp.get_blackbox_heartbeat_status()
    buffer_stat = dp.get_blackbox_buffer_status()
    z_data = dp.get_blackbox_zscore_series(scrub_val)
    event_chain = dp.get_forensic_event_chain(scrub_val)
    incident_stat = dp.get_blackbox_incident_status(scrub_val)

    # Status indicators
    is_crash = hb.get('is_crash', False)
    if is_crash:
        status_color = "#ef4444"
        status_bg = "rgba(239, 68, 68, 0.15)"
        status_badge_text = "● CRASH INCIDENT DETECTED"
    elif buffer_stat.get('row_count', 0) > 0:
        status_color = "#00f5c4"
        status_bg = "rgba(0, 245, 196, 0.12)"
        status_badge_text = "● FLIGHT RECORDER ACTIVE (30-MIN BUFFER)"
    else:
        status_color = "#38bdf8"
        status_bg = "rgba(56, 189, 248, 0.12)"
        status_badge_text = "● BUFFER STANDBY (WAL READY)"

    # ---------------------------------------------------------
    # 2. Header Banner
    # ---------------------------------------------------------
    st.markdown(f"""
        <div class="cognios-header-banner">
            <div>
                <h1 class="cognios-header-title">
                    <span style="color:#00f5c4; text-shadow: 0 0 16px rgba(0, 245, 196, 0.4);"><i class="fa-solid fa-box-archive"></i></span> BlackBox Flight Recorder
                </h1>
                <p class="cognios-header-sub">
                    POST-INCIDENT FORENSICS // 30-MINUTE ROLLING ROBUST TELEMETRY
                </p>
            </div>
            <div class="cognios-header-badges">
                <span class="cognios-badge-pill" style="background:{status_bg}; color:{status_color}; border-color:{status_color}; box-shadow:0 0 15px {status_bg};">
                    {status_badge_text}
                </span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # 3. Subsystem Cards Row (Consistent .cognios-card Grid)
    # ---------------------------------------------------------
    c1, c2, c3 = st.columns(3)

    # --- Card 1: Heartbeat Sentinel ---
    with c1:
        hb_color = "#ef4444" if is_crash else "#00f5c4"
        hb_label = "CRASH DETECTED" if is_crash else ("CLEAN SHUTDOWN" if hb.get('graceful_shutdown') else "ACTIVE PULSE")
        badge_class = "critical" if is_crash else ""
        st.markdown(f"""
            <div class="cognios-card" style="margin-bottom: 18px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
                    <span style="color:#94a3b8; font-size:13px; font-weight:600; text-transform:uppercase; font-family:'JetBrains Mono', monospace; letter-spacing:0.5px;">
                        <i class="fa-solid fa-heart-pulse" style="color:{hb_color}; margin-right:6px;"></i> Heartbeat Sentinel
                    </span>
                    <span class="cognios-badge {badge_class}" style="color:{hb_color}; background:rgba(0,0,0,0.3); border:1px solid {hb_color} !important;">
                        {hb_label}
                    </span>
                </div>
                <div class="cognios-metric-val" style="color:{hb_color}; font-size:32px;">
                    {hb.get('gap_sec', 0.0)}s <span style="font-size:14px; font-weight:500; color:#64748b;">GAP</span>
                </div>
                <div style="margin-top: 14px; display:flex; justify-content:space-between; align-items:center; font-size:11.5px; font-family:'JetBrains Mono', monospace; color:#94a3b8; border-top: 1px solid #162336; padding-top: 8px;">
                    <span>Last Beat: <strong style="color:#ffffff;">{hb.get('last_beat', 'N/A')}</strong></span>
                    <span style="color:{'#00f5c4' if hb.get('graceful_shutdown') else '#ef4444'}; font-weight:700;">
                        {'GRACEFUL (1)' if hb.get('graceful_shutdown') else 'UNGRACEFUL (0)'}
                    </span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # --- Card 2: Rolling Buffer Storage ---
    with c2:
        buf_rows = buffer_stat.get('row_count', 0)
        buf_color = "#00f5c4" if buf_rows > 0 else "#64748b"
        st.markdown(f"""
            <div class="cognios-card" style="margin-bottom: 18px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
                    <span style="color:#94a3b8; font-size:13px; font-weight:600; text-transform:uppercase; font-family:'JetBrains Mono', monospace; letter-spacing:0.5px;">
                        <i class="fa-solid fa-database" style="color:#38bdf8; margin-right:6px;"></i> Rolling Buffer
                    </span>
                    <span class="cognios-badge" style="color:{buf_color}; background:rgba(0,0,0,0.3); border:1px solid {buf_color} !important;">
                        {buffer_stat.get('status', 'STANDBY')}
                    </span>
                </div>
                <div class="cognios-metric-val" style="color:#38bdf8; font-size:32px;">
                    {buf_rows:,} <span style="font-size:14px; font-weight:500; color:#64748b;">SAMPLES</span>
                </div>
                <div style="margin-top: 14px; display:flex; justify-content:space-between; align-items:center; font-size:11.5px; font-family:'JetBrains Mono', monospace; color:#94a3b8; border-top: 1px solid #162336; padding-top: 8px;">
                    <span>Span: <strong style="color:#ffffff;">{buffer_stat.get('span_str', 'N/A')}</strong></span>
                    <span>Size: <strong style="color:#38bdf8;">{buffer_stat.get('size_kb', 0)} KB</strong></span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # --- Card 3: Replay & Baselines Engine ---
    with c3:
        inc_count = incident_stat.get('incident_count', 0)
        inc_color = incident_stat.get('status_color', '#00f5c4')
        badge_class = "critical" if inc_count > 0 else ""
        st.markdown(f"""
            <div class="cognios-card" style="margin-bottom: 18px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
                    <span style="color:#94a3b8; font-size:13px; font-weight:600; text-transform:uppercase; font-family:'JetBrains Mono', monospace; letter-spacing:0.5px;">
                        <i class="fa-solid fa-magnifying-glass-chart" style="color:#a855f7; margin-right:6px;"></i> Replay & Baselines
                    </span>
                    <span class="cognios-badge {badge_class}" style="color:{inc_color}; background:rgba(0,0,0,0.3); border:1px solid {inc_color} !important;">
                        {incident_stat.get('status_label', 'ALL CLEAR')}
                    </span>
                </div>
                <div class="cognios-metric-val" style="color:{inc_color}; font-size:32px;">
                    {inc_count} <span style="font-size:14px; font-weight:500; color:#64748b;">INCIDENTS</span>
                </div>
                <div style="margin-top: 14px; display:flex; justify-content:space-between; align-items:center; font-size:11.5px; font-family:'JetBrains Mono', monospace; color:#94a3b8; border-top: 1px solid #162336; padding-top: 8px;">
                    <span>Baselines: <strong style="color:#ffffff;">CPU {z_data.get('cpu_baseline', 0)}% / RAM {z_data.get('mem_baseline', 0)}%</strong></span>
                    <span>Limits: <strong style="color:#a855f7;">±2.0σ / +3.0σ</strong></span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # 4. 30-Minute Buffer Scrub Navigation Container
    # ---------------------------------------------------------
    with st.container(border=True):
        st.markdown("""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="color:#00f5c4; font-size:18px;"><i class="fa-solid fa-clock-rotate-left"></i></span>
                    <div>
                        <h3 style="margin:0; font-size:16px; font-weight:700; color:#ffffff;">30-Minute Rolling Buffer Timeline</h3>
                        <p style="margin:2px 0 0 0; font-size:12px; color:#64748b; font-family:'JetBrains Mono', monospace;">
                            SCRUB BACKWARD IN TIME TO REPLAY HISTORICAL ANOMALIES & SYSTEM TELEMETRY
                        </p>
                    </div>
                </div>
                <span class="cognios-badge">
                    WAL Auto-Retention (1800s)
                </span>
            </div>
        """, unsafe_allow_html=True)

        new_scrub = st.slider(
            "Timeline Navigation Slider",
            min_value=-30,
            max_value=0,
            step=1,
            label_visibility="collapsed",
            key="bb_scrub_val"
        )

        offset_text = "Live Stream (T-00:00)" if new_scrub == 0 else f"Historical Replay (T{new_scrub}:00 min)"
        c_lbl, c_b1, c_b2, c_b3 = st.columns([3, 0.7, 0.7, 0.7], vertical_alignment="center")
        with c_lbl:
            st.markdown(f"""
                <div style="font-size:12px; font-family:'JetBrains Mono', monospace;">
                    <span style="color:#64748b;">T-30m ── T-0m (NOW)</span> &nbsp;|&nbsp; 
                    <span style="color:#00f5c4; font-weight:700;">{offset_text}</span>
                </div>
            """, unsafe_allow_html=True)

        with c_b1:
            st.button("-5m", on_click=_on_scrub_preset, args=(-5,), use_container_width=True, help="Jump to 5 minutes ago")
        with c_b2:
            st.button("-15m", on_click=_on_scrub_preset, args=(-15,), use_container_width=True, help="Jump to 15 minutes ago")
        with c_b3:
            st.button("-30m", on_click=_on_scrub_preset, args=(-30,), use_container_width=True, help="Jump to 30 minutes ago (oldest)")

    # ---------------------------------------------------------
    # 5. Main Content Grid: Z-Score Anomaly Detector + Groq AI Synthesis
    # ---------------------------------------------------------
    col_z, col_ai = st.columns([1.15, 1.0])

    with col_z:
        with st.container(border=True):
            x_vals = z_data.get('timestamps', [])
            y_cpu_z = z_data.get('z_scores', [])
            y_mem_z = z_data.get('mem_z_scores', [])

            vis_all = [abs(x) for x in (y_cpu_z + y_mem_z)]
            max_dev = round(max(vis_all), 1) if vis_all else 0.0
            dev_color = "#ef4444" if max_dev >= 3.0 else ("#f59e0b" if max_dev >= 2.0 else "#00f5c4")
            
            dev_badge = "CRITICAL" if max_dev >= 3.0 else ("WARNING" if max_dev >= 2.0 else "NOMINAL")
            
            st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                    <div>
                        <h3 style="margin:0; font-size:17px; font-weight:700; color:#ffffff;">Z-Score Anomaly Detector</h3>
                        <p style="margin:2px 0 0 0; font-size:12px; color:#64748b; font-family:'JetBrains Mono', monospace;">
                            STREAMING STATISTICAL DEVIATION AGAINST DYNAMIC BASELINES
                        </p>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:22px; font-weight:800; color:{dev_color}; font-family:'JetBrains Mono', monospace; line-height:1;">
                            {max_dev}σ
                        </div>
                        <div style="font-size:10px; color:#64748b; font-weight:600; text-transform:uppercase; margin-top:2px;">Peak Deviation</div>
                        <span class="cognios-badge" style="margin-top:6px; display:inline-block; font-size:9px;">{dev_badge}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            if HAS_PLOTLY and len(x_vals) > 0:
                fig = go.Figure()

                # CPU Z-Score line
                fig.add_trace(go.Scatter(
                    x=x_vals,
                    y=y_cpu_z,
                    mode='lines',
                    name='CPU Z-Score',
                    line=dict(color='#00f5c4', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(0, 245, 196, 0.05)',
                    hovertemplate='Time: %{x}<br>CPU Deviation: %{y:.2f}σ<extra></extra>'
                ))

                # RAM Z-Score line
                fig.add_trace(go.Scatter(
                    x=x_vals,
                    y=y_mem_z,
                    mode='lines',
                    name='RAM Z-Score',
                    line=dict(color='#38bdf8', width=2, dash='dot'),
                    hovertemplate='Time: %{x}<br>RAM Deviation: %{y:.2f}σ<extra></extra>'
                ))

                # Threshold reference lines
                fig.add_shape(type="line", x0=0, x1=1, xref="paper", y0=3.0, y1=3.0, line=dict(color="#ef4444", width=1, dash="dash"))
                fig.add_shape(type="line", x0=0, x1=1, xref="paper", y0=2.0, y1=2.0, line=dict(color="#f59e0b", width=1, dash="dot"))
                fig.add_shape(type="line", x0=0, x1=1, xref="paper", y0=-2.0, y1=-2.0, line=dict(color="#f59e0b", width=1, dash="dot"))

                all_z = (y_cpu_z or []) + (y_mem_z or [])
                y_max = max(4.0, max(all_z) + 1.0) if all_z else 4.0
                y_min = min(-2.5, min(all_z) - 0.5) if all_z else -2.5

                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=30, r=20, t=10, b=25),
                    height=290,
                    showlegend=True,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1,
                        font=dict(color="#94a3b8", size=10, family="JetBrains Mono")
                    ),
                    xaxis=dict(
                        showgrid=True,
                        gridcolor='#141d2b',
                        zeroline=False,
                        nticks=6,
                        tickangle=0,
                        tickfont=dict(color='#64748b', size=10, family="JetBrains Mono")
                    ),
                    yaxis=dict(
                        range=[y_min, y_max],
                        showgrid=True,
                        gridcolor='#141d2b',
                        zeroline=True,
                        zerolinecolor='#1e293b',
                        tickfont=dict(color='#64748b', size=10, family="JetBrains Mono")
                    )
                )
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'responsive': True})
            else:
                df_chart = pd.DataFrame({
                    "CPU Z-Score": y_cpu_z,
                    "RAM Z-Score": y_mem_z
                }, index=x_vals if len(x_vals) == len(y_cpu_z) else None)
                st.line_chart(df_chart, height=290)

    with col_ai:
        with st.container(border=True):
            groq_model_name = os.getenv("GROQ_MODEL") or getattr(config, "GROQ_MODEL", "llama-3.3-70b-versatile")
            model_badge = groq_model_name.split("/")[-1].upper()

            st.html(f"""
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="color:#00f5c4; font-size:16px;"><i class="fa-solid fa-brain"></i></span>
                        <h3 style="margin:0; font-size:17px; font-weight:700; color:#ffffff;">Groq AI Synthesis</h3>
                    </div>
                    <span class="cognios-badge" style="font-size:10px; padding:2px 8px;">
                        {model_badge}
                    </span>
                </div>
            """)

            # Initialize AI postmortem on first load only
            if "ai_postmortem" not in st.session_state:
                st.session_state["ai_postmortem"] = ""

            if not st.session_state["ai_postmortem"]:
                with st.spinner("Analyzing telemetry..."):
                    st.session_state["ai_postmortem"] = dp.get_ai_post_mortem(scrub_minutes=scrub_val)

            # Always display the current AI response from session state
            formatted_html = dp.format_ai_response_to_html(st.session_state["ai_postmortem"])
            st.html(f"""
                <div class="ai-response-container" style="min-height:190px; max-height:280px; overflow-y:auto; margin-bottom:14px; font-size:12.5px; padding: 4px;">
                    {formatted_html}
                </div>
            """)

            # Helper to run a query and update session state
            def _run_ai_query(query_text):
                with st.spinner("Querying AI..."):
                    st.session_state["ai_postmortem"] = dp.get_ai_post_mortem(query_text, scrub_minutes=scrub_val)

            # Query input with synthesize button
            with st.form("bb_ai_query_form", border=False):
                p_col1, p_col2 = st.columns([2.8, 1.2], vertical_alignment="center")
                with p_col1:
                    user_query = st.text_input(
                        "Ask AI Forensic Assistant",
                        placeholder="e.g., What caused the CPU spike at T-12m?",
                        label_visibility="collapsed",
                        key="bb_ai_query_input"
                    )
                with p_col2:
                    submitted = st.form_submit_button("Synthesize", type="primary", use_container_width=True, icon=":material/psychology:")
                    if submitted and user_query.strip():
                        _run_ai_query(user_query.strip())
                        st.rerun(scope="fragment")

    # ---------------------------------------------------------
    # 6. Forensic Event Chain (Chronological Incident Replay)
    # ---------------------------------------------------------
    with st.container(border=True):
        st.html("""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
                <h3 style="margin:0; font-size:17px; font-weight:700; color:#ffffff;">Forensic Event Chain</h3>
                <span style="color:#64748b; font-size:11.5px; font-family:'JetBrains Mono', monospace;">
                    Causal Incident Timeline Reconstructed From Rolling Buffer
                </span>
            </div>
        """)

        if event_chain and len(event_chain) > 0:
            events_html = []
            for ev in event_chain:
                badge_color = ev.get('color', '#f59e0b')
                badge_level = ev.get('level', 'WARN')
                ev_time = ev.get('time', '??:??')
                ev_msg = ev.get('msg', '')
                events_html.append(
                    f'<div style="display:flex; align-items:center; gap:14px; padding:10px 16px; '
                    f'background:#101725; border-radius:8px; margin-bottom:8px; border-left:3px solid {badge_color}; '
                    f'font-family:\'JetBrains Mono\', monospace; font-size:13px; box-shadow:0 2px 8px rgba(0,0,0,0.2);">'
                    f'<span style="color:#64748b; font-weight:600; min-width:65px;">{ev_time}</span>'
                    f'<span style="color:{badge_color}; font-weight:700; min-width:48px;">{badge_level}:</span>'
                    f'<span style="color:#e2e8f0; flex-grow:1;">{ev_msg}</span>'
                    f'</div>'
                )

            full_chain_markup = "".join(events_html)
            st.html(
                f'<div class="forensic-chain-container" style="max-height:320px; overflow-y:auto; padding-right:4px;">'
                f'{full_chain_markup}'
                f'</div>'
            )
        else:
            st.html(
                '<div style="padding:16px 20px; background:rgba(0, 245, 196, 0.04); border:1px solid rgba(0, 245, 196, 0.2); '
                'border-radius:8px; font-family:\'JetBrains Mono\', monospace; font-size:13px;">'
                '<span style="color:#00f5c4; font-weight:700;">ALL BASELINES NOMINAL:</span>'
                '<span style="color:#94a3b8; margin-left:6px;">No statistical anomalies, memory leaks, or I/O storms detected in this 30-minute window. System parameters operated within standard dynamic baseline bounds.</span>'
                '</div>'
            )
