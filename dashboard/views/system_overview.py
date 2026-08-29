"""System Overview Page for CogniOS Dashboard matching Stitch design."""

import streamlit as st
import plotly.graph_objects as go
import dashboard.data_provider as dp
import config

@st.fragment(run_every=1)
def render():
    st.html("""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;"><div><h1 style="margin:0; font-size: 28px; font-weight: 800; color: #ffffff;">Live Telemetry</h1><p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px;">System observability matrix initialized.</p></div></div>""")

    metrics = dp.get_live_system_metrics()

    # --- Dynamic CPU status badge ---
    cpu_pct = metrics['cpu_pct']
    if cpu_pct > 85:
        cpu_status, badge_color = "CRITICAL", "#ef4444"
    elif cpu_pct > 60:
        cpu_status, badge_color = "ELEVATED", "#f59e0b"
    else:
        cpu_status, badge_color = "NORMAL", "#00f5c4"

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.html(f"""<div class="cognios-card"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;"><span style="color:#94a3b8; font-size:13px; font-weight:600;">CPU Usage %</span><span style="color:#00f5c4;"><i class="fa-solid fa-microchip"></i></span></div><div class="cognios-metric-val">{int(metrics['cpu_pct'])}%</div><div style="margin-top: 12px; display:flex; justify-content:space-between; align-items:center;"><span style="background:rgba(0,0,0,0.2); color:{badge_color}; border:1px solid {badge_color}; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:700; font-family:'JetBrains Mono';">{cpu_status}</span><span style="font-size:12px; color:#64748b; font-family:'JetBrains Mono';">Load: {metrics['load_avg1']}, {metrics['load_avg5']}, {metrics['load_avg15']}</span></div></div>""")

    with c2:
        st.html(f"""<div class="cognios-card"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;"><span style="color:#94a3b8; font-size:13px; font-weight:600;">Memory Usage %</span><span style="color:#00f5c4;"><i class="fa-solid fa-memory"></i></span></div><div class="cognios-metric-val">{int(metrics['memory_pct'])}%</div><div style="margin-top: 12px; font-size:12px; color:#94a3b8; font-family:'JetBrains Mono';">{metrics['memory_used_gb']}GB / {metrics['memory_total_gb']}GB</div><div style="background:#1a2436; height:6px; border-radius:3px; margin-top:8px; overflow:hidden;"><div style="background:#00f5c4; width:{metrics['memory_pct']}%; height:100%;"></div></div></div>""")

    with c3:
        st.html(f"""<div class="cognios-card"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;"><span style="color:#94a3b8; font-size:13px; font-weight:600;">Disk I/O</span><span style="color:#f59e0b;"><i class="fa-solid fa-hard-drive"></i></span></div><div style="margin-top: 4px;"><div style="display:flex; justify-content:space-between; font-size:14px; margin-bottom:4px;"><span style="color:#64748b;">↓ Read</span><span style="color:#f8fafc; font-weight:600; font-family:'JetBrains Mono';">{metrics['disk_read_mb']} <span style="font-size:11px; color:#64748b;">MB/s</span></span></div><div style="display:flex; justify-content:space-between; font-size:14px;"><span style="color:#64748b;">↑ Write</span><span style="color:#f8fafc; font-weight:600; font-family:'JetBrains Mono';">{metrics['disk_write_mb']} <span style="font-size:11px; color:#64748b;">MB/s</span></span></div></div></div>""")

    with c4:
        st.html(f"""<div class="cognios-card"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;"><span style="color:#94a3b8; font-size:13px; font-weight:600;">Network Traffic</span><span style="color:#38bdf8;"><i class="fa-solid fa-network-wired"></i></span></div><div style="margin-top: 4px;"><div style="display:flex; justify-content:space-between; font-size:14px; margin-bottom:4px;"><span style="color:#64748b;">▲ In</span><span style="color:#f8fafc; font-weight:600; font-family:'JetBrains Mono';">{metrics['net_in_mb']} <span style="font-size:11px; color:#64748b;">Mbps</span></span></div><div style="display:flex; justify-content:space-between; font-size:14px; margin-bottom:6px;"><span style="color:#64748b;">▼ Out</span><span style="color:#f8fafc; font-weight:600; font-family:'JetBrains Mono';">{metrics['net_out_mb']} <span style="font-size:11px; color:#64748b;">Mbps</span></span></div><div style="font-size:11px; color:#00f5c4; font-family:'JetBrains Mono';">● Link Active ({metrics['net_interface']})</div></div></div>""")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.html("""<div style="background:#0d121c; border-radius:14px; padding:22px; margin-bottom:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;"><h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Resource Trends</h3><div style="display:flex; gap:16px; font-size:12px; font-family:'JetBrains Mono';"><span style="color:#e2e8f0;">— CPU</span><span style="color:#00f5c4;">— RAM</span></div></div>""")

        history_df = dp.get_telemetry_history(40)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=history_df['timestamp'],
            y=history_df['cpu'],
            mode='lines',
            name='CPU',
            line=dict(color='#cbd5e1', width=2),
            hovertemplate='%{y:.1f}%'
        ))
        fig.add_trace(go.Scatter(
            x=history_df['timestamp'],
            y=history_df['ram'],
            mode='lines',
            name='RAM',
            line=dict(color='#00f5c4', width=2),
            hovertemplate='%{y:.1f}%'
        ))

        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=30, r=20, t=10, b=30),
            height=300,
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor='#151d2a', zeroline=False, tickfont=dict(color='#64748b', size=10)),
            yaxis=dict(range=[0, 100], showgrid=True, gridcolor='#151d2a', zeroline=False, tickfont=dict(color='#64748b', size=10))
        )
        st.plotly_chart(fig, use_container_width=True)
        st.html("</div>")

    with col_right:
        st.html("""<div style="background:#0d121c; border-radius:14px; padding:22px; margin-bottom:20px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; align-items:center; gap:8px; margin-bottom:16px;"><span style="color:#94a3b8;"><i class="fa-solid fa-list-check"></i></span><h3 style="margin:0; font-size:16px; font-weight:700; color:#ffffff;">Process Monitor</h3></div>""")

        procs = dp.get_top_processes_list(6)

        st.html("""<div style="display:flex; justify-content:space-between; font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase; padding-bottom:8px; border-bottom:1px solid #16202e; font-family:'JetBrains Mono';"><span style="width:50px;">PID</span><span style="width:110px;">NAME</span><span style="width:50px; text-align:right;">CPU%</span><span style="width:50px; text-align:right;">RAM%</span></div>""")

        for p in procs:
            cpu_color = "#00f5c4" if p['cpu'] > 10 else "#f8fafc"
            ram_color = "#00f5c4" if p['ram'] > 10 else "#94a3b8"
            st.html(f"""<div style="display:flex; justify-content:space-between; font-size:13px; padding:8px 0; border-bottom:1px solid #131b28; font-family:'JetBrains Mono';"><span style="width:50px; color:#64748b;">{p['pid']}</span><span style="width:110px; color:#e2e8f0; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">{p['name']}</span><span style="width:50px; text-align:right; color:{cpu_color}; font-weight:600;">{p['cpu']}</span><span style="width:50px; text-align:right; color:{ram_color};">{p['ram']}</span></div>""")

        st.html("""<div style="margin-top:16px; text-align:center;"><button style="background:#141c2b; border:none; color:#94a3b8; border-radius:6px; padding:8px 16px; font-size:12px; font-family:'JetBrains Mono'; cursor:pointer; width:100%;">View All Processes</button></div></div>""")
