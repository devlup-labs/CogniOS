import os
import psutil

# =====================================================================
# COGNIOS PRODUCTION-GRADE CONFIGURATION
# =====================================================================

# 1. System-Wide Directory Anchors
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "cognios_telemetry.db"
DB_PATH = os.path.join(BASE_DIR, DB_NAME)

# 2. Clock Synchronization & Timing Windows
SAMPLING_INTERVAL = None   # Mandated None for stateless, non-blocking ticks 
TICK_DELAY = 1.0           # Pacing gap delta (Δt) passed to time.sleep() 

# 3. Dynamic Hardware Core Discovery
CPU_CORE_COUNT = psutil.cpu_count(logical=True)
CORE_COLUMNS = [f"core_{i}_pct" for i in range(CPU_CORE_COUNT)]

# 4. Defensive Ingestion Boundaries
TOP_PROCESS_LIMIT = 5      # Caps process_telemetry rows to the top 5 hogs

# 5. Machine Learning Sliding Windows (UNCOMMENTED FOR PIPELINE STABILITY)
BLACKBOX_RETENTION_MINS = 30  # Rolling crash-recorder flight window constraint 
FOCUSOS_WINDOW_SECS = 120     # 2-minute sliding array size for CNN heatmaps 
FOCUSOS_STEP_SECS = 30        # How frequently a workload classification triggers 