"""Single startup script for CogniOS."""
import subprocess
import sys

print("Starting CogniOS System...")

# Start the Telemetry Daemon in the background
# Output is routed to telemetry_daemon.log
telemetry_log = open('telemetry_daemon.log', 'w')
telemetry_process = subprocess.Popen(
    [sys.executable, "cognios_as_daemon.py"], 
    stdout=telemetry_log, 
    stderr=telemetry_log
)
print(f"Telemetry Daemon started! (PID: {telemetry_process.pid})")
print("To view the live logs anytime, run: tail -f telemetry_daemon.log")
print("To stop the daemon, run: pkill -f cognios_as_daemon.py")
# Start the FocusOS Daemon in the background
# Output is routed to focusos.log
# focusos_log = open('focusos.log', 'w')
# focusos_process = subprocess.Popen(
#     [sys.executable, "focusos_daemon.py"], 
#     stdout=focusos_log, 
#     stderr=focusos_log
#)
#print(f"FocusOS Daemon started! (PID: {focusos_process.pid})")

#print("\nAll CogniOS modules are now running silently in the background!")
print("Your terminal is free to use.")
