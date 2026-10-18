import argparse
import os
import sys
import subprocess
import shutil
import time
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from check_requirements import ensure_requirements

def _get_venv_python():
    """Returns the path to the virtual environment python executable if it exists."""
    candidates = [
        os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe") if sys.platform == "win32" else os.path.join(BASE_DIR, ".venv", "bin", "python"),
        os.path.expanduser("~/venv/bin/python"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


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


def _daemon_running():
    if shutil.which("systemctl"):
        try:
            if subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", "cognios"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            pass

    try:
        return subprocess.run(
            ["pgrep", "-f", "cognios_as_daemon.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
    except OSError:
        return False


def main(ui_mode="desktop"):
    _ensure_environment()

    print("\n=======================================================")
    print(" Starting CogniOS System...")
    print(f" Python Environment: {sys.executable}")
    print("=======================================================")

    dashboard_log_path = os.path.join(BASE_DIR, 'dashboard.log')
    dashboard_script = os.path.join(BASE_DIR, "dashboard", "app.py")

    if _daemon_running():
        print("CogniOS daemon is running.")
    else:
        print("CogniOS daemon is not running. Start it with: systemctl --user start cognios")

    # 2. Start the existing dashboard so localhost and launcher use one UI.
    dashboard_log = open(dashboard_log_path, 'w')
    dashboard_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", dashboard_script, "--server.headless=true"],
        stdout=dashboard_log,
        stderr=dashboard_log,
    )
    print(f"[✔] CogniOS Dashboard started (PID: {dashboard_process.pid})")

    print("\n=======================================================")
    print("All systems are running!")
    print(f"Opening dashboard in {ui_mode} mode...")
    print(f" Dashboard logs : tail -f '{dashboard_log_path}'")
    print("=======================================================\n")
    print("Press Ctrl+C to stop all services.")

    try:
        if ui_mode == "browser":
            if not webbrowser.open("http://127.0.0.1:8501", new=2):
                raise RuntimeError("Could not open the dashboard in a browser.")
            while True:
                time.sleep(1)
        else:
            from dashboard.desktop import run_dashboard
            run_dashboard()
    except KeyboardInterrupt:
        print("\nStopping CogniOS System...")
    finally:
        if dashboard_process.poll() is None:
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard_process.kill()

        dashboard_log.close()
        print("Shutdown complete. Goodbye!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", choices=("browser", "desktop"), default="desktop")
    args = parser.parse_args()
    main(args.ui)
