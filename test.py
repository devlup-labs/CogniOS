import threading
from os_doctor.os_doctor_db_g import execute_os_doctor_db as execute_gaming
from os_doctor.os_doctor_db_b import execute_os_doctor_db as execute_browsing
from os_doctor.os_doctor_db_c import execute_os_doctor_db as execute_coding
from os_doctor.os_doctor_db_i import execute_os_doctor_db as execute_idle
from cognios_as_daemon import run_daemon
from os_doctor.i_forest_predict import flag_anomaly
from os_doctor.i_forest_train import train_isolation_forest_model, train_all_workloads
# from os_doctor.llm_layer import run_llm_daemon

from config import DB_PATH

if __name__ == "__main__":
    # ── Training: uncomment ONE workload at a time to collect its baseline ──
    # threading.Thread(target=execute_gaming, daemon=True).start()       # gaming workload
    # threading.Thread(target=execute_browsing, daemon=True).start()   # browsing workload
    threading.Thread(target=execute_coding, daemon=True).start()     # coding workload
    # threading.Thread(target=execute_idle, daemon=True).start()       # idle workload

    # ── Model training: uncomment to train a workload model (0=idle, 1=browsing, 2=coding, 3=gaming) ──
    # train_isolation_forest_model(3)  # train gaming model
    # train_isolation_forest_model(1)  # train browsing model
    # train_isolation_forest_model(2)  # train coding model
    # train_isolation_forest_model(0)  # train idle model
    # train_all_workloads()            # train all workloads that have data

    # ── Prediction: pass a callable that returns the current workload int (0-3) ──
    # threading.Thread(target=flag_anomaly, args=(lambda: 3,), daemon=True).start()

    # threading.Thread(target=run_llm_daemon, daemon=True).start()
    run_daemon()