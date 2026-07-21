"""Per-layer file logging setup, no console output."""
import logging
from pathlib import Path

_LOG_DIR = Path("logs")


def get_layer_logger(name: str) -> logging.Logger:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"cognios.{name}")
    if not logger.handlers:
        handler = logging.FileHandler(_LOG_DIR / f"{name}.log")
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
