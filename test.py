import threading
from os_doctor.os_doctor_db import execute_os_doctor_db
from cognios_as_daemon import run_daemon
from os_doctor.i_forest_predict import flag_anomaly
from os_doctor.i_forest_train import train_isolation_forest_model
from os_doctor.featuring import extract_and_engineer_sys, extract_and_engineer_processes, build_unified_vector, get_inference_payload
from os_doctor.alerts_db import create_connection, init_alerts_db, write_to_alerts_table, _harden_connection, ensure_wal_mode

from config import DB_PATH
if __name__ == "__main__":
    # threading.Thread(target=execute_os_doctor_db, daemon=True).start()
    threading.Thread(target=flag_anomaly, daemon=True).start()
    run_daemon()
    # extract_and_engineer_sys(DB_PATH)
    # extract_and_engineer_processes(DB_PATH)
    # train_isolation_forest_model()
    # flag_anomaly()
    # execute_os_doctor_db()
    # conn = create_connection()
    # init_alerts_db(conn)

    