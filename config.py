import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

DB_PATH = "cognios_telemetry.db"
BLACKBOX_DB_PATH         = "blackbox/blackbox.db"
BLACKBOX_WINDOW_SEC = 1800  # 30 minutes
BLACKBOX_CRASH_GAP_SEC = 30   # SIGKILL-only fallback, not the primary check
