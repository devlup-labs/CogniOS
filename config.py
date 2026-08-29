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

# Blackbox config

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
BLACKBOX_DB_PATH = "blackbox/blackbox.db"
BLACKBOX_WINDOW_SEC = 1800  # 30 minutes
BLACKBOX_CRASH_GAP_SEC = 30   # SIGKILL-only fallback, not the primary check

# Alert / Telemetry thresholds
BLACKBOX_CPU_CRITICAL = 90.0
BLACKBOX_MEM_CRITICAL = 90.0
BLACKBOX_ZOMBIE_LIMIT = 10
BLACKBOX_TEMP_CRITICAL = 85.0
BLACKBOX_SWAP_CRITICAL = 80.0

