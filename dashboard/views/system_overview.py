"""System Overview Page for CogniOS Dashboard matching modern cyber-command design."""

import streamlit as st
import plotly.graph_objects as go
import dashboard.data_provider as dp
import psutil

@st.fragment(run_every=1)
def render():
    metrics = dp.get_live_system_metrics()
    
    cpu_pct = float(metrics.get('cpu_pct', 0.0))
    mem_pct = float(metrics.get('memory_pct', 0.0))
    mem_used = float(metrics.get('memory_used_gb', 0.0))
    mem_total = float(metrics.get('memory_total_gb', 0.0))
    mem_avail = max(0.0, round(mem_total - mem_used, 1))
    
    disk_read = float(metrics.get('disk_read_mb', 0.0))
    disk_write = float(metrics.get('disk_write_mb', 0.0))
    total_disk_io = round(disk_read + disk_write, 1)

    net_in = float(metrics.get('net_in_mb', 0.0))
    net_out = float(metrics.get('net_out_mb', 0.0))
    total_net = round(net_in + net_out, 2)
    iface = metrics.get('net_interface', 'eth0')
    total_procs = metrics.get('total_procs', len(psutil.pids()))
    cores_count = psutil.cpu_count(logical=True) or 8

    # Dynamic CPU status badge & color
    if cpu_pct > 85:
        cpu_status, cpu_badge_bg, cpu_badge_fg = "CRITICAL", "rgba(239, 68, 68, 0.15)", "#ef4444"
    elif cpu_pct > 60:
        cpu_status, cpu_badge_bg, cpu_badge_fg = "ELEVATED", "rgba(245, 158, 11, 0.15)", "#f59e0b"
    else:
        cpu_status, cpu_badge_bg, cpu_badge_fg = "OPTIMAL", "rgba(0, 245, 196, 0.12)", "#00f5c4"

    # Memory status badge & color
    if mem_pct > 88:
        mem_status, mem_badge_bg, mem_badge_fg = "HIGH", "rgba(239, 68, 68, 0.15)", "#ef4444"
    elif mem_pct > 70:
        mem_status, mem_badge_bg, mem_badge_fg = "MODERATE", "rgba(56, 189, 248, 0.15)", "#38bdf8"
    else:
        mem_status, mem_badge_bg, mem_badge_fg = "HEALTHY", "rgba(0, 245, 196, 0.12)", "#00f5c4"

    # ---------------------------------------------------------
    # 1. Header Banner
    # ---------------------------------------------------------
    st.html(f"""
        <div class="cognios-header-banner">
            <div>
                <h1 class="cognios-header-title">
                    <span style="color:#00f5c4;"><i class="fa-solid fa-satellite-dish"></i></span> Live Telemetry
                </h1>
                <p class="cognios-header-sub">
                    HOST TELEMETRY PIPELINE // 1.0s SAMPLING // {cores_count} LOGICAL CORES
                </p>
            </div>
            <div class="cognios-header-badges">
                <span class="cognios-badge-pill">
                    <span class="pulse-green"></span> REAL-TIME KERNEL POLLING
                </span>
            </div>
        </div>
    """)

    # ---------------------------------------------------------
    # 2. Key Metrics Grid (4 Hero Cards)
    # ---------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        load1 = metrics.get('load_avg1', 0.0)
        load5 = metrics.get('load_avg5', 0.0)
        load15 = metrics.get('load_avg15', 0.0)
        st.html(f"""
            <div class="cognios-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                    <span style="color:#94a3b8; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; font-family:'JetBrains Mono';">CPU Load</span>
                    <span style="color:#00f5c4; font-size:15px;"><i class="fa-solid fa-microchip"></i></span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:baseline; margin: 4px 0 8px 0;">
                    <span class="cognios-metric-val">{int(cpu_pct)}<span style="font-size:20px; font-weight:600; color:#64748b;">%</span></span>
                    <span style="background:{cpu_badge_bg}; color:{cpu_badge_fg}; border:1px solid {cpu_badge_fg}; border-radius:6px; padding:2px 8px; font-size:10.5px; font-weight:800; font-family:'JetBrains Mono';">{cpu_status}</span>
                </div>
                <div style="background:#131c2a; height:5px; border-radius:3px; overflow:hidden; margin-bottom:10px;">
                    <div style="background:linear-gradient(90deg, #00f5c4 0%, {cpu_badge_fg} 100%); width:{min(100.0, cpu_pct)}%; height:100%; transition: width 0.3s ease;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; font-family:'JetBrains Mono';">
                    <span>Load: <strong style="color:#cbd5e1;">{load1}</strong>, {load5}, {load15}</span>
                </div>
            </div>
        """)

    with c2:
        st.html(f"""
            <div class="cognios-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                    <span style="color:#94a3b8; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; font-family:'JetBrains Mono';">Memory RAM</span>
                    <span style="color:#38bdf8; font-size:15px;"><i class="fa-solid fa-memory"></i></span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:baseline; margin: 4px 0 8px 0;">
                    <span class="cognios-metric-val" style="color:#38bdf8;">{int(mem_pct)}<span style="font-size:20px; font-weight:600; color:#64748b;">%</span></span>
                    <span style="background:{mem_badge_bg}; color:{mem_badge_fg}; border:1px solid {mem_badge_fg}; border-radius:6px; padding:2px 8px; font-size:10.5px; font-weight:800; font-family:'JetBrains Mono';">{mem_status}</span>
                </div>
                <div style="background:#131c2a; height:5px; border-radius:3px; overflow:hidden; margin-bottom:10px;">
                    <div style="background:linear-gradient(90deg, #38bdf8 0%, #00f5c4 100%); width:{min(100.0, mem_pct)}%; height:100%; transition: width 0.3s ease;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; font-family:'JetBrains Mono';">
                    <span>Used: <strong style="color:#cbd5e1;">{mem_used:.1f}G</strong> / {mem_total:.1f}G</span>
                    <span style="color:#94a3b8;">Free: {mem_avail:.1f}G</span>
                </div>
            </div>
        """)

    with c3:
        st.html(f"""
            <div class="cognios-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                    <span style="color:#94a3b8; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; font-family:'JetBrains Mono';">Storage I/O</span>
                    <span style="color:#f59e0b; font-size:15px;"><i class="fa-solid fa-hard-drive"></i></span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:baseline; margin: 4px 0 8px 0;">
                    <span class="cognios-metric-val" style="color:#f59e0b;">{total_disk_io}<span style="font-size:16px; font-weight:600; color:#64748b;"> MB/s</span></span>
                    <span style="background:rgba(245, 158, 11, 0.12); color:#f59e0b; border:1px solid #f59e0b; border-radius:6px; padding:2px 8px; font-size:10.5px; font-weight:800; font-family:'JetBrains Mono';">DISK</span>
                </div>
                <div style="background:#131c2a; height:5px; border-radius:3px; overflow:hidden; margin-bottom:10px;">
                    <div style="background:#f59e0b; width:{min(100.0, total_disk_io * 8)}%; height:100%; transition: width 0.3s ease;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; font-family:'JetBrains Mono';">
                    <span>↓ R: <strong style="color:#38bdf8;">{disk_read:.1f}</strong> MB/s</span>
                    <span>↑ W: <strong style="color:#f59e0b;">{disk_write:.1f}</strong> MB/s</span>
                </div>
            </div>
        """)

    with c4:
        st.html(f"""
            <div class="cognios-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                    <span style="color:#94a3b8; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; font-family:'JetBrains Mono';">Network</span>
                    <span style="color:#c084fc; font-size:15px;"><i class="fa-solid fa-network-wired"></i></span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:baseline; margin: 4px 0 8px 0;">
                    <span class="cognios-metric-val" style="color:#c084fc;">{total_net}<span style="font-size:16px; font-weight:600; color:#64748b;"> Mbps</span></span>
                    <span style="background:rgba(192, 132, 252, 0.12); color:#c084fc; border:1px solid #c084fc; border-radius:6px; padding:2px 8px; font-size:10.5px; font-weight:800; font-family:'JetBrains Mono';">NET</span>
                </div>
                <div style="background:#131c2a; height:5px; border-radius:3px; overflow:hidden; margin-bottom:10px;">
                    <div style="background:#c084fc; width:{min(100.0, total_net * 12)}%; height:100%; transition: width 0.3s ease;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; font-family:'JetBrains Mono';">
                    <span>▲ In: <strong style="color:#00f5c4;">{net_in:.2f}</strong></span>
                    <span>▼ Out: <strong style="color:#c084fc;">{net_out:.2f}</strong></span>
                </div>
            </div>
        """)

    # ---------------------------------------------------------
    # 3. Main Operational Deck (Trends + Process Monitor)
    # ---------------------------------------------------------
    col_left, col_right = st.columns([1.9, 1.1])

    with col_left:
        st.html(f"""
            <div style="background:linear-gradient(180deg, #0e1524 0%, #080c14 100%); border:1px solid rgba(255,255,255,0.06); border-radius:14px; padding:18px 20px 10px 20px; margin-bottom:18px; box-shadow:0 8px 28px rgba(0,0,0,0.45);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="color:#00f5c4; font-size:16px;"><i class="fa-solid fa-chart-line"></i></span>
                        <h3 style="margin:0; font-size:16px; font-weight:700; color:#ffffff; letter-spacing:-0.3px;">Resource Trends</h3>
                        <span style="background:rgba(255,255,255,0.05); color:#64748b; border-radius:4px; padding:2px 6px; font-size:10.5px; font-family:'JetBrains Mono';">40s WINDOW</span>
                    </div>
                    <div style="display:flex; gap:12px; font-size:11.5px; font-family:'JetBrains Mono'; font-weight:700;">
                        <span style="background:rgba(0,245,196,0.1); color:#00f5c4; border:1px solid rgba(0,245,196,0.25); border-radius:6px; padding:3px 10px;">● CPU: {cpu_pct:.1f}%</span>
                        <span style="background:rgba(56,189,248,0.1); color:#38bdf8; border:1px solid rgba(56,189,248,0.25); border-radius:6px; padding:3px 10px;">● RAM: {mem_pct:.1f}%</span>
                    </div>
                </div>
        """)

        history_df = dp.get_telemetry_history(40)

        fig = go.Figure()
        
        # RAM area + line trace
        fig.add_trace(go.Scatter(
            x=history_df['timestamp'],
            y=history_df['ram'],
            mode='lines',
            name='RAM',
            line=dict(color='#38bdf8', width=2.5, shape='spline', smoothing=0.7),
            fill='tozeroy',
            fillcolor='rgba(56, 189, 248, 0.05)',
            hovertemplate='<b>RAM:</b> %{y:.1f}%<extra></extra>'
        ))

        # CPU area + line trace
        fig.add_trace(go.Scatter(
            x=history_df['timestamp'],
            y=history_df['cpu'],
            mode='lines',
            name='CPU',
            line=dict(color='#00f5c4', width=2.5, shape='spline', smoothing=0.7),
            fill='tozeroy',
            fillcolor='rgba(0, 245, 196, 0.09)',
            hovertemplate='<b>CPU:</b> %{y:.1f}%<extra></extra>'
        ))

        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=35, r=15, t=10, b=30),
            height=310,
            showlegend=False,
            hovermode="x unified",
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(255, 255, 255, 0.04)',
                zeroline=False,
                nticks=6,
                tickangle=0,
                tickfont=dict(color='#64748b', size=10, family='JetBrains Mono')
            ),
            yaxis=dict(
                range=[0, 100],
                showgrid=True,
                gridcolor='rgba(255, 255, 255, 0.04)',
                zeroline=False,
                ticksuffix="%",
                tickfont=dict(color='#64748b', size=10, family='JetBrains Mono')
            )
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'responsive': True})
        st.html("</div>")

    with col_right:
        procs = dp.get_top_processes_list(6)
        rows_html = ""
        for p in procs:
            p_cpu = float(p.get('cpu', 0.0))
            p_ram = float(p.get('ram', 0.0))
            
            if p_cpu > 35:
                c_bg, c_fg = "rgba(239, 68, 68, 0.18)", "#ef4444"
            elif p_cpu > 15:
                c_bg, c_fg = "rgba(245, 158, 11, 0.18)", "#f59e0b"
            elif p_cpu > 3:
                c_bg, c_fg = "rgba(0, 245, 196, 0.12)", "#00f5c4"
            else:
                c_bg, c_fg = "transparent", "#94a3b8"

            p_name = p.get('name', 'unknown')
            disp_name = (p_name[:14] + "..") if len(p_name) > 16 else p_name

            rows_html += f"""
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:11.5px; padding:7px 4px; border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono';">
                    <span style="width:55px; color:#64748b;">{p['pid']}</span>
                    <span style="flex:1; color:#e2e8f0; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="{p_name}">{disp_name}</span>
                    <span style="width:58px; text-align:right;">
                        <span style="background:{c_bg}; color:{c_fg}; border-radius:4px; padding:1px 6px; font-weight:700;">{p_cpu:.1f}%</span>
                    </span>
                    <span style="width:52px; text-align:right; color:#94a3b8;">{p_ram:.1f}%</span>
                </div>
            """

        st.html(f"""
            <div style="background:linear-gradient(180deg, #0e1524 0%, #080c14 100%); border:1px solid rgba(255,255,255,0.06); border-radius:14px; padding:18px 20px; margin-bottom:18px; box-shadow:0 8px 28px rgba(0,0,0,0.45);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="color:#38bdf8; font-size:16px;"><i class="fa-solid fa-list-check"></i></span>
                        <h3 style="margin:0; font-size:16px; font-weight:700; color:#ffffff; letter-spacing:-0.3px;">Process Monitor</h3>
                    </div>
                    <span style="color:#64748b; font-size:11px; font-family:'JetBrains Mono'; font-weight:600;">{total_procs} TASKS</span>
                </div>
                <div class="cognios-table-container">
                    <div style="min-width:260px;">
                        <div style="display:flex; justify-content:space-between; font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase; padding:6px 4px; border-bottom:1px solid rgba(255,255,255,0.08); font-family:'JetBrains Mono';">
                            <span style="width:55px;">PID</span>
                            <span style="flex:1;">PROCESS NAME</span>
                            <span style="width:58px; text-align:right;">CPU %</span>
                            <span style="width:52px; text-align:right;">RAM %</span>
                        </div>
                        {rows_html}
                    </div>
                </div>
            </div>
        """)

        with st.expander("🔍 View Extended Process Table (Top 20)", expanded=False):
            all_procs = dp.get_top_processes_list(20)
            if all_procs:
                st.dataframe(
                    all_procs,
                    column_order=["pid", "name", "cpu", "ram", "status"],
                    column_config={
                        "pid": st.column_config.NumberColumn("PID", format="%d"),
                        "name": st.column_config.TextColumn("Process Name"),
                        "cpu": st.column_config.ProgressColumn("CPU %", min_value=0, max_value=100, format="%.1f%%"),
                        "ram": st.column_config.ProgressColumn("RAM %", min_value=0, max_value=100, format="%.1f%%"),
                        "status": st.column_config.TextColumn("Status"),
                    },
                    hide_index=True,
                    use_container_width=True
                )

        st.html("</div>")
