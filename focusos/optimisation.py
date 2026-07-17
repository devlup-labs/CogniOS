import psutil
import os
import sqlite3
import time
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DBPATH
from config import COMPILERS    # yet not written in the config files- > will update soon
from config import BROWSERS     # yet not written in the config files- > will update soon
from config import CALLS        # yet not written in the config files- > will update soon
from config import IDES         # yet not written in the config files- > will update soon
def apply_optimization(workload: str, confidence: float) -> bool:
  if confidence < 0.80:
    print(f"Optimisation aborted: Confidence for {workload} is less than 80%")
    return False
  actions = []
  total_cores = os.cpu_count() or 4
  # isolating backgrounds tasks by allocating them unto the last core
  background_cores=[total_cores-1]
  foreground_cores=list(range(0,total_cores-1)) if total_cores > 1 else [0]
  if workload.lower()=="compiler":
    #deprioritising the compilers
    count_nice=sum(prioritise_process(compiler,15) for compiler in COMPILERS)
    count_affinity=sum(pin_process_to_cores(compiler,background_cores) for compiler in COMPILERS)
    count_io = sum(prioritise_process(compiler, 3) for compiler in COMPILERS)
    if count_nice > 0:
      actions.append(f"Deprioritise {count_nice},pinned {core_affinity} to core(s) {background_cores},set {count_io} to idle IO")
 
 
  elif workload.lower() == "gaming":
  #will reset the affinity of the bg processes to free up gaming cores
    count_nice=prioritise_process("steam",-5)
    count_nice+=prioritise_process("game-process",-10)
    count_affinity=pin_process_to_cores("game-process",list(range(total_cores)))
    actions.append(f"Prioritised {count_nice},granted {counted_affinity} full core affinity")
  
  
  elif workload.lower() == "coding":
    count_nice=prioritise_process(ide,-5) for ide in IDEs
    count_affinity=pin_process_to_cores(browser,background_cores) for browser in BROWSERS
    action.append(f"Prioritised{count_nice},pinned {cpu_affinity} browser process to cores {background_cores}")
  
  
  elif workload.lower()=="browsing":
    #reset all the process to normal priority and spread across all cores
    count_nice=sum(prioritise_process(browser,0) for browser in BROWSERS)
    count_affinity=sum(pin_process_to_cores(browser,list(range(total_cores))) for browser BROWSERS)
    action.append(f"Browsing: Restored {count_nice} browser processes to normal nice priority across {count_aff} cores")


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
        pid=proc.info['info']
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
  optimized_count = 0
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        try:
            current_name = proc.info['name'] or ""
            if proc_name.lower() in current_name.lower():
                pid = proc.info['pid']
                process_obj = psutil.Process(pid)
                process_obj.nice(nice_val)
                optimized_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue
      return optimized_count

  def log_optimization_result(workload: str, confidence: float, actions: list[str]):
  #logging all the optimisation event to the database
  try:
    with sqlite3.connect(DBPATH) as conn:
      cur = conn.cursor()
      with conn:
      cur.execute("""CREATE TABLE IF NOT EXISTS focusos_events (timestamp REAL,workload TEXT,confidence INTEGER,actions TEXT)""")
      cur.execute("""INSERT INTO focusos_events (timestamp, workload, confidence, actions_json)VALUES (?, ?, ?, ?)""", (time.time(), workload, confidence, json.dumps(actions)))
    conn.commit()
  except Exception as e:
    print(f"Database logging error {e}")
