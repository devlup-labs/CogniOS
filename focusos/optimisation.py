import psutil
import os
import sqlite3
import time
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import subprocess
import threading
import numpy as np
from focusos.collector import get_top_processes
from focusos.sliding_window import get_window_from_db
from config import DB_PATH
from config import COMPILERS
from config import IDES
from config import BROWSERS
from config import GAMES
from config import CALLS
'''These lists are not yet written in cofig file, will be updated soon'''

def capture_process_states():
	"""Captures exact state (nice, cpu_affinity, ionice) of all running processes."""
	state = {}
	for proc in psutil.process_iter(attrs=['pid', 'name']):
		try:
			pid = proc.info['pid']
			p = psutil.Process(pid)
			proc_state = {}
			try:
				proc_state['nice'] = p.nice()
			except psutil.AccessDenied:
				pass
			try:
				proc_state['affinity'] = p.cpu_affinity()
			except (psutil.AccessDenied, AttributeError):
				pass
			try:
				io = p.ionice()
				proc_state['ioclass'] = io.ioclass
				proc_state['iovalue'] = io.value
			except (psutil.AccessDenied, AttributeError):
				pass
			if proc_state:
				state[pid] = proc_state
		except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
			continue
	return state

def restore_process_states(saved_state: dict):
	"""Restores the exact state of processes from a saved snapshot."""
	restored_count = 0
	for pid, state in saved_state.items():
		try:
			p = psutil.Process(pid)
			if 'nice' in state:
				p.nice(state['nice'])
			if 'affinity' in state and state['affinity']:
				p.cpu_affinity(state['affinity'])
			if 'ioclass' in state:
				p.ionice(state['ioclass'], state.get('iovalue', 0))
			restored_count += 1
		except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError):
			continue
	return restored_count

def verify_and_rollback(pre_state: dict, workload: str, baseline_mean: float, baseline_std: float):
	"""Monitors telemetry post-optimization and rolls back on regression."""
	time.sleep(60)
	df_window = get_window_from_db(limit=60)
	if df_window is None or df_window.empty:
		return
	
	post_cpu = df_window['cpu_usage_percent'].values
	post_mean = np.mean(post_cpu)
	
	std = baseline_std + 0.001
	z_score = (post_mean - baseline_mean) / std
	
	if z_score < -2.5:
		restored = restore_process_states(pre_state)
		log_optimization_result(workload, 100.0, [f"Rollback triggered (Z={z_score:.2f})"], f"Performance regression detected. Restored {restored} processes.")
		print(f"Rollback executed: Z-score {z_score:.2f} < -2.5. Restored {restored} processes.")
	else:
		log_optimization_result(workload, 100.0, [f"Optimization verified (Z={z_score:.2f})"], "Telemetry within acceptable bounds.")

