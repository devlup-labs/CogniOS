import threading
from os_doctor.os_doctor_db import execute_os_doctor_db
from cognios_as_daemon import run_daemon

if __name__ == "__main__":
    threading.Thread(target=execute_os_doctor_db, daemon=True).start() 
    run_daemon()
