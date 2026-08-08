import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cognios_telemetry.db")
SLIDING_WIND_N = 30
COMPILERS = ["gcc", "g++", "clang", "make", "ninja", "rustc", "javac"]
BROWSERS = ["chrome", "firefox", "brave", "msedge"]
CALLS = ["zoom", "teams", "slack", "discord", "skype", "webex"]
IDES = ["code", "code-insiders", "sublime", "vim", "nvim"]
GAMES = ["cs2", "dota2", "valorant", "vgc", "fortniteclient", 
    "r5apex", "pubg", "tslgame", "gta5", "gtav", "cod", "overwatch","cyberpunk2077", "eldenring", "bg3", "pathofexile", "witcher3", "minecraft",
    "gamemoded", "winedevice", "easyanticheat", "battleye"]
