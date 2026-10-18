import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cognios_telemetry.db")
SLIDING_WIND_N = 120

# OS Doctor Config
# All paths are absolute (built from BASE_DIR) so they do not depend on the
# folder you run a script from.
OS_DOCTOR_DB_PATH = os.path.join(BASE_DIR, "os_doctor.db")
OS_DOCTOR_TRAIN_TABLE = "os_doctor_train_v2"
ALERTS_DB_PATH = os.path.join(BASE_DIR, "os_doctor", "alerts.db")
ALERTS_TABLE_NAME = "alerts"
OS_DOCTOR_MODELS_DIR = os.path.join(BASE_DIR, "os_doctor", "models")
MODEL_PATH = os.path.join(OS_DOCTOR_MODELS_DIR, "iso_forest_model.joblib")
SCALER_PATH = os.path.join(OS_DOCTOR_MODELS_DIR, "robust_scaler.joblib")

# Workload-specific baselines.
# Integer ID -> { name, table, model_path, scaler_path }
# 0 = Idle, 1 = Browsing, 2 = Coding, 3 = Gaming
WORKLOADS = {
    0: {
        "name": "idle",
        "table": "os_doctor_train_i",
        "model_path": os.path.join(OS_DOCTOR_MODELS_DIR, "iso_forest_idle.joblib"),
        "scaler_path": os.path.join(OS_DOCTOR_MODELS_DIR, "scaler_idle.joblib"),
    },
    1: {
        "name": "browsing",
        "table": "os_doctor_train_b",
        "model_path": os.path.join(OS_DOCTOR_MODELS_DIR, "iso_forest_browsing.joblib"),
        "scaler_path": os.path.join(OS_DOCTOR_MODELS_DIR, "scaler_browsing.joblib"),
    },
    2: {
        "name": "coding",
        "table": "os_doctor_train_c",
        "model_path": os.path.join(OS_DOCTOR_MODELS_DIR, "iso_forest_coding.joblib"),
        "scaler_path": os.path.join(OS_DOCTOR_MODELS_DIR, "scaler_coding.joblib"),
    },
    3: {
        "name": "gaming",
        "table": "os_doctor_train_g",
        "model_path": os.path.join(OS_DOCTOR_MODELS_DIR, "iso_forest_gaming.joblib"),
        "scaler_path": os.path.join(OS_DOCTOR_MODELS_DIR, "scaler_gaming.joblib"),
    },
}

# FocusOS config
COMPILERS = ["gcc", "g++", "clang", "make", "ninja", "rustc", "javac"]
BROWSERS = ["chrome", "firefox", "brave", "msedge"]
CALLS = ["zoom", "teams", "slack", "discord", "skype", "webex"]
IDES = ["code", "code-insiders", "sublime", "vim", "nvim"]

# Blackbox config
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

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

TRAINING_DATA_PATH = "blackbox/training_vectors.jsonl"
COLLECT_INTERVAL_SEC = 30
ROWS_PER_VECTOR = 120  # ~2 min of telemetry per feature vector
ANOMALY_CHECK_INTERVAL_SEC = 120  # Isolation Forest check cadence
