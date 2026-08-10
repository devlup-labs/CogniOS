import os
import sys
import subprocess
import time
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_stop_watchdog = threading.Event()


def _daemon_watchdog(daemon_script, telemetry_log_path, restart_delay=3):
    """Watches the daemon process and restarts it if it crashes."""
    restart_count = 0
    process = None

    while not _stop_watchdog.is_set():
        # Start (or restart) the daemon
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

        # Block until the process exits
        process.wait()

        if _stop_watchdog.is_set():
            break  # Intentional shutdown — don't restart

        exit_code = process.returncode
        print(f"[!] CogniOS Engine exited (code={exit_code}). Restarting in {restart_delay}s...")
        restart_count += 1
        _stop_watchdog.wait(timeout=restart_delay)

    return process


def main():
    print("Starting CogniOS System...")

    telemetry_log_path = os.path.join(BASE_DIR, 'telemetry_daemon.log')
    daemon_script = os.path.join(BASE_DIR, "cognios_as_daemon.py")

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
    dashboard_script = os.path.join(BASE_DIR, "dashboard", "app.py")
    dashboard_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", dashboard_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"[✔] CogniOS Dashboard started (PID: {dashboard_process.pid})")

    print("\n=======================================================")
    print("🚀 All systems are running!")
    print("📊 Dashboard is available at: http://localhost:8501")
    print(f"📝 Live logs: tail -f '{telemetry_log_path}'")
    print("=======================================================\n")
    print("Press Ctrl+C to stop all services.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping CogniOS System...")
    finally:
        # Signal watchdog to stop restarting the daemon
        _stop_watchdog.set()

        if dashboard_process.poll() is None:
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard_process.kill()

        print("Shutdown complete. Goodbye!")

if __name__ == "__main__":
    main()