def apply_optimization(workload: str, confidence: float, explanation: str = "") -> bool:
	if confidence < 80:
		print(f"Optimisation aborted: Confidence for {workload} is less than 80%")
		log_optimization_result(workload, confidence, ["Optimization skipped (Confidence < 80%)"], explanation)
		return False

	pre_state = capture_process_states()
	df_baseline = get_window_from_db(limit=60)
	baseline_mean = 0.0
	baseline_std = 1.0
	if df_baseline is not None and not df_baseline.empty:
		baseline_mean = np.mean(df_baseline['cpu_usage_percent'].values)
		baseline_std = np.std(df_baseline['cpu_usage_percent'].values)

	actions = []

	# Gathering hardware architecture details
	total_cores = os.cpu_count() or 4
	p_cores, e_cores = get_cores()
		
	# Assign cores based on whether the system is hybrid or symmetrical
	if e_cores:
			#Hybrid system
			foreground_cores = p_cores
			background_cores = e_cores
	else:
			#Traditional system without hybrid architecture
			foreground_cores = [c for c in range(total_cores) if c % 2 == 0] or [0]
			background_cores = [c for c in range(total_cores) if c % 2 != 0] or [total_cores - 1]

	top_cpu, top_mem = get_top_processes(5)
	unique_processes_dict = {p['pid']: p for p in top_cpu + top_mem}
	unique_processes = list(unique_processes_dict.values())
	
	workload_clean = workload.lower().replace("_", " ")

	if workload_clean != "video call":
			set_network_fair_queuing(False)

	if workload_clean == "compiling":
		#prioritising the compilers
		count_nice = sum(prioritise_process(compiler,-12) for compiler in COMPILERS)
		count_affinity = sum(pin_process_to_cores(compiler, foreground_cores) for compiler in COMPILERS)
		count_io = sum(set_io_priority(compiler, 'b', 3) for compiler in COMPILERS)
		count_nice_bg = 0
		count_affinity_bg = 0

		#moderately prioritising IDEs
		count_nice_ide = sum(prioritise_process(ide,-5) for ide in IDES)

		#de-prioritising top processes that are background processes
		for p in unique_processes:
				proc_name = p["name"].lower()
				if proc_name not in COMPILERS and proc_name not in IDES:
						count_nice_bg += prioritise_process(proc_name, 7)
						set_io_priority(proc_name, 'i', 0)
						pin_process_to_cores(proc_name, background_cores)

		if count_nice > 0 or count_nice_bg > 0:
			actions.append(f"Prioritised {count_nice} compiler(s), pinned {count_affinity} to core(s) {foreground_cores}, set {count_io} to idle IO")
 
 
	elif workload_clean == "gaming":
		#will reset the affinity of the bg processes to free up gaming cores and pin game processes to foreground cores
		count_nice = sum(prioritise_process(game, -10) for game in GAMES)
		count_affinity = sum(pin_process_to_cores(game, foreground_cores) for game in GAMES)
		count_io = sum(set_io_priority(game, 'b', 1) for game in GAMES)
		
		count_bg = 0
		for p in unique_processes:
				proc_name = p["name"].lower()
				if proc_name not in GAMES:
						count_bg += prioritise_process(proc_name, 10)
						set_io_priority(proc_name, 'i', 0)
						pin_process_to_cores(proc_name, background_cores)

		if count_nice > 0 or count_bg > 0:
			actions.append(f"Prioritised {count_nice} game process(es), granted {count_affinity} full core affinity")
	
	
	elif workload_clean == "coding":
		count_nice = sum(prioritise_process(ide, -5) for ide in IDES)
		count_affinity = sum(pin_process_to_cores(ide, foreground_cores) for ide in IDES)
		count_browser_aff = sum(pin_process_to_cores(browser, background_cores) for browser in BROWSERS)
		
		if count_nice > 0:
			actions.append(f"Prioritised {count_nice} IDE process(es), pinned {count_browser_aff} browser(s) to cores {background_cores}")
	
	
	elif workload_clean == "browsing":
		#reset all the process to normal priority and spread across all cores
		count_nice = sum(prioritise_process(browser, 0) for browser in BROWSERS)
		count_affinity = sum(pin_process_to_cores(browser, foreground_cores) for browser in BROWSERS)
		
		# Deprioritize background I/O to yield disk cache to the browser process
		for p in unique_processes:
				proc_name = p["name"].lower()
				if proc_name not in BROWSERS:
						set_io_priority(proc_name, 'i', 0)

		if count_nice > 0:
			actions.append(f"Browsing: Restored {count_nice} browser(s) to normal nice priority across {count_affinity} core(s)")


	elif workload_clean == "video call":
		#prioritising the communication 
		count_nice = sum(prioritise_process(call, -5) for call in CALLS)
		count_affinity = sum(pin_process_to_cores(call, foreground_cores) for call in CALLS)
		
		# Deprioritize background I/O to prevent loss of audio or video packets
		for p in unique_processes:
				proc_name = p["name"].lower()
				if proc_name not in CALLS:
						set_io_priority(proc_name, 'i', 0)
						
		# Fair Queuing with the help of tc (Traffic control tool), will require sudo privilages
		set_network_fair_queuing(True)

		actions.append(f"Video calling: Prioritising {count_nice} communication process")

	elif workload_clean == "idle":
		target_proc = set(COMPILERS + IDES + GAMES + BROWSERS + CALLS)
		
		count_nice = 0
		count_aff = 0
		all_cores = list(range(total_cores))

		# Iterate through currently running active processes
		for p in unique_processes:
				proc_name = p["name"].lower()
				
				# Check if the running process is one of our managed applications
				if any(target in proc_name for target in target_proc):
						# Reset CPU nice priority to baseline (0)
						count_nice += prioritise_process(p["name"], 0)
						
						# Reset CPU affinity across all available cores
						count_aff += pin_process_to_cores(p["name"], all_cores)
						
						# Release from Idle I/O to Best Effort (Value 7)
						set_io_priority(p["name"], 'b', 7)

		actions.append(f"Idle: Restored {count_nice} running workload process(es) to normal priority and granted full core affinity across {count_aff} core(s).")


	if len(actions) > 0:
		try:
			log_optimization_result(workload, confidence, actions, explanation)
			print(f"Optimization Successful: {actions[-1]}")
			verifier_thread = threading.Thread(target=verify_and_rollback, args=(pre_state, workload, baseline_mean, baseline_std), daemon=True)
			verifier_thread.start()
			return True
		except Exception as e:
			print(f"Database logging error :{e}")
	return True

