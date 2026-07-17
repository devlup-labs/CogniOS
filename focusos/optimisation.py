import psutil
import os
import sqlite3
import time
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DBPATH
from config import compilers  # yet not written in the config files- > will update soon
from config import browsers   # yet not written in the config files- > will update soon
from config import IDEs       # yet not written in the config files- > will update soon
def apply_optimization(workload: str, confidence: float) -> bool:
  if confidence < 0.80:
    return False
  actions = []
  total_cores = os.cpu_count() or 4
  if workload == "compiler":
    compiler_prioritized_count = 0
    for c in compilers:
      compiler_prioritized_count += prioritize_process(c, 10)
    if compiler_prioritized_count > 0:
      actions.append(f"Deprioritise {compiler_prioritized_count} build processes to nice=10")
    pin_count = pin_process_to_cores("gcc", [0, 1])
    if pin_count > 0:
      actions.append(f"Pin {pin_count} compiler tasks to cores [0,1]")
  elif workload.lower() == "gaming":
  #will reset the affinity of the bg processes to free up gaming cores
    restore_count = pin_process_to_cores("gaming", list(range(total_cores)))
    if restore_count > 0:
      print(f"Restoring full affinity for the background browsers")
  elif workload.lower() == "coding":
    ide_count = prioritize_process("code", -2)
    if ide_count > 0:
      actions.append(f"Prioritise {ide_count} IDE processes to nice=-2")
  if len(actions) > 0:
    try:
      log_optimization_result(workload, confidence, actions)
      return True
    except Exception as e:
      print(f"Database logging error :{e}")
  return True