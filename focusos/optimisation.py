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


def apply_settings(p: psutil.Process, nice=None, affinity=None, io_class=None, io_value=0):
	applied = {'nice': False, 'affinity': False, 'io': False}
	if nice is not None:
		try:
			p.nice(nice)
			applied['nice'] = True
		except psutil.AccessDenied:
			print(f"Warning: Permission denied to set nice for PID {p.pid}")
		except Exception:
			pass
			
	if affinity is not None:
		try:
			p.cpu_affinity(affinity)
			applied['affinity'] = True
		except psutil.AccessDenied:
			print(f"Warning: Permission denied to set affinity for PID {p.pid}")
		except Exception:
			pass
			
	if io_class is not None:
		try:
			if io_class == 'b':
				p.ionice(psutil.IOPRIO_CLASS_BE, io_value)
			elif io_class == 'r':
				p.ionice(psutil.IOPRIO_CLASS_RT, io_value)
			elif io_class == 'i':
				p.ionice(psutil.IOPRIO_CLASS_IDLE)
			applied['io'] = True
		except (AttributeError, ValueError):
			pass
		except psutil.AccessDenied:
			print(f"Warning: Permission denied to set IO priority for PID {p.pid}")
		except Exception:
			pass
			
	return applied

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
	unique_pids = set(unique_processes_dict.keys())
	
	workload_clean = workload.lower().replace("_", " ")

	if workload_clean != "video call":
			set_network_fair_queuing(False)

	rules_exact = {}
	rules_top_bg = None
	bg_exclusions = set()
	all_cores = list(range(total_cores))

	# Define rules based on workload
	if workload_clean == "compiling":
		for c in COMPILERS:
			rules_exact[c.lower()] = {'nice': -12, 'affinity': foreground_cores, 'io_class': 'b', 'io_value': 3}
		for i in IDES:
			if i.lower() in rules_exact:
				rules_exact[i.lower()]['nice'] = -5
			else:
				rules_exact[i.lower()] = {'nice': -5}
		rules_top_bg = {'nice': 7, 'io_class': 'i', 'io_value': 0, 'affinity': background_cores}
		bg_exclusions = set([x.lower() for x in COMPILERS + IDES])

	elif workload_clean == "gaming":
		for g in GAMES:
			rules_exact[g.lower()] = {'nice': -10, 'affinity': foreground_cores, 'io_class': 'b', 'io_value': 1}
		rules_top_bg = {'nice': 10, 'io_class': 'i', 'io_value': 0, 'affinity': background_cores}
		bg_exclusions = set([x.lower() for x in GAMES])

	elif workload_clean == "coding":
		for i in IDES:
			rules_exact[i.lower()] = {'nice': -5, 'affinity': foreground_cores}
		for b in BROWSERS:
			rules_exact[b.lower()] = {'affinity': background_cores}
			
	elif workload_clean == "browsing":
		for b in BROWSERS:
			rules_exact[b.lower()] = {'nice': 0, 'affinity': foreground_cores}
		rules_top_bg = {'io_class': 'i', 'io_value': 0}
		bg_exclusions = set([x.lower() for x in BROWSERS])

	elif workload_clean == "video call":
		for c in CALLS:
			rules_exact[c.lower()] = {'nice': -5, 'affinity': foreground_cores}
		rules_top_bg = {'io_class': 'i', 'io_value': 0}
		bg_exclusions = set([x.lower() for x in CALLS])
		set_network_fair_queuing(True)
		
	elif workload_clean == "idle":
		for p in COMPILERS + IDES + GAMES + BROWSERS + CALLS:
			rules_exact[p.lower()] = {'nice': 0, 'affinity': all_cores, 'io_class': 'b', 'io_value': 7}

	# Apply rules in a single pass
	stats = {
		'nice': 0, 'affinity': 0, 'io': 0,
		'bg_nice': 0, 'bg_affinity': 0, 'bg_io': 0,
		'ide_nice': 0, 'browser_affinity': 0
	}

	for proc in psutil.process_iter(attrs=['pid', 'name']):
		try:
			pid = proc.info['pid']
			p_name = proc.info['name'] or ""
			p_name_lower = p_name.lower()
			
			applied = False
			
			if p_name_lower in rules_exact:
				rule = rules_exact[p_name_lower]
				res = apply_settings(psutil.Process(pid), **rule)
				if res['nice']: stats['nice'] += 1
				if res['affinity']: stats['affinity'] += 1
				if res['io']: stats['io'] += 1
				
				# Track specific counts for logging if needed
				if workload_clean == "coding":
					if p_name_lower in [x.lower() for x in BROWSERS] and res['affinity']:
						stats['browser_affinity'] += 1
					if p_name_lower in [x.lower() for x in IDES] and res['nice']:
						stats['ide_nice'] += 1
				applied = True
				
			if not applied and rules_top_bg and pid in unique_pids:
				if p_name_lower not in bg_exclusions:
					res = apply_settings(psutil.Process(pid), **rules_top_bg)
					if res['nice']: stats['bg_nice'] += 1
					if res['affinity']: stats['bg_affinity'] += 1
					if res['io']: stats['bg_io'] += 1
		except (psutil.NoSuchProcess, psutil.ZombieProcess):
			continue

	# Build logging actions
	if workload_clean == "compiling":
		if stats['nice'] > 0 or stats['bg_nice'] > 0:
			msg = []
			if stats['nice'] > 0:
				msg.append(f"Prioritised {stats['nice']} compiler(s)/IDE(s), pinned {stats['affinity']} to core(s) {foreground_cores}, set {stats['io']} to best effort IO")
			if stats['bg_nice'] > 0:
				msg.append(f"Deprioritised {stats['bg_nice']} bg process(es)")
			actions.append("; ".join(msg))
			
	elif workload_clean == "gaming":
		if stats['nice'] > 0 or stats['bg_nice'] > 0:
			msg = []
			if stats['nice'] > 0:
				msg.append(f"Prioritised {stats['nice']} game process(es), granted {stats['affinity']} full core affinity")
			if stats['bg_nice'] > 0:
				msg.append(f"Deprioritised {stats['bg_nice']} bg process(es)")
			actions.append("; ".join(msg))
			
	elif workload_clean == "coding":
		if stats['ide_nice'] > 0 or stats['browser_affinity'] > 0:
			actions.append(f"Prioritised {stats['ide_nice']} IDE process(es), pinned {stats['browser_affinity']} browser(s) to cores {background_cores}")
			
	elif workload_clean == "browsing":
		if stats['nice'] > 0 or stats['bg_io'] > 0:
			actions.append(f"Browsing: Restored {stats['nice']} browser(s) to normal priority, yielded IO for {stats['bg_io']} bg processes")

	elif workload_clean == "video call":
		if stats['nice'] > 0 or stats['bg_io'] > 0:
			actions.append(f"Video calling: Prioritised {stats['nice']} communication process(es), yielded IO for {stats['bg_io']} bg processes")

	elif workload_clean == "idle":
		if stats['nice'] > 0:
			actions.append(f"Idle: Restored {stats['nice']} running workload process(es) to normal priority and full core affinity")

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


def get_active_network_interface() -> str:
	try:
		if os.path.exists("/proc/net/route"):
			with open("/proc/net/route") as f:
				for line in f:
					fields = line.strip().split()
					if len(fields) >= 4 and fields[1] == '00000000' and int(fields[3], 16) & 2:
						return fields[0]
	except Exception:
		pass
	
	try:
		stats = psutil.net_if_stats()
		for iface, stat in stats.items():
			if stat.isup and iface != 'lo':
				return iface
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