#reads 'route' proc file and indentifies acctive network interface, with a fallback to ethernet
def get_active_network_interface() -> str:
		try:
				with open("/proc/net/route") as f:
						for line in f:
								fields = line.strip().split()
								if len(fields) >= 4 and fields[1] == '00000000' and int(fields[3], 16) & 2:  #to ensure that the route has an active gateway and is not an idle or local route
										return fields[0]
		except Exception:
				pass
		return "eth0"


def set_network_fair_queuing(enable: bool) -> bool:
		"""Uses subprocess library for Fair Queuing with the help of tc (Traffic control tool) command."""
		try:
				interface = get_active_network_interface()
				cmd = f"sudo tc qdisc add dev {interface} root fq_codel" if enable else f"sudo tc qdisc del dev {interface} root"
				subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
				return True
		except Exception:
				return False


#assigns a process to a specific core via cpu affinity
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


def set_io_priority(proc_name: str, io_class: str, io_value: int = 0) -> int:
	optimised_count = 0
	for proc in psutil.process_iter(attrs=["pid", "name"]):
		current_pid = proc.info["pid"]
		try:
			current_name = proc.info["name"] or ""
			if proc_name.lower() in current_name.lower():
				process_obj = psutil.Process(current_pid)
				try:
					if io_class.lower() == 'b':
						process_obj.ionice(psutil.IOPRIO_CLASS_BE, io_value)
						optimised_count += 1
					elif io_class.lower() == 'r':
						process_obj.ionice(psutil.IOPRIO_CLASS_RT, io_value)
						optimised_count += 1
					elif io_class.lower() == 'i':
						process_obj.ionice(psutil.IOPRIO_CLASS_IDLE)
						optimised_count += 1
				except (AttributeError, ValueError):
					continue
		except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
			continue
	return optimised_count


#retrieves core details and returns as 2 lists
def get_cores():
		p_cores = []
		e_cores = []
		
		# Intel specific hardware path: searches for file and coverts a range such as 1-3 into a list [1,2,3]
		if os.path.exists("/sys/devices/cpu_core/cpus") and os.path.exists("/sys/devices/cpu_atom/cpus"):
				with open("/sys/devices/cpu_core/cpus", "r") as f:
						for r in f.read().strip().split(','):
								if '-' in r:
										start, end = map(int, r.split('-'))
										p_cores.extend(range(start, end+1))
								else:
										p_cores.append(int(r))
				with open("/sys/devices/cpu_atom/cpus", "r") as f:
						for r in f.read().strip().split(','):
								if '-' in r:
										start, end = map(int, r.split('-'))
										e_cores.extend(range(start, end+1))
								else:
										e_cores.append(int(r))

				return p_cores, e_cores

		base_path = "/sys/devices/system/cpu/"
		frequencies = {} #dictionary that stores cpu_id: frequency pairs
		
		if os.path.exists(os.path.join(base_path, "cpu0", "cpufreq")):
				for folder in os.listdir(base_path):
						if folder.startswith("cpu") and folder[3:].isdigit():  #checking for file names such as cpu0, cpu1 etc.
								cpu_id = int(folder[3:])
								freq_file = os.path.join(base_path, folder, "cpufreq/cpuinfo_max_freq")
								if os.path.exists(freq_file):
										with open(freq_file, "r") as f:
												frequencies[cpu_id] = int(f.read().strip())
												
				unique_speeds = sorted(list(set(frequencies.values())))
				
				# If we have distinct frequencies, it's a hybrid architecture having P and E cores
				if len(unique_speeds) > 1:
						p_cores = [cpu for cpu, freq in frequencies.items() if freq == max(unique_speeds)]
						e_cores = [cpu for cpu, freq in frequencies.items() if freq == min(unique_speeds)]
						
		return p_cores, e_cores #returns empty lists if p and e core bifurcation does not exist


def log_optimization_result(workload: str, confidence: float, actions: list[str], explanation: str = ""):
		"""Log all optimisation events to the focusos_events database table."""
		conn = None
		try:
				conn = sqlite3.connect(DB_PATH)
				cur = conn.cursor()
				cur.execute("""
						CREATE TABLE IF NOT EXISTS focusos_events (
								timestamp  REAL,
								workload   TEXT,
								confidence REAL,
								actions    TEXT
						)
				""")
				try:
						cur.execute("ALTER TABLE focusos_events ADD COLUMN explanation TEXT")
				except sqlite3.OperationalError:
						pass  # Column already exists
				
				cur.execute(
						"""INSERT INTO focusos_events (timestamp, workload, confidence, actions, explanation)
							 VALUES (?, ?, ?, ?, ?)""",
						(time.time(), workload, confidence, json.dumps(actions), explanation)
				)
				conn.commit()
		except Exception as e:
				print(f"Database logging error: {e}")
		finally:
				if conn is not None:
						conn.close()
