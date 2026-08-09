"""BlackBox System Flight Recorder View matching Stitch design."""

import streamlit as st
import plotly.graph_objects as go
import dashboard.data_provider as dp
import config


def render():
    st.html("""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;"><div><h1 style="margin:0; font-size: 28px; font-weight: 800; color: #ffffff; display:flex; align-items:center; gap:10px;"><span style="color:#00f5c4;"><i class="fa-solid fa-box-archive"></i></span> BlackBox Flight Recorder</h1><p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px; font-family: 'JetBrains Mono';">SYSTEM FLIGHT RECORDER // POST-INCIDENT FORENSICS</p></div><div style="background: rgba(239, 68, 68, 0.15); color:#ef4444; border-radius:6px; padding:6px 14px; font-size:12px; font-weight:700; font-family:'JetBrains Mono';">● INCIDENT MONITORING ACTIVE</div></div>""")

    # 30-Minute Rolling Buffer Scrub Slider
    st.html("""<div style="background:#0d121c; border-radius:14px; padding:22px; margin-bottom:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;"><div style="display:flex; align-items:center; gap:8px;"><span style="color:#00f5c4;"><i class="fa-solid fa-rotate-left"></i></span><h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">30-Minute Rolling Buffer</h3></div><span class="cognios-badge">Scrub Mode: Active</span></div>""")

    scrub_val = st.slider(
        "Timeline Navigation",
        min_value=-30,
        max_value=0,
        value=0,
        step=1,
        format="T%d:00 min",
        label_visibility="collapsed"
    )

    st.html(f"""<div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; font-family:'JetBrains Mono'; margin-top:4px;"><span>T-30:00</span><span>T-20:00</span><span>T-10:00</span><span style="color:#00f5c4; font-weight:bold;">Current Window (Offset: {scrub_val} min)</span><span>T-00:00 (Live)</span></div></div>""")

    # Dynamic query using scrub slider position
    z_data = dp.get_blackbox_zscore_series(scrub_val)
    event_chain = dp.get_forensic_event_chain(scrub_val)

    # Subsystems Grid: Heartbeat Sentinel | Rule Engine | ML Anomaly Model
    hb = dp.get_blackbox_heartbeat_status()
    rules = dp.get_blackbox_rule_engine_alerts()
    ml = dp.get_blackbox_model_status()

    b1, b2, b3 = st.columns(3)

    with b1:
        hb_color = "#ef4444" if hb['is_crash'] else "#00f5c4"
        st.html(f"""
            <div style="background:#0d121c; border-radius:14px; padding:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3); margin-bottom:20px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <div style="font-size:14px; font-weight:700; color:#ffffff; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-heartbeat" style="color:{hb_color};"></i> Heartbeat Sentinel
                    </div>
                    <span style="background:rgba(0,0,0,0.3); color:{hb_color}; font-size:10px; font-weight:700; font-family:'JetBrains Mono'; padding:3px 8px; border-radius:4px;">
                        {hb['status_label']}
                    </span>
                </div>
                <div style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono'; margin-bottom:4px;">
                    Last Beat: <strong style="color:#ffffff;">{hb['last_beat']}</strong> ({hb['gap_sec']}s gap)
                </div>
                <div style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono';">
                    Shutdown Flag: <strong style="color:{'#00f5c4' if hb['graceful_shutdown'] else '#ef4444'};">{'GRACEFUL (1)' if hb['graceful_shutdown'] else 'UNGRACEFUL / CRASH (0)'}</strong>
                </div>
            </div>
        """)

    with b2:
        rule_status_color = "#ef4444" if rules['fired_alerts'] else "#00f5c4"
        st.html(f"""
            <div style="background:#0d121c; border-radius:14px; padding:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3); margin-bottom:20px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <div style="font-size:14px; font-weight:700; color:#ffffff; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-gears" style="color:#38bdf8;"></i> Rule Engine Monitor
                    </div>
                    <span style="background:rgba(0,0,0,0.3); color:{rule_status_color}; font-size:10px; font-weight:700; font-family:'JetBrains Mono'; padding:3px 8px; border-radius:4px;">
                        {rules['status']}
                    </span>
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px; font-size:11px; font-family:'JetBrains Mono'; color:#94a3b8;">
                    <div>CPU Limit: <strong style="color:#ffffff;">{rules['thresholds'][0]['limit']}</strong></div>
                    <div>Mem Limit: <strong style="color:#ffffff;">{rules['thresholds'][1]['limit']}</strong></div>
                    <div>Zombie Limit: <strong style="color:#ffffff;">{rules['thresholds'][2]['limit']}</strong></div>
                    <div>Swap Limit: <strong style="color:#ffffff;">{rules['thresholds'][4]['limit']}</strong></div>
                </div>
            </div>
        """)

    with b3:
        st.html(f"""
            <div style="background:#0d121c; border-radius:14px; padding:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3); margin-bottom:6px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <div style="font-size:14px; font-weight:700; color:#ffffff; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-brain" style="color:#a855f7;"></i> Isolation Forest ML
                    </div>
                    <span style="background:rgba(0,245,196,0.12); color:#00f5c4; font-size:10px; font-weight:700; font-family:'JetBrains Mono'; padding:3px 8px; border-radius:4px;">
                        LOADED
                    </span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px; color:#94a3b8; font-family:'JetBrains Mono'; margin-bottom:6px;">
                    <span>Vectors: <strong style="color:#00f5c4;">{ml['vectors_count']} samples</strong></span>
                    <span>Dim: <strong style="color:#38bdf8;">{ml['feature_dim']}D</strong></span>
                </div>
            </div>
        """)
        if st.button("Retrain ML Model", key="retrain_if_model", use_container_width=True):
            with st.spinner("Training Isolation Forest model on vectors..."):
                res = dp.retrain_blackbox_model()
                if res['success']:
                    st.success(res['message'])
                else:
                    st.error(res['message'])

    # Middle Row: Z-Score Anomaly Detector & AI Synthesis
    col_chart, col_ai = st.columns([3, 2])

    with col_chart:
        st.html(f"""<div style="background:#0d121c; border-radius:14px; padding:22px; height:100%; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px;"><div><h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Z-Score Anomaly Detector</h3><p style="margin:2px 0 0 0; font-size:12px; color:#64748b;">Streaming statistical deviations (&gt;2.8σ threshold)</p></div><div style="text-align:right;"><div style="font-size:26px; font-weight:800; color:#00f5c4; font-family:'JetBrains Mono';">{z_data['max_z']}σ</div><div style="font-size:11px; color:#38bdf8; font-weight:600;"><i class="fa-solid fa-chart-line"></i> Real-time Deviation</div></div></div>""")

        x_vals = z_data['timestamps']
        y_vals = z_data['z_scores']

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            mode='lines',
            name='Z-Score',
            line=dict(color='#38bdf8', width=2),
            fill='tozeroy',
            fillcolor='rgba(56, 189, 248, 0.08)'
        ))

        fig.add_shape(type="line", x0=0, x1=1, xref="paper", y0=2.8, y1=2.8, line=dict(color="#ef4444", width=1, dash="dash"))
        fig.add_shape(type="line", x0=0, x1=1, xref="paper", y0=-2.8, y1=-2.8, line=dict(color="#ef4444", width=1, dash="dash"))

        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=30, r=20, t=10, b=30),
            height=280,
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor='#151d2a', zeroline=False, tickfont=dict(color='#64748b', size=10)),
            yaxis=dict(range=[-4, 6], showgrid=True, gridcolor='#151d2a', zeroline=False, tickfont=dict(color='#64748b', size=10))
        )

        st.plotly_chart(fig, use_container_width=True)
        st.html("</div>")

    with col_ai:
        st.html("""<div style="background:#0d121c; border-radius:14px; padding:22px; height:100%; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;"><div style="display:flex; align-items:center; gap:10px;"><span style="color:#00f5c4; font-size:18px;"><i class="fa-solid fa-robot"></i></span><div><h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Groq AI Synthesis</h3><p style="margin:0; font-size:11px; color:#64748b; font-family:'JetBrains Mono';">LLM FORENSIC QUERY ENGINE (LLAMA-3.3-70B)</p></div></div><span class="cognios-badge">● READY</span></div>""")

        if "ai_postmortem" not in st.session_state:
            st.session_state["ai_postmortem"] = dp.get_ai_post_mortem()

        formatted_html = dp.format_ai_response_to_html(st.session_state["ai_postmortem"])
        st.html(
            f"""<div class="ai-response-container">
                {formatted_html}
            </div>"""
        )

        p_col1, p_col2 = st.columns([2.5, 1])
        with p_col1:
            user_query = st.text_input("Ask AI Forensic Assistant", placeholder="Ask why OS is slow...", label_visibility="collapsed")
        with p_col2:
            st.markdown('<div class="synth-btn-box">', unsafe_allow_html=True)
            if st.button("Synthesize", icon=":material/psychology:", use_container_width=True):
                with st.spinner("Analyzing with Groq LLM..."):
                    st.session_state["ai_postmortem"] = dp.get_ai_post_mortem(user_query)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.html("</div>")

    # Forensic Event Chain (100% Dynamic from SQLite Telemetry)
    st.html("""<div style="background:#0d121c; border-radius:14px; padding:22px; margin-top:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; align-items:center; gap:8px; margin-bottom:16px;"><span style="color:#94a3b8;"><i class="fa-solid fa-timeline"></i></span><h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Forensic Event Chain</h3></div>""")

    for ev in event_chain:
        st.html(f"""<div style="display:flex; align-items:center; gap:16px; padding:12px 16px; background:#131b28; border-radius:6px; margin-bottom:10px; font-family:'JetBrains Mono'; font-size:13px;"><span style="color:#64748b;">{ev['time']}</span><span style="color:{ev['color']}; font-weight:700;">{ev['level']}:</span><span style="color:#e2e8f0;">{ev['msg']}</span></div>""")

    st.html("</div>")
