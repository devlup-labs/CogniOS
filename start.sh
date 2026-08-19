#!/usr/bin/env bash
# CogniOS - Automated Environment Setup & Launcher
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# 1. Create virtual environment if it doesn't exist
if [ ! -f "$VENV_PYTHON" ]; then
    echo "======================================================="
    echo "📦 Setting up isolated CogniOS environment (.venv)..."
    echo "======================================================="
    if command -v python3 &>/dev/null; then
        PYTHON_BIN="python3"
    elif command -v python &>/dev/null; then
        PYTHON_BIN="python"
    else
        echo "❌ Error: Python 3 is not installed or not in PATH."
        exit 1
    fi

    "$PYTHON_BIN" -m venv "$VENV_DIR"
    echo "✔ Created virtual environment at $VENV_DIR"
    
    echo "📥 Installing required dependencies from requirements.txt..."
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt"
    echo "✔ Dependencies installed successfully!"
fi

# 2. Run CogniOS main application using the virtual environment
exec "$VENV_PYTHON" "$SCRIPT_DIR/main.py" "$@"
