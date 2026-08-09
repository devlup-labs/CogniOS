import os
import sys
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    print("Starting CogniOS System...")

    # 1. Start the Unified Engine Daemon
    telemetry_log_path = os.path.join(BASE_DIR, 'telemetry_daemon.log')
    telemetry_log = open(telemetry_log_path, 'w')
    daemon_script = os.path.join(BASE_DIR, "cognios_as_daemon.py")
    
    daemon_process = subprocess.Popen(
        [sys.executable, daemon_script], 
        stdout=telemetry_log,
        stderr=telemetry_log
    )
    print(f"[✔] CogniOS Engine started in background (PID: {daemon_process.pid})")
    
    # 2. Start the Streamlit Dashboard
    dashboard_script = os.path.join(BASE_DIR, "dashboard", "app.py")
    dashboard_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", dashboard_script],
        stdout=subprocess.DEVNULL,  # Hide streamlit terminal spam
        stderr=subprocess.DEVNULL
    )
    print(f"[✔] CogniOS Dashboard started (PID: {dashboard_process.pid})")
    
    print("\n=======================================================")
    print("🚀 All systems are running!")
    print("📊 Dashboard is available at: http://localhost:8501")
    print(f"📝 Live logs: tail -f '{telemetry_log_path}'")
    print("=======================================================\n")
    print("Press Ctrl+C to stop all services.")

    try:
        # Keep the main thread alive to catch Ctrl+C
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping CogniOS System...")
    finally:
        # Graceful cleanup
        if daemon_process.poll() is None:
            daemon_process.terminate()
            try:
                daemon_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                daemon_process.kill()
        
        if dashboard_process.poll() is None:
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard_process.kill()
                
        telemetry_log.close()
        print("Shutdown complete. Goodbye!")

if __name__ == "__main__":
    main()
