import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cognios_telemetry.db")
SLIDING_WIND_N = 120
COMPILERS = ["gcc", "g++", "clang", "make", "ninja", "rustc", "javac"]
BROWSERS = ["chrome", "firefox", "brave", "msedge"]
CALLS = ["zoom", "teams", "slack", "discord", "skype", "webex"]
IDES = ["code", "code-insiders", "sublime", "vim", "nvim"]
