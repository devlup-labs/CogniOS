import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cognios_telemetry.db")
SLIDING_WIND_N = 30
AUTO_REFRESH = 2  # seconds between dashboard refreshes


# OS Doctor Config
OS_DOCTOR_DB_PATH = "os_doctor.db"
ALERTS_DB_PATH = "os_doctor/alerts.db"
ALERTS_TABLE_NAME = "alerts"
MODEL_PATH = "iso_forest_model.joblib"
SCALER_PATH = "scaler.joblib"

# FocusOS config
COMPILERS = ["gcc", "g++", "clang", "make", "ninja", "rustc", "javac"]
BROWSERS = ["chrome", "firefox", "brave", "msedge"]
CALLS = ["zoom", "teams", "slack", "discord", "skype", "webex"]
IDES = ["code", "code-insiders", "sublime", "vim", "nvim"]
GAMES = ["steam", "csgo", "dota2", "hl2_linux", "minecraft"]

# FocusOS Rule Engine Config
RULE_CPU_ACTIVE_THRESHOLD = 2.0   # process CPU% to be "relevant"
RULE_RAM_ACTIVE_THRESHOLD = 0.5   # process RAM% to be "relevant"
RULE_SYSTEM_CPU_CONTENTION = 35.0  # system CPU% before optimization triggers
RULE_ATTRIBUTION_THRESHOLD = 0.40  # workload must own >=40% of active CPU
RULE_PERSISTENCE_COUNT = 3     # consecutive cycles before CONFIRMED
RULE_COOLDOWN_SEC = 45    # seconds between policy changes
RULE_HISTORY_LEN = 8     # rolling history window size
RULE_MIN_EVIDENCE_SCORE = 1.5   # minimum combined evidence before considering
RULE_IDLE_CPU_THRESHOLD = 10.0  # system CPU% below which = IDLE
RULE_SCORE_WEIGHT_CPU = 0.55  # weight for CPU attribution in final score
RULE_SCORE_WEIGHT_RAM = 0.20  # weight for RAM attribution
RULE_SCORE_WEIGHT_EVIDENCE = 0.15  # weight for process evidence count
RULE_SCORE_WEIGHT_PERSISTENCE = 0.10  # weight for temporal persistence

# Blackbox config

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
BLACKBOX_DB_PATH = "blackbox/blackbox.db"
BLACKBOX_WINDOW_SEC = 1800  # 30 minutes
BLACKBOX_CRASH_GAP_SEC = 30   # SIGKILL-only fallback, not the primary check

# Alert / Telemetry thresholds
BLACKBOX_CPU_CRITICAL = 90.0
BLACKBOX_MEM_CRITICAL = 90.0
BLACKBOX_ZOMBIE_LIMIT = 10
BLACKBOX_TEMP_CRITICAL = 85.0
BLACKBOX_SWAP_CRITICAL = 80.0

