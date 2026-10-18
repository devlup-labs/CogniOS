import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cognios_telemetry.db")
SLIDING_WIND_N = 30
AUTO_REFRESH = 2  # seconds between dashboard refreshes


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
GAMES = ["steam", "csgo", "dota2", "hl2_linux", "minecraft"]

# FocusOS Rule Engine Config
RULE_CPU_ACTIVE_THRESHOLD = 2.0   # process CPU% to be "relevant"
RULE_RAM_ACTIVE_THRESHOLD = 150.0  # process RAM RSS in MB to be "relevant"
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
BLACKBOX_PRUNE_INTERVAL_SEC = 60 # Run database cleanup once every 60 seconds
BLACKBOX_CRASH_GAP_SEC = 30   # SIGKILL-only fallback, not the primary check

BLACKBOX_Z_THRESHOLD     = 2.8    # std deviations for spike
BLACKBOX_SLOPE_THRESHOLD = 0.003  # %/sec rise = suspicious
BLACKBOX_SUSTAINED_SEC   = 30     # spike must last this long
BLACKBOX_SUSTAINED_RATIO = 0.6    # 60% readings above threshold
BLACKBOX_TREND_WINDOW    = 600    # 10 min for slope calculation

# Alert / Telemetry thresholds
BLACKBOX_CPU_CRITICAL  = 90.0 # critical CPU usage threshold
BLACKBOX_MEM_CRITICAL  = 90.0 # critical memory usage threshold
BLACKBOX_ZOMBIE_LIMIT  = 10   # limit for zombie processes
BLACKBOX_TEMP_CRITICAL = 85.0 # critical temperature threshold
BLACKBOX_SWAP_CRITICAL = 80.0 # critical swap usage threshold

TRAINING_DATA_PATH = "blackbox/training_vectors.jsonl"
COLLECT_INTERVAL_SEC = 30
ROWS_PER_VECTOR = 120  # ~2 min of telemetry per feature vector
ANOMALY_CHECK_INTERVAL_SEC = 120  # Isolation Forest check cadence

# User-editable configuration overrides from dashboard UI
CONFIG_OVERRIDES_PATH = os.path.join(BASE_DIR, "config_overrides.json")

def load_config_overrides():
    if os.path.exists(CONFIG_OVERRIDES_PATH):
        try:
            import json
            with open(CONFIG_OVERRIDES_PATH, "r") as f:
                overrides = json.load(f)
            for k, v in overrides.items():
                globals()[k] = v
        except Exception:
            pass

def save_config_overrides(updates: dict):
    """Saves user config changes from UI to config_overrides.json and updates current module globals."""
    import json
    existing = {}
    if os.path.exists(CONFIG_OVERRIDES_PATH):
        try:
            with open(CONFIG_OVERRIDES_PATH, "r") as f:
                existing = json.load(f)
        except Exception:
            pass
    existing.update(updates)
    with open(CONFIG_OVERRIDES_PATH, "w") as f:
        json.dump(existing, f, indent=2)

    # Update in-memory globals
    import config
    for k, v in updates.items():
        setattr(config, k, v)
        globals()[k] = v

    if "GROQ_API_KEY" in updates:
        os.environ["GROQ_API_KEY"] = str(updates["GROQ_API_KEY"])
    if "GROQ_MODEL" in updates:
        os.environ["GROQ_MODEL"] = str(updates["GROQ_MODEL"])

# Load overrides on initial module import
load_config_overrides()


