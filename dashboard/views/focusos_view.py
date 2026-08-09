"""FocusOS Workload Optimization Engine View matching Stitch design."""

import streamlit as st
import dashboard.data_provider as dp


def render():
    workload_data = dp.get_focusos_detected_workload()
    affinity_data = dp.get_processor_affinity_matrix()
    events = dp.get_focusos_events()

    st.html(f"""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;"><div><h1 style="margin:0; font-size: 28px; font-weight: 800; color: #ffffff; display:flex; align-items:center; gap:10px;"><span style="color:#00f5c4;"><i class="fa-solid fa-eye"></i></span> Workload Optimization Engine</h1><p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px; font-family: 'JetBrains Mono';">FocusOS Daemon // Process Affinity & Scheduling Control</p></div></div>""")

    col_target, col_opts = st.columns([2, 1])

    with col_target:
        p_boxes = "".join([f'<div style="background:rgba(0,245,196,0.08); border-radius:8px; padding:12px; text-align:center; color:#00f5c4; font-weight:700; font-family:\'JetBrains Mono\'; box-shadow:0 0 12px rgba(0,245,196,0.15);">P{c}</div>' for c in affinity_data['p_cores'][:8]])
        e_boxes = "".join([f'<div style="background:#131b28; border-radius:8px; padding:12px; text-align:center; color:#475569; font-weight:700; font-family:\'JetBrains Mono\';">E{i}</div>' for i in range(8)])

        st.html(f"""<div style="background:#0d121c; border-radius:14px; padding:24px; min-height: 380px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;"><div><h3 style="margin:0; font-size:20px; font-weight:700; color:#ffffff;">Target Workload</h3><p style="margin:2px 0 0 0; font-size:12px; color:#64748b;">Real-time resource allocation</p></div><div style="background: rgba(0, 245, 196, 0.12); color:#00f5c4; border-radius:6px; padding:6px 14px; font-size:12px; font-weight:700; font-family:\'JetBrains Mono\';">● ACTIVE STATE: {workload_data['workload']} ({workload_data['confidence']}% CONF)</div></div><div style="margin-top:24px;"><div style="font-size:12px; font-weight:700; color:#64748b; font-family:\'JetBrains Mono\'; text-transform:uppercase; margin-bottom:16px;">Processor Affinity Matrix</div><div style="margin-bottom:20px;"><div style="display:flex; justify-content:space-between; font-size:13px; color:#cbd5e1; margin-bottom:8px;"><span><strong style="color:#ffffff;">Performance Pool (P-Cores)</strong></span><span style="color:#00f5c4; font-family:\'JetBrains Mono\'; font-weight:600;">{affinity_data['p_active']}/{affinity_data['p_active']} Active</span></div><div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:10px;">{p_boxes}</div></div><div><div style="display:flex; justify-content:space-between; font-size:13px; color:#cbd5e1; margin-bottom:8px;"><span><strong style="color:#ffffff;">Efficiency Pool (E-Cores)</strong></span><span style="color:#64748b; font-family:\'JetBrains Mono\'; font-weight:600;">{affinity_data['e_active']}/8 Active</span></div><div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:10px;">{e_boxes}</div></div></div></div>""")

    with col_opts:
        st.html("""<div style="background:#0d121c; border-radius:14px; padding:24px; min-height: 380px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; align-items:center; gap:8px; margin-bottom:20px;"><span style="color:#94a3b8;"><i class="fa-solid fa-gears"></i></span><h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Active Optimizations</h3></div><div style="background:#131b28; border-radius:8px; padding:14px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;"><div><div style="font-size:12px; color:#94a3b8;">CPU Scheduler</div><div style="font-size:15px; font-weight:700; color:#ffffff; font-family:\'JetBrains Mono\'; margin-top:2px;">nice: -10</div></div><div style="background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:bold;"><i class="fa-solid fa-check"></i></div></div><div style="background:#131b28; border-radius:8px; padding:14px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;"><div><div style="font-size:12px; color:#94a3b8;">I/O Priority</div><div style="font-size:15px; font-weight:700; color:#ffffff; font-family:\'JetBrains Mono\'; margin-top:2px;">ionice: realtime</div></div><div style="background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:bold;"><i class="fa-solid fa-check"></i></div></div><div style="background:#131b28; border-radius:8px; padding:14px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;"><div><div style="font-size:12px; color:#94a3b8;">Network Queue</div><div style="font-size:15px; font-weight:700; color:#ffffff; font-family:\'JetBrains Mono\'; margin-top:2px;">tc fq_codel: ON</div></div><div style="background:rgba(0,245,196,0.15); color:#00f5c4; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:bold;"><i class="fa-solid fa-check"></i></div></div></div>""")
        if st.button("Override Settings", key="override_settings_btn", use_container_width=True):
            st.info("Override settings panel opened.")

    # Bottom Event Log
    st.html("""<div style="background:#0d121c; border-radius:14px; padding:24px; margin-top:24px; box-shadow:0 6px 24px rgba(0,0,0,0.3);"><div style="display:flex; align-items:center; gap:8px; margin-bottom:16px;"><span style="color:#94a3b8;"><i class="fa-solid fa-clock-rotate-left"></i></span><h3 style="margin:0; font-size:18px; font-weight:700; color:#ffffff;">Optimization Event Log</h3></div>""")

    for ev in events:
        badge_bg = "rgba(0,245,196,0.12)" if ev['type'] == "SCHED" else ("rgba(56,189,248,0.12)" if ev['type'] == "PRIO" else "rgba(245,158,11,0.12)")
        badge_fg = "#00f5c4" if ev['type'] == "SCHED" else ("#38bdf8" if ev['type'] == "PRIO" else "#f59e0b")

        st.html(f"""<div style="display:flex; align-items:center; gap:16px; padding:10px 0; border-bottom:1px solid #131b28; font-family:\'JetBrains Mono\'; font-size:13px;"><span style="color:#64748b;">{ev['time']}</span><span style="background:{badge_bg}; color:{badge_fg}; border-radius:4px; padding:2px 8px; font-weight:700; font-size:11px;">[{ev['type']}]</span><span style="color:#e2e8f0;">{ev['message']}</span></div>""")

    st.html("</div>")
