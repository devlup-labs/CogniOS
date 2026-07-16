DB_PATH = "cognios_telemetry.db"

OS_DOCTOR_DB_PATH = "os_doctor.db"

BLACKBOX_DB_PATH         = "blackbox/blackbox.db"
BLACKBOX_WINDOW_SEC = 1800  # 30 minutes
BLACKBOX_WARMUP_SEC      = 60     # wait before detection starts
BLACKBOX_CRASH_GAP_SEC = 30   # SIGKILL-only fallback, not the primary check

BLACKBOX_Z_THRESHOLD     = 2.8    # std deviations for spike
BLACKBOX_SLOPE_THRESHOLD = 0.003  # %/sec rise = suspicious
BLACKBOX_SUSTAINED_SEC   = 30     # spike must last this long
BLACKBOX_SUSTAINED_RATIO = 0.6    # 60% readings above threshold
BLACKBOX_TREND_WINDOW    = 600    # 10 min for slope calculation