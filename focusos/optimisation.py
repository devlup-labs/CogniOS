import psutil
import os
import sqlite3
import time
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH
from config import COMPILERS  
from config import BROWSERS     
from config import CALLS        
from config import IDES         
def apply_optimization(workload: str, confidence: float) -> bool:
  if confidence < 80:
    print(f"Optimisation aborted: Confidence for {workload} is less than 80%")
    return False
  actions = []
  total_cores = os.cpu_count() or 4
  # isolating backgrounds tasks by allocating them unto the last core
  background_cores=[total_cores-1]
  foreground_cores=list(range(0,total_cores-1)) if total_cores > 1 else [0]
  if workload.lower()=="compiling":
    #deprioritising the compilers
    count_nice=sum(prioritise_process(compiler,15) for compiler in COMPILERS)
    count_affinity=sum(pin_process_to_cores(compiler,background_cores) for compiler in COMPILERS)
    count_io = sum(set_io_priority(compiler, 3) for compiler in COMPILERS)
    if count_nice > 0:
      actions.append(f"Deprioritised {count_nice} compiler(s), pinned {count_affinity} to core(s) {background_cores}, set {count_io} to idle IO")
 
 
  elif workload.lower() == "gaming":
  #will reset the affinity of the bg processes to free up gaming cores
    count_nice=prioritise_process("steam",-5)
    count_nice+=prioritise_process("game-process",-10)
    count_affinity=pin_process_to_cores("game-process",list(range(total_cores)))
    if count_nice > 0:
      actions.append(f"Prioritised {count_nice} game process(es), granted {count_affinity} full core affinity")
  
  
  elif workload.lower() == "coding":
    count_nice = sum(prioritise_process(ide, -5) for ide in IDES)
    count_affinity = sum(pin_process_to_cores(browser, background_cores) for browser in BROWSERS)
    if count_nice > 0:
      actions.append(f"Prioritised {count_nice} IDE process(es), pinned {count_affinity} browser(s) to cores {background_cores}")
  
  
  elif workload.lower()=="browsing":
    #reset all the process to normal priority and spread across all cores
    count_nice=sum(prioritise_process(browser,0) for browser in BROWSERS)
    count_affinity = sum(pin_process_to_cores(browser, list(range(total_cores))) for browser in BROWSERS)
    if count_nice > 0:
      actions.append(f"Browsing: Restored {count_nice} browser(s) to normal nice priority across {count_affinity} core(s)")


  elif workload.lower()=="video call":
    #prioritising the communication 
    count_nice=sum(prioritise_process(call,-5) for call in CALLS)
    actions.append(f"Video calling :Prioritising {count_nice} communication process")

  elif workload.lower() == "idle":
    # restore IDEs, browsers, and communication tools to baseline priority and full affinity
    count_nice = sum(prioritise_process(ide, 0) for ide in IDES)
    count_nice += sum(prioritise_process(browser, 0) for browser in BROWSERS)
    count_nice += sum(prioritise_process(call, 0) for call in CALLS)
    
    count_aff = sum(pin_process_to_cores(browser, list(range(total_cores))) for browser in BROWSERS)
    actions.append(
        f"Idle: Restored {count_nice} processes to normal scheduling and granted {count_aff} full core affinity."
    )
  #
  if len(actions) > 0:
    try:
      log_optimization_result(workload, confidence, actions)
      print(f"Optimization Successful: {actions[-1]}")
      return True
    except Exception as e:
      print(f"Database logging error :{e}")
  return True

def pin_process_to_cores(proc_name: str,cores: list[int]) -> int:
  optimised_count=0
  for proc in psutil.process_iter(attrs=['pid','name']):
    try:
      current_name=proc.info['name'] or ""
      if proc_name.lower() in current_name.lower():
        pid=proc.info['pid']
        process_obj=psutil.Process(pid)

        process_obj.cpu_affinity(cores) 
        optimised_count+=1
    except(psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess):
      continue
    except Exception:
      continue
  return optimised_count
#it safely adjusts the cpu scheduling priority 19 to -20(nicest)
def prioritise_process(proc_name: str, nice_val: int) -> int:
  """Safely adjusts the CPU scheduling priority (nice: -20 highest to 19 lowest)."""
  optimised_count = 0
  for proc in psutil.process_iter(attrs=['pid', 'name']):
      try:
          current_name = proc.info['name'] or ""
          if proc_name.lower() in current_name.lower():
              pid = proc.info['pid']
              process_obj = psutil.Process(pid)
              process_obj.nice(nice_val)
              optimised_count += 1
      except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
          continue
      except Exception:
          continue
  return optimised_count
def set_io_priority(proc_name: str,io_class: int) -> int:
    optimised_count=0
    for proc in psutil.process_iter(attrs=["pid","name"]):
        current_pid=proc.info["pid"]
        try:
            current_name=proc.info["name"] or ""
            if proc_name.lower() in current_name.lower():
                process_obj=psutil.Process(current_pid)
                process_obj.ionice(io_class)
                optimised_count += 1
        except(psutil.NoSuchProcess,psutil.ZombieProcess,psutil.AccessDenied):
            continue
    return optimised_count




def log_optimization_result(workload: str, confidence: float, actions: list[str]):
    """Log all optimisation events to the focusos_events database table."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS focusos_events (
                    timestamp  REAL,
                    workload   TEXT,
                    confidence REAL,
                    actions    TEXT
                )
            """)
            cur.execute(
                """INSERT INTO focusos_events (timestamp, workload, confidence, actions)
                   VALUES (?, ?, ?, ?)""",
                (time.time(), workload, confidence, json.dumps(actions))
            )
            # `with sqlite3.connect(...) as conn` auto-commits on exit
    except Exception as e:
        print(f"Database logging error: {e}")
