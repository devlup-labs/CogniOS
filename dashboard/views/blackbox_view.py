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
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 22px;">
            <div>
                <h1 style="margin:0; font-size: 28px; font-weight: 800; color: #ffffff; display:flex; align-items:center; gap:12px;">
                    <span style="color:#00f5c4; text-shadow: 0 0 16px rgba(0, 245, 196, 0.4);"><i class="fa-solid fa-box-archive"></i></span> BlackBox Flight Recorder
                </h1>
                <p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px; font-family: 'JetBrains Mono', monospace;">
                    POST-INCIDENT FORENSICS // 30-MINUTE ROLLING ROBUST TELEMETRY
                </p>
            </div>
            <div style="background: {status_bg}; color:{status_color}; border: 1px solid {status_color}; border-radius:6px; padding:6px 16px; font-size:12px; font-weight:700; font-family:'JetBrains Mono', monospace; box-shadow: 0 0 15px {status_bg};">
                {status_badge_text}
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
        st.markdown(f"""
            <div class="cognios-card" style="margin-bottom: 18px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
                    <span style="color:#94a3b8; font-size:13px; font-weight:600; text-transform:uppercase; font-family:'JetBrains Mono', monospace; letter-spacing:0.5px;">
                        <i class="fa-solid fa-heart-pulse" style="color:{hb_color}; margin-right:6px;"></i> Heartbeat Sentinel
                    </span>
                    <span class="cognios-badge" style="color:{hb_color}; background:rgba(0,0,0,0.3); border:1px solid {hb_color} !important;">
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
        st.markdown(f"""
            <div class="cognios-card" style="margin-bottom: 18px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
                    <span style="color:#94a3b8; font-size:13px; font-weight:600; text-transform:uppercase; font-family:'JetBrains Mono', monospace; letter-spacing:0.5px;">
                        <i class="fa-solid fa-magnifying-glass-chart" style="color:#a855f7; margin-right:6px;"></i> Replay & Baselines
                    </span>
                    <span class="cognios-badge" style="color:{inc_color}; background:rgba(0,0,0,0.3); border:1px solid {inc_color} !important;">
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

        c_slider, c_presets = st.columns([3.8, 1.4])

        with c_slider:
            new_scrub = st.slider(
                "Timeline Navigation Slider",
                min_value=-30,
                max_value=0,
                step=1,
                label_visibility="collapsed",
                key="bb_scrub_val"
            )

            offset_text = "Live Stream (T-00:00)" if new_scrub == 0 else f"Historical Replay (T{new_scrub}:00 min)"
            st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; font-family:'JetBrains Mono', monospace; margin-top:-4px;">
                    <span style="color:#64748b;">T-30 min</span>
                    <span style="color:#00f5c4; font-weight:700; background:rgba(0,245,196,0.1); padding:3px 12px; border-radius:6px; border:1px solid rgba(0,245,196,0.25);">
                        {offset_text}
                    </span>
                    <span style="color:#64748b;">Live (T-00:00)</span>
                </div>
            """, unsafe_allow_html=True)

        with c_presets:
            p1, p2 = st.columns(2)
            with p1:
                st.button("🔴 Live", on_click=_on_scrub_preset, args=(0,), use_container_width=True, help="Jump to live stream")
                st.button("T -15m", on_click=_on_scrub_preset, args=(-15,), use_container_width=True, help="Jump to T-15 minutes")
            with p2:
                st.button("T -5m", on_click=_on_scrub_preset, args=(-5,), use_container_width=True, help="Jump to T-5 minutes")
                st.button("T -30m", on_click=_on_scrub_preset, args=(-30,), use_container_width=True, help="Jump to T-30 minutes")

    # ---------------------------------------------------------
    # 5. Middle Row: Statistical Z-Score Chart & Groq AI Synthesis
    # ---------------------------------------------------------
    col_chart, col_ai = st.columns([3.1, 1.9])

    with col_chart:
        with st.container(border=True):
            x_vals = z_data.get('timestamps', [])
            y_cpu_z = z_data.get('z_scores', [])
            y_mem_z = z_data.get('mem_z_scores', [])

            vis_all = [abs(x) for x in (y_cpu_z + y_mem_z)]
            max_dev = round(max(vis_all), 1) if vis_all else 0.0
            dev_color = "#ef4444" if max_dev >= 3.0 else ("#f59e0b" if max_dev >= 2.0 else "#00f5c4")
            
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
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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
            # if "ai_postmortem" not in st.session_state:
            #     st.session_state["ai_postmortem"] = dp.get_ai_post_mortem(scrub_minutes=scrub_val)

            if "ai_postmortem" not in st.session_state:
                st.session_state["ai_postmortem"] = ""  # empty on first load

            if not st.session_state["ai_postmortem"]:
                st.session_state["ai_postmortem"] = dp.get_ai_post_mortem(scrub_minutes=scrub_val)

            # Always display the current AI response from session state
            formatted_html = dp.format_ai_response_to_html(st.session_state["ai_postmortem"])
            st.html(f"""
                <div class="ai-response-container" style="min-height:190px; max-height:220px; overflow-y:auto; margin-bottom:14px; font-size:12.5px;">
                    {formatted_html}
                </div>
            """)

            # Helper to run a query and update session state
            def _run_ai_query(query_text):
                st.session_state["ai_postmortem"] = ""
                st.session_state["ai_postmortem"] = dp.get_ai_post_mortem(query_text, scrub_minutes=scrub_val)

            # Query input with synthesize button
            p_col1, p_col2 = st.columns([2.7, 1.3], vertical_alignment="center")
            with p_col1:
                user_query = st.text_input(
                    "Ask AI Forensic Assistant",
                    placeholder="Ask why system spiked...",
                    label_visibility="collapsed",
                    key="bb_ai_query_input"
                )
            with p_col2:
                if st.button("Synthesize", icon=":material/psychology:", use_container_width=True):
                    if user_query and user_query.strip():
                        with st.spinner("Analyzing timeline..."):
                            _run_ai_query(user_query.strip())
                            st.rerun(scope="fragment")

            # Quick Prompt Presets (No emojis, sleek Material icons)
            pill1, pill2, pill3 = st.columns(3)
            with pill1:
                if st.button("Spikes", icon=":material/bolt:", use_container_width=True, help="Analyze CPU & RAM load spikes"):
                    with st.spinner("Analyzing spikes..."):
                        _run_ai_query("Analyze any CPU or Memory spikes in this timeline.")
                        st.rerun(scope="fragment")
            with pill2:
                if st.button("Leaks", icon=":material/water_drop:", use_container_width=True, help="Check memory leak indicators"):
                    with st.spinner("Checking memory leaks..."):
                        _run_ai_query("Check if there are signs of memory leaks or monotonic memory drift.")
                        st.rerun(scope="fragment")
            with pill3:
                if st.button("Summary", icon=":material/description:", use_container_width=True, help="Executive post-mortem summary"):
                    with st.spinner("Generating post-mortem..."):
                        _run_ai_query("Provide an executive post-mortem of this 30-minute window.")
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
                f'<div class="forensic-chain-container" style="max-height:260px; overflow-y:auto; padding-right:4px;">'
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
