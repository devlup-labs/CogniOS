"""OS Doctor AI Anomaly Diagnostics View matching Stitch design."""

import streamlit as st
import plotly.graph_objects as go
import dashboard.data_provider as dp
import config

def render():
    diag_score = dp.get_os_doctor_anomaly_score()
    hogs = dp.get_resource_hogs_heatmap()
    stats = dp.get_os_doctor_summary_stats()

    st.html("""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;"><div><h1 style="margin:0; font-size: 28px; font-weight: 800; color: #ffffff; display:flex; align-items:center; gap:10px;"><span style="color:#00f5c4;"><i class="fa-solid fa-stethoscope"></i></span> AI Anomaly Diagnostics</h1><p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px; font-family: 'JetBrains Mono';">ISOLATION FOREST MODEL ACTIVE // OLLAMA GEMMA2 DIAGNOSTIC ENGINE</p></div><div style="background: rgba(0, 245, 196, 0.12); color:#00f5c4; border-radius:6px; padding:6px 14px; font-size:12px; font-weight:700; font-family:'JetBrains Mono';">● LIVE TELEMETRY</div></div>""")

    col_gauge, col_heatmap = st.columns([1, 2])

    with col_gauge:
        st.html("""<div style="background:#0d121c; border-radius:14px; padding:22px; text-align:center; height:100%; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="font-size:12px; font-weight:700; color:#64748b; font-family:'JetBrains Mono'; text-transform:uppercase; margin-bottom:12px;">Overall System Anomaly Score</div>""")

        score_val = diag_score['score']
        score_status = diag_score['status']

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score_val,
            number={'suffix': "/100", 'font': {'size': 36, 'color': '#ffffff', 'family': 'JetBrains Mono'}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#64748b"},
                'bar': {'color': "#00f5c4"},
                'bgcolor': "rgba(0,0,0,0)",
                'bordercolor': "rgba(0,0,0,0)",
                'steps': [
                    {'range': [0, 45], 'color': 'rgba(0, 245, 196, 0.15)'},
                    {'range': [45, 75], 'color': 'rgba(245, 158, 11, 0.15)'},
                    {'range': [75, 100], 'color': 'rgba(239, 68, 68, 0.15)'}
                ]
            }
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=200,
            margin=dict(l=20, r=20, t=20, b=10)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.html(f"""<div style="margin-top: -10px;"><span class="cognios-badge" style="font-size:13px; padding:6px 16px;">{score_status}</span><p style="margin: 8px 0 0 0; font-size:11px; color:#64748b; font-family:'JetBrains Mono';">DERIVED FROM ISOLATION FOREST</p></div></div>""")

    with col_heatmap:
        st.html("""<div style="background:#0d121c; border-radius:14px; padding:22px; height:100%; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;"><h3 style="margin:0; font-size:16px; font-weight:700; color:#ffffff;">TOP RESOURCE HOGS PROCESS TABLE</h3><div style="display:flex; gap:12px; font-size:11px; font-family:'JetBrains Mono'; font-weight:600;"><span style="color:#00f5c4;">■ NORMAL</span><span style="color:#f59e0b;">■ ELEVATED</span><span style="color:#ef4444;">■ HIGH RISK</span></div></div>""")

        st.html("""<div style="display:grid; grid-template-columns: 3fr 1.5fr 1.5fr 1.5fr 1.5fr; font-size:11px; font-weight:700; color:#64748b; font-family:'JetBrains Mono'; padding-bottom:8px; border-bottom:1px solid #16202e; margin-bottom:8px;"><span>PROCESS NAME</span><span>PID</span><span>CPU %</span><span>RAM %</span><span>STATUS</span></div>""")

        for idx, hog in enumerate(hogs[:8]):
            status_label = "HIGH RISK" if hog['impact'] > 30 else ("ELEVATED" if hog['impact'] > 15 else "NORMAL")
            status_color = hog['color']
            
            c1, c2, c3, c4, c5 = st.columns([3, 1.5, 1.5, 1.5, 1.5])
            with c1:
                st.markdown(f"<span style='color:#ffffff; font-weight:700; font-family:\"JetBrains Mono\"; font-size:13px;'>{hog['name']}</span>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<span style='color:#38bdf8; font-family:\"JetBrains Mono\"; font-size:12px;'>{hog['pid']}</span>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<span style='color:#ffffff; font-family:\"JetBrains Mono\"; font-size:12px;'>{hog['cpu']}%</span>", unsafe_allow_html=True)
            with c4:
                st.markdown(f"<span style='color:#94a3b8; font-family:\"JetBrains Mono\"; font-size:12px;'>{hog['ram']}%</span>", unsafe_allow_html=True)
            with c5:
                st.markdown(f"<span style='background:rgba(0,0,0,0.3); color:{status_color}; border-radius:4px; padding:2px 6px; font-size:10px; font-weight:800; font-family:\"JetBrains Mono\";'>{status_label}</span>", unsafe_allow_html=True)

        st.html("</div>")

    # --- NEW SECTION: Human-Readable LLM Diagnostic Explanations ---
    st.html("""<div style="background:#0d121c; border-radius:14px; padding:24px; margin-top:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;"><div style="display:flex; align-items:center; gap:10px;"><span style="color:#00f5c4; font-size:20px;"><i class="fa-solid fa-brain"></i></span><h3 style="margin:0; font-size:20px; font-weight:700; color:#ffffff;">AI Diagnostic Stream & Human-Readable Explanations</h3></div><div style="background:rgba(0, 245, 196, 0.12); color:#00f5c4; border-radius:6px; padding:4px 12px; font-size:11px; font-weight:700; font-family:'JetBrains Mono';">ENGINE: OLLAMA (GEMMA2)</div></div></div>""")

    # KPI summary bar
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.html(f"""<div style="background:#131b28; border-radius:10px; padding:14px; text-align:center;"><div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700;">TOTAL DIAGNOSES</div><div style="font-size:24px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono'; margin-top:4px;">{stats['total_diagnoses']}</div></div>""")
    with k2:
        st.html(f"""<div style="background:#131b28; border-radius:10px; padding:14px; text-align:center;"><div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700;">HIGH / CRITICAL</div><div style="font-size:24px; font-weight:800; color:#ef4444; font-family:'JetBrains Mono'; margin-top:4px;">{stats['critical_high_count']}</div></div>""")
    with k3:
        st.html(f"""<div style="background:#131b28; border-radius:10px; padding:14px; text-align:center;"><div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700;">AVG AI CONFIDENCE</div><div style="font-size:24px; font-weight:800; color:#00f5c4; font-family:'JetBrains Mono'; margin-top:4px;">{stats['avg_confidence']}%</div></div>""")
    with k4:
        st.html(f"""<div style="background:#131b28; border-radius:10px; padding:14px; text-align:center;"><div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700;">LATEST ANOMALY</div><div style="font-size:14px; font-weight:700; color:#38bdf8; font-family:'JetBrains Mono'; margin-top:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{stats['latest_issue']}</div></div>""")

    # Filter & Search Controls
    f1, f2 = st.columns([1, 2])
    with f1:
        sev_filter = st.selectbox("Filter by Severity", ["All", "High", "Medium", "Low"], key="os_doc_sev_filter")
    with f2:
        search_query = st.text_input("Search Diagnoses", placeholder="e.g. CPU, RAM, process, network...", key="os_doc_search_query")

    diagnoses = dp.get_os_doctor_diagnoses(limit=15, severity_filter=sev_filter, search_query=search_query)

    if not diagnoses:
        st.info("No AI diagnoses recorded yet. Run `uv run test.py` to start generating live anomaly diagnoses.")
    else:
        for diag in diagnoses:
            sev_str = (diag['severity'] or "Low").upper()
            if sev_str in ("HIGH", "CRITICAL"):
                badge_bg, badge_fg = "rgba(239, 68, 68, 0.15)", "#ef4444"
            elif sev_str == "MEDIUM":
                badge_bg, badge_fg = "rgba(245, 158, 11, 0.15)", "#f59e0b"
            else:
                badge_bg, badge_fg = "rgba(0, 245, 196, 0.15)", "#00f5c4"

            conf_pct = diag['confidence']

            st.html(f"""<div style="background:#131b28; border:1px solid #1e293b; border-radius:12px; padding:18px; margin-bottom:14px;"><div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e293b; padding-bottom:10px; margin-bottom:12px;"><div style="display:flex; align-items:center; gap:10px;"><span style="background:{badge_bg}; color:{badge_fg}; font-size:11px; font-weight:800; font-family:'JetBrains Mono'; padding:3px 10px; border-radius:4px;">{sev_str}</span><span style="font-size:16px; font-weight:700; color:#ffffff;">{diag['issue']}</span></div><div style="display:flex; align-items:center; gap:12px; font-size:12px; font-family:'JetBrains Mono';"><span style="color:#64748b;">{diag['created_at']}</span><span style="background:rgba(56, 189, 248, 0.15); color:#38bdf8; font-weight:700; padding:2px 8px; border-radius:4px;">{conf_pct}% Confidence</span></div></div><div style="margin-bottom:12px;"><div style="font-size:11px; font-weight:700; color:#64748b; font-family:'JetBrains Mono'; text-transform:uppercase; margin-bottom:4px;">ROOT CAUSE EXPLANATION</div><div style="font-size:14px; color:#e2e8f0; line-height:1.5; background:#0d121c; padding:12px; border-radius:8px; border-left:3px solid {badge_fg};">{diag['cause']}</div></div><div style="display:flex; align-items:center; gap:10px;"><span style="font-size:11px; font-weight:700; color:#00f5c4; font-family:'JetBrains Mono';">SUGGESTED REMEDIATION:</span><span style="font-size:13px; color:#38bdf8; font-weight:600; font-family:'JetBrains Mono'; background:rgba(56, 189, 248, 0.1); padding:4px 10px; border-radius:4px;">{diag['suggested_action']}</span></div></div>""")

            with st.expander(f"🔍 Raw Telemetry Payload (Alert #{diag['alert_id']})"):
                t1, t2 = st.columns(2)
                with t1:
                    st.markdown("**Raw Metrics**")
                    st.json(diag['raw_metrics'])
                with t2:
                    st.markdown("**Process Metadata**")
                    st.json(diag['metadata'])

    # Bottom Process Drill-Down Card
    selected_pid = st.session_state.get("selected_pid", hogs[0]['pid'] if hogs else 1)
    drill = dp.get_process_drilldown(selected_pid)

    st.html(f"""<div style="background:#0d121c; border-radius:14px; padding:24px; margin-top:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;"><div style="display:flex; align-items:center; gap:10px;"><span style="color:#00f5c4;"><i class="fa-solid fa-magnifying-glass"></i></span><h3 style="margin:0; font-size:20px; font-weight:700; color:#ffffff;">Layer 4 Process Drill-Down</h3><span style="background:rgba(0, 245, 196, 0.12); color:#00f5c4; border-radius:4px; padding:2px 10px; font-size:12px; font-family:'JetBrains Mono'; font-weight:700;">PID: {drill['pid']} ({drill['name']})</span></div></div>""")

    d1, d2, d3 = st.columns(3)

    with d1:
        st.html(f"""<div style="background:#131b28; border-radius:10px; padding:18px;"><div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700;">OPEN FILE DESCRIPTORS</div><div style="font-size:28px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono'; margin-top:4px;">{drill['open_files']:,} <span style="font-size:12px; color:#00f5c4; font-weight:600;">Active</span></div></div>""")

    with d2:
        st.html(f"""<div style="background:#131b28; border-radius:10px; padding:18px;"><div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700;">CPU TIME ({drill['thread_count']} THREADS)</div><div style="font-size:15px; font-weight:700; color:#ffffff; font-family:'JetBrains Mono'; margin-top:6px; display:flex; gap:16px;"><span>User: <strong style="color:#38bdf8;">{drill['user_time']}s</strong></span><span>Sys: <strong style="color:#f59e0b;">{drill['sys_time']}s</strong></span></div><div style="background:#1a2436; height:6px; border-radius:3px; margin-top:10px; display:flex; overflow:hidden;"><div style="background:#38bdf8; width:75%; height:100%;"></div><div style="background:#f59e0b; width:25%; height:100%;"></div></div></div>""")

    with d3:
        st.html(f"""<div style="background:#131b28; border-radius:10px; padding:18px;"><div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700;">CONTEXT SWITCHES</div><div style="font-size:15px; font-weight:700; color:#ffffff; font-family:'JetBrains Mono'; margin-top:6px; display:flex; gap:16px;"><span>Vol: <strong style="color:#ffffff;">{drill['vol_ctx']}</strong></span><span>Invol: <strong style="color:#ef4444;">{drill['invol_ctx']}</strong></span></div></div>""")

    # Socket Table
    st.html("""<div style="margin-top:20px;"><div style="font-size:12px; font-weight:700; color:#64748b; font-family:'JetBrains Mono'; margin-bottom:10px;">SOCKET TABLE</div><div style="display:grid; grid-template-columns: 1fr 2fr 2fr 1fr; font-size:11px; font-weight:700; color:#64748b; font-family:'JetBrains Mono'; padding-bottom:8px; border-bottom:1px solid #16202e;"><span>PROTOCOL</span><span>LOCAL ADDRESS</span><span>FOREIGN ADDRESS</span><span>STATUS</span></div>""")

    for sock in drill['sockets']:
        st_color = "#00f5c4" if sock['status'] == "LISTEN" else ("#38bdf8" if sock['status'] == "ESTABLISHED" else "#94a3b8")
        st.html(f"""<div style="display:grid; grid-template-columns: 1fr 2fr 2fr 1fr; font-size:13px; font-family:'JetBrains Mono'; padding:10px 0; border-bottom:1px solid #131b28;"><span style="color:#e2e8f0; font-weight:600;">{sock['protocol']}</span><span style="color:#94a3b8;">{sock['local']}</span><span style="color:#94a3b8;">{sock['foreign']}</span><span><span style="background:rgba(0,0,0,0.3); color:{st_color}; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:700;">{sock['status']}</span></span></div>""")

    st.html("</div></div>")
