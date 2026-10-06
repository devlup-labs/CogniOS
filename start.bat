@echo off
REM CogniOS - Automated Environment Setup & Launcher for Windows
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "VENV_DIR=%SCRIPT_DIR%.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo =======================================================
    echo Setting up isolated CogniOS environment (.venv)...
    echo =======================================================
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Error: Failed to create virtual environment. Ensure Python is installed.
        exit /b 1
    )
    echo Created virtual environment at %VENV_DIR%
    echo Installing dependencies from requirements.txt...
    "%VENV_PYTHON%" -m pip install --upgrade pip
    "%VENV_PYTHON%" -m pip install -r "%SCRIPT_DIR%requirements.txt"
)

"%VENV_PYTHON%" "%SCRIPT_DIR%main.py" %*
