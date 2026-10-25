"""OS Doctor AI Anomaly Diagnostics View matching modern cyber-command design."""

import streamlit as st
import plotly.graph_objects as go
import dashboard.data_provider as dp
import config


@st.fragment(run_every=2)
def render():
    diag_score = dp.get_os_doctor_anomaly_score()
    hogs = dp.get_resource_hogs_heatmap()
    stats = dp.get_os_doctor_summary_stats()

    score_val = diag_score.get('score', 12)
    score_status = diag_score.get('status', 'LOW RISK')

    # Color scheme based on anomaly severity
    if score_val > 75 or "HIGH" in score_status:
        score_color = "#ef4444"
        score_bg = "rgba(239, 68, 68, 0.15)"
        bar_color = "#ef4444"
    elif score_val > 45 or "ELEVATED" in score_status:
        score_color = "#f59e0b"
        score_bg = "rgba(245, 158, 11, 0.15)"
        bar_color = "#f59e0b"
    else:
        score_color = "#00f5c4"
        score_bg = "rgba(0, 245, 196, 0.12)"
        bar_color = "#00f5c4"

    # ---------------------------------------------------------
    # 1. Header Banner
    # ---------------------------------------------------------
    st.html(f"""
        <div class="cognios-header-banner">
            <div>
                <h1 class="cognios-header-title">
                    <span style="color:#00f5c4;"><i class="fa-solid fa-stethoscope"></i></span> OS Doctor AI Diagnostics
                </h1>
                <p class="cognios-header-sub">
                    ISOLATION FOREST ANOMALY SENTINEL // OLLAMA & GROQ REASONING ENGINE
                </p>
            </div>
            <div class="cognios-header-badges">
                <span class="cognios-badge-pill" style="background:{score_bg}; color:{score_color}; border-color:{score_color}; box-shadow:0 0 16px {score_bg};">
                    <span class="pulse-green" style="background-color:{score_color};"></span> {score_status}
                </span>
            </div>
        </div>
    """)

    # ---------------------------------------------------------
    # 2. Anomaly Score Gauge & Resource Hogs Deck
    # ---------------------------------------------------------
    col_gauge, col_heatmap = st.columns([1.1, 1.9])

    with col_gauge:
        st.html(f"""
            <div class="cognios-card" style="height:100%; display:flex; flex-direction:column; justify-content:space-between;">
                <div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="color:#94a3b8; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; font-family:'JetBrains Mono';">Anomaly Index</span>
                        <span style="color:{score_color}; font-size:15px;"><i class="fa-solid fa-shield-halved"></i></span>
                    </div>
                    <div style="text-align:center; padding: 4px 0;">
        """)

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score_val,
            number={'suffix': "/100", 'font': {'size': 38, 'color': '#ffffff', 'family': 'JetBrains Mono'}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#64748b"},
                'bar': {'color': bar_color, 'thickness': 0.28},
                'bgcolor': "rgba(255, 255, 255, 0.03)",
                'bordercolor': "rgba(255, 255, 255, 0.06)",
                'steps': [
                    {'range': [0, 45], 'color': 'rgba(0, 245, 196, 0.12)'},
                    {'range': [45, 75], 'color': 'rgba(245, 158, 11, 0.12)'},
                    {'range': [75, 100], 'color': 'rgba(239, 68, 68, 0.15)'}
                ]
            }
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=190,
            margin=dict(l=15, r=15, t=15, b=5)
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'responsive': True})

        st.html(f"""
                    </div>
                </div>
                <div style="border-top:1px solid rgba(255,255,255,0.06); padding-top:12px; margin-top:6px; display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:11px; color:#64748b; font-family:'JetBrains Mono';">MODEL: i-Forest (L4)</span>
                    <span style="background:{score_bg}; color:{score_color}; font-size:11px; font-weight:800; font-family:'JetBrains Mono'; padding:3px 10px; border-radius:6px; border:1px solid {score_color};">{score_status}</span>
                </div>
            </div>
        """)

    with col_heatmap:
        hogs_rows_html = ""
        for hog in hogs[:6]:
            impact = hog.get('impact', 0.0)
            if impact > 30:
                h_bg, h_fg, h_lbl = "rgba(239, 68, 68, 0.18)", "#ef4444", "CRITICAL"
            elif impact > 15:
                h_bg, h_fg, h_lbl = "rgba(245, 158, 11, 0.18)", "#f59e0b", "ELEVATED"
            else:
                h_bg, h_fg, h_lbl = "rgba(0, 245, 196, 0.12)", "#00f5c4", "NORMAL"

            p_name = hog.get('name', 'unknown')
            disp_name = (p_name[:12] + "..") if len(p_name) > 14 else p_name

            hogs_rows_html += f"""
                <div style="display:grid; grid-template-columns: 2.2fr 0.9fr 0.9fr 0.9fr 1.1fr; font-size:11.5px; font-family:'JetBrains Mono'; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.04); align-items:center;">
                    <span style="color:#ffffff; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="{p_name}">{disp_name}</span>
                    <span style="color:#38bdf8;">{hog['pid']}</span>
                    <span style="text-align:right; color:#ffffff; font-weight:600;">{hog['cpu']}%</span>
                    <span style="text-align:right; color:#94a3b8;">{hog['ram']}%</span>
                    <span style="text-align:right;">
                        <span style="background:{h_bg}; color:{h_fg}; border-radius:4px; padding:2px 8px; font-size:10px; font-weight:800;">{h_lbl}</span>
                    </span>
                </div>
            """

        st.html(f"""
            <div class="cognios-card" style="height:100%;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="color:#f59e0b; font-size:15px;"><i class="fa-solid fa-fire-flame-curved"></i></span>
                        <h3 style="margin:0; font-size:15px; font-weight:700; color:#ffffff; letter-spacing:-0.3px;">Top Resource Hogs</h3>
                    </div>
                    <div style="display:flex; gap:10px; font-size:10.5px; font-family:'JetBrains Mono'; font-weight:700;">
                        <span style="color:#00f5c4;">■ NORMAL</span>
                        <span style="color:#f59e0b;">■ ELEVATED</span>
                        <span style="color:#ef4444;">■ CRITICAL</span>
                    </div>
                </div>
                <div class="cognios-table-container">
                    <div style="min-width: 300px;">
                        <div style="display:grid; grid-template-columns: 2.2fr 0.9fr 0.9fr 0.9fr 1.1fr; font-size:10px; font-weight:700; color:#64748b; font-family:'JetBrains Mono'; padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:6px;">
                            <span>PROCESS</span>
                            <span>PID</span>
                            <span style="text-align:right;">CPU %</span>
                            <span style="text-align:right;">RAM %</span>
                            <span style="text-align:right;">RISK</span>
                        </div>
                        {hogs_rows_html}
                    </div>
                </div>
            </div>
        """)

    # ---------------------------------------------------------
    # 3. KPI Summary Deck
    # ---------------------------------------------------------
    st.markdown("<div style='margin-top:18px;'></div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.html(f"""
            <div class="cognios-card" style="padding:16px 18px; text-align:center;">
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700; text-transform:uppercase;">Total Diagnoses</div>
                <div style="font-size:26px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono'; margin-top:4px;">{stats['total_diagnoses']}</div>
                <div style="font-size:11px; color:#00f5c4; font-family:'JetBrains Mono'; margin-top:2px;">● Incident History</div>
            </div>
        """)
    with k2:
        st.html(f"""
            <div class="cognios-card" style="padding:16px 18px; text-align:center;">
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700; text-transform:uppercase;">Critical & High</div>
                <div style="font-size:26px; font-weight:800; color:#ef4444; font-family:'JetBrains Mono'; margin-top:4px;">{stats['critical_high_count']}</div>
                <div style="font-size:11px; color:#ef4444; font-family:'JetBrains Mono'; margin-top:2px;">● Needs Attention</div>
            </div>
        """)
    with k3:
        st.html(f"""
            <div class="cognios-card" style="padding:16px 18px; text-align:center;">
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700; text-transform:uppercase;">AI Confidence</div>
                <div style="font-size:26px; font-weight:800; color:#00f5c4; font-family:'JetBrains Mono'; margin-top:4px;">{stats['avg_confidence']}%</div>
                <div style="font-size:11px; color:#38bdf8; font-family:'JetBrains Mono'; margin-top:2px;">● Mean Certainty</div>
            </div>
        """)
    with k4:
        st.html(f"""
            <div class="cognios-card" style="padding:16px 18px; text-align:center;">
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700; text-transform:uppercase;">Latest Incident</div>
                <div style="font-size:13.5px; font-weight:700; color:#38bdf8; font-family:'JetBrains Mono'; margin-top:8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{stats['latest_issue']}">{stats['latest_issue']}</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; margin-top:4px;">● {stats.get('provider', 'LLM Sentinel')}</div>
            </div>
        """)

    # ---------------------------------------------------------
    # 4. AI Diagnostic Stream & Human-Readable Explanations
    # ---------------------------------------------------------
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.html("""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="color:#00f5c4; font-size:18px;"><i class="fa-solid fa-brain"></i></span>
                    <h3 style="margin:0; font-size:17px; font-weight:700; color:#ffffff;">AI Diagnostic Stream & Forensic Insights</h3>
                </div>
                <span style="background:rgba(0, 245, 196, 0.12); color:#00f5c4; border:1px solid rgba(0,245,196,0.3); border-radius:6px; padding:3px 10px; font-size:11px; font-weight:700; font-family:'JetBrains Mono';">LIVE ANOMALY REASONING</span>
            </div>
        """)

        # Filter & Search Controls in unified bar
        f1, f2 = st.columns([1, 2.5])
        with f1:
            sev_filter = st.selectbox("Filter by Severity", ["All", "High", "Medium", "Low"], key="os_doc_sev_filter", label_visibility="collapsed")
        with f2:
            search_query = st.text_input("Search Diagnoses", placeholder="Search by issue, cause, process, or remediation...", key="os_doc_search_query", label_visibility="collapsed")

        diagnoses = dp.get_os_doctor_diagnoses(limit=15, severity_filter=sev_filter, search_query=search_query)

        if not diagnoses:
            st.info("No AI diagnoses matching filter criteria. Telemetry operating within baseline thresholds.")
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

                st.html(f"""
                    <div style="background:linear-gradient(180deg, #101726 0%, #0a0f19 100%); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:16px 18px; margin-bottom:12px; box-shadow:0 4px 16px rgba(0,0,0,0.3);">
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:8px; margin-bottom:10px;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <span style="background:{badge_bg}; color:{badge_fg}; font-size:10.5px; font-weight:800; font-family:'JetBrains Mono'; padding:2px 8px; border-radius:4px; border:1px solid {badge_fg};">{sev_str}</span>
                                <span style="font-size:15px; font-weight:700; color:#ffffff;">{diag['issue']}</span>
                            </div>
                            <div style="display:flex; align-items:center; gap:12px; font-size:11.5px; font-family:'JetBrains Mono';">
                                <span style="color:#64748b;">{diag['created_at']}</span>
                                <span style="background:rgba(56, 189, 248, 0.12); color:#38bdf8; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid rgba(56,189,248,0.25);">{conf_pct}% Confidence</span>
                            </div>
                        </div>
                        <div style="margin-bottom:10px;">
                            <div style="font-size:10.5px; font-weight:700; color:#64748b; font-family:'JetBrains Mono'; text-transform:uppercase; margin-bottom:4px;">Causal Diagnosis</div>
                            <div style="font-size:13.5px; color:#e2e8f0; line-height:1.55; background:#070a12; padding:10px 14px; border-radius:8px; border-left:3px solid {badge_fg}; font-family:'Plus Jakarta Sans', sans-serif;">{diag['cause']}</div>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="font-size:10.5px; font-weight:700; color:#00f5c4; font-family:'JetBrains Mono';">ACTION:</span>
                            <span style="font-size:12px; color:#38bdf8; font-weight:600; font-family:'JetBrains Mono'; background:rgba(56, 189, 248, 0.08); padding:3px 10px; border-radius:4px; border:1px solid rgba(56,189,248,0.2);">{diag['suggested_action']}</span>
                        </div>
                    </div>
                """)

                with st.expander(f"🔍 Telemetry Snapshot & Metadata (Alert #{diag['alert_id']})"):
                    t1, t2 = st.columns(2)
                    with t1:
                        st.caption("Telemetry Vector")
                        st.json(diag['raw_metrics'])
                    with t2:
                        st.caption("Process Execution Context")
                        st.json(diag['metadata'])

    # ---------------------------------------------------------
    # 5. Layer 4 Process Deep-Inspection Card
    # ---------------------------------------------------------
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        hog_pids = [h['pid'] for h in hogs] if hogs else [1]
        
        c_title, c_picker = st.columns([2, 1], vertical_alignment="center")
        with c_title:
            st.html("""
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="color:#38bdf8; font-size:18px;"><i class="fa-solid fa-microscope"></i></span>
                    <h3 style="margin:0; font-size:17px; font-weight:700; color:#ffffff;">Layer 4 Process Deep Inspection</h3>
                </div>
            """)
        with c_picker:
            selected_pid = st.selectbox(
                "Target PID",
                options=hog_pids,
                format_func=lambda x: f"PID {x}: {next((h['name'] for h in hogs if h['pid'] == x), 'Process')}",
                key="os_doc_inspect_pid",
                label_visibility="collapsed"
            )

        drill = dp.get_process_drilldown(selected_pid)

        # Safe open_files string formatting (prevent format string crash on 'N/A')
        open_f = drill.get('open_files')
        open_files_str = f"{open_f:,}" if isinstance(open_f, int) else str(open_f or "N/A")

        d1, d2, d3 = st.columns(3)
        with d1:
            st.html(f"""
                <div style="background:linear-gradient(180deg, #101726 0%, #0a0f19 100%); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:16px;">
                    <div style="font-size:10.5px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700; text-transform:uppercase;">Open File Descriptors</div>
                    <div style="font-size:24px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono'; margin-top:4px;">
                        {open_files_str} <span style="font-size:11px; color:#00f5c4; font-weight:600;">FDs</span>
                    </div>
                    <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; margin-top:2px;">Process: {drill.get('name', 'N/A')}</div>
                </div>
            """)

        with d2:
            st.html(f"""
                <div style="background:linear-gradient(180deg, #101726 0%, #0a0f19 100%); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:16px;">
                    <div style="font-size:10.5px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700; text-transform:uppercase;">CPU Time ({drill.get('thread_count', 1)} Threads)</div>
                    <div style="font-size:13.5px; font-weight:700; color:#ffffff; font-family:'JetBrains Mono'; margin-top:6px; display:flex; gap:14px;">
                        <span>User: <strong style="color:#38bdf8;">{drill.get('user_time', 'N/A')}s</strong></span>
                        <span>Sys: <strong style="color:#f59e0b;">{drill.get('sys_time', 'N/A')}s</strong></span>
                    </div>
                    <div style="background:#131c2a; height:5px; border-radius:3px; margin-top:10px; display:flex; overflow:hidden;">
                        <div style="background:#38bdf8; width:70%; height:100%;"></div>
                        <div style="background:#f59e0b; width:30%; height:100%;"></div>
                    </div>
                </div>
            """)

        with d3:
            st.html(f"""
                <div style="background:linear-gradient(180deg, #101726 0%, #0a0f19 100%); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:16px;">
                    <div style="font-size:10.5px; color:#64748b; font-family:'JetBrains Mono'; font-weight:700; text-transform:uppercase;">Context Switches</div>
                    <div style="font-size:13.5px; font-weight:700; color:#ffffff; font-family:'JetBrains Mono'; margin-top:6px; display:flex; gap:14px;">
                        <span>Voluntary: <strong style="color:#00f5c4;">{drill.get('vol_ctx', 'N/A')}</strong></span>
                        <span>Involuntary: <strong style="color:#ef4444;">{drill.get('invol_ctx', 'N/A')}</strong></span>
                    </div>
                    <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; margin-top:6px;">Preemption Frequency Indicator</div>
                </div>
            """)

        # Socket Table
        sockets = drill.get('sockets', [])
        st.html("""
            <div style="margin-top:16px;">
                <div style="font-size:11px; font-weight:700; color:#64748b; font-family:'JetBrains Mono'; margin-bottom:8px; text-transform:uppercase;">Active Network Sockets</div>
                <div style="display:grid; grid-template-columns: 1fr 2.5fr 2.5fr 1.2fr; font-size:10.5px; font-weight:700; color:#64748b; font-family:'JetBrains Mono'; padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08);">
                    <span>PROTOCOL</span>
                    <span>LOCAL ENDPOINT</span>
                    <span>FOREIGN ENDPOINT</span>
                    <span style="text-align:right;">STATUS</span>
                </div>
        """)

        if not sockets:
            st.html("""<div style="padding:10px 0; font-size:12px; color:#64748b; font-family:'JetBrains Mono';">No active TCP/UDP internet sockets bound to this process.</div>""")
        else:
            for sock in sockets:
                st_color = "#00f5c4" if sock['status'] == "LISTEN" else ("#38bdf8" if sock['status'] == "ESTABLISHED" else "#94a3b8")
                st.html(f"""
                    <div style="display:grid; grid-template-columns: 1fr 2.5fr 2.5fr 1.2fr; font-size:12px; font-family:'JetBrains Mono'; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.04); align-items:center;">
                        <span style="color:#38bdf8; font-weight:700;">{sock['protocol']}</span>
                        <span style="color:#cbd5e1;">{sock['local']}</span>
                        <span style="color:#94a3b8;">{sock['foreign']}</span>
                        <span style="text-align:right;">
                            <span style="background:rgba(0,0,0,0.3); color:{st_color}; border:1px solid {st_color}; border-radius:4px; padding:2px 8px; font-size:10.5px; font-weight:700;">{sock['status']}</span>
                        </span>
                    </div>
                """)

        st.html("</div>")
