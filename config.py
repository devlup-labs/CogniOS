import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cognios_telemetry.db")
SLIDING_WIND_N = 120
BLACKBOX_DB_PATH         = "blackbox/blackbox.db"
BLACKBOX_WINDOW_SEC = 1800  # 30 minutes
BLACKBOX_WARMUP_SEC      = 60     # wait before detection starts
BLACKBOX_CRASH_GAP_SEC = 30   # SIGKILL-only fallback, not the primary check

BLACKBOX_Z_THRESHOLD     = 2.8    # std deviations for spike
BLACKBOX_SLOPE_THRESHOLD = 0.003  # %/sec rise = suspicious
BLACKBOX_SUSTAINED_SEC   = 30     # spike must last this long
BLACKBOX_SUSTAINED_RATIO = 0.6    # 60% readings above threshold
BLACKBOX_TREND_WINDOW    = 600    # 10 min for slope calculation

BLACKBOX_CPU_CRITICAL  = 90.0 # critical CPU usage threshold
BLACKBOX_MEM_CRITICAL  = 90.0 # critical memory usage threshold
BLACKBOX_ZOMBIE_LIMIT  = 10   # limit for zombie processes
BLACKBOX_TEMP_CRITICAL = 85.0 # critical temperature threshold
BLACKBOX_SWAP_CRITICAL = 80.0 # critical swap usage threshold