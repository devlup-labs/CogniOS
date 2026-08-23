import os
import sys
import subprocess
import time
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from check_requirements import ensure_requirements

_stop_watchdog = threading.Event()


def _get_venv_python():
    """Returns the path to the project's .venv python executable if it exists."""
    if sys.platform == "win32":
        venv_py = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
    else:
        venv_py = os.path.join(BASE_DIR, ".venv", "bin", "python")
    return venv_py if os.path.isfile(venv_py) else None


def _ensure_environment():
    """
    Ensures CogniOS runs in the dedicated virtual environment (.venv)
    with all required dependencies installed.
    """
    venv_py = _get_venv_python()
    current_py = os.path.abspath(sys.executable)

    # 1. If .venv exists and we are not currently running in it, re-exec into .venv
    if venv_py:
        abs_venv_py = os.path.abspath(venv_py)
        if current_py != abs_venv_py and os.environ.get("COGNI_VENV_ACTIVE") != "1":
            os.environ["COGNI_VENV_ACTIVE"] = "1"
            os.environ["VIRTUAL_ENV"] = os.path.join(BASE_DIR, ".venv")
            venv_bin = os.path.dirname(abs_venv_py)
            os.environ["PATH"] = venv_bin + os.pathsep + os.environ.get("PATH", "")
            try:
                os.execv(abs_venv_py, [abs_venv_py] + sys.argv)
            except Exception as e:
                print(f"[!] Failed to auto-switch to .venv python: {e}")

    # 2. Check & auto-install missing requirements gracefully
    ensure_requirements(auto_install=True, quiet=False)


def _daemon_watchdog(daemon_script, telemetry_log_path, restart_delay=3):
    """Watches the daemon process and restarts it if it crashes."""
    restart_count = 0
    process = None

    while not _stop_watchdog.is_set():
        with open(telemetry_log_path, 'a') as log:
            process = subprocess.Popen(
                [sys.executable, daemon_script],
                stdout=log,
                stderr=log,
            )
        if restart_count == 0:
            print(f"[✔] CogniOS Engine started (PID: {process.pid})")
        else:
            print(f"[⟳] CogniOS Engine restarted (PID: {process.pid}, attempt #{restart_count})")

        process.wait()

        if _stop_watchdog.is_set():
            break

        exit_code = process.returncode
        print(f"[!] CogniOS Engine exited (code={exit_code}). Restarting in {restart_delay}s...")
        restart_count += 1
        _stop_watchdog.wait(timeout=restart_delay)

    return process


def main():
    _ensure_environment()

    print("\n=======================================================")
    print("🚀 Starting CogniOS System...")
    print(f"🐍 Python Environment: {sys.executable}")
    print("=======================================================")

    telemetry_log_path = os.path.join(BASE_DIR, 'telemetry_daemon.log')
    dashboard_log_path = os.path.join(BASE_DIR, 'dashboard.log')
    daemon_script = os.path.join(BASE_DIR, "cognios_as_daemon.py")
    dashboard_script = os.path.join(BASE_DIR, "dashboard", "app.py")

    # 1. Start daemon under watchdog thread so it auto-restarts on crash
    watchdog_thread = threading.Thread(
        target=_daemon_watchdog,
        args=(daemon_script, telemetry_log_path),
        daemon=True,
        name="daemon-watchdog",
    )
    watchdog_thread.start()

    # Give the daemon a moment to initialise DB before dashboard connects
    time.sleep(2)

    # 2. Start the Streamlit Dashboard
    dashboard_log = open(dashboard_log_path, 'w')
    dashboard_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", dashboard_script, "--server.headless=true"],
        stdout=dashboard_log,
        stderr=dashboard_log,
    )
    print(f"[✔] CogniOS Dashboard started (PID: {dashboard_process.pid})")

    print("\n=======================================================")
    print("✨ All systems are running!")
    print("📊 Dashboard is available at: http://localhost:8501")
    print(f"📝 Telemetry logs : tail -f '{telemetry_log_path}'")
    print(f"📊 Dashboard logs : tail -f '{dashboard_log_path}'")
    print("=======================================================\n")
    print("Press Ctrl+C to stop all services.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping CogniOS System...")
    finally:
        _stop_watchdog.set()

        if dashboard_process.poll() is None:
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard_process.kill()

        try:
            dashboard_log.close()
        except Exception:
            pass

        print("Shutdown complete. Goodbye!")


if __name__ == "__main__":
    main()

