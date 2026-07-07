import collectors.layer1_system as layer1_system
import collectors.layer2_process as layer2_process
from utils import helpers
import db
import sqlite3
import subprocess
import json

DB_PATH = "cognios_telemetry.db"
conn = db.create_connection(DB_PATH)

#collects relevant telemetry data from layer 1 table and returns it as a dictionary
def collect_snapshot(conn):
	conn.row_factory = sqlite3.Row
	cursor = conn.cursor()
	
	cursor.execute("SELECT timestamp, cpu_usage_percent, memory_percent, net_rate_mb_s, total_processes, process_data, num_threads FROM layer1_sys ORDER BY timestamp DESC LIMIT 1")
	row = cursor.fetchone()
	result_dict = {}
	if row is not None:
		result_dict = dict(row)
		
		# 1. Safely decode the JSON string from SQLite into a Python list
		if result_dict.get('process_data'):
			try:
				processes = json.loads(result_dict['process_data'])
				
				#Sorting the list and retaining top 5 entries
				result_dict['process_data'] = sorted(processes, key=lambda x: x['cpu'], reverse=True)[:5]
			except (json.JSONDecodeError, TypeError):
				result_dict['process_data'] = []
		else:
			result_dict['process_data'] = []

		if result_dict.get('num_threads'):
			try:
				result_dict['num_threads'] = json.loads(result_dict['num_threads'])
			except (json.JSONDecodeError, TypeError):
				result_dict['num_threads'] = []
		else:
			result_dict['num_threads'] = []	
			
	return result_dict

	
#returns the active window name in lowercase, example: 'firefox'
def get_foreground_app():
    try:
        window_id = subprocess.check_output(["xdotool", "getactivewindow"]).decode().strip()
        temp_window = subprocess.check_output(["xdotool", "getwindowname", window_id])
        window = temp_window.decode("utf-8").strip().lower()
        if " - " in window:
            window = window.split(" - ")[-1]
        return window
    except subprocess.CalledProcessError:
        window = "unknown"
        return window
    
        
#returns 2 list[dict], one for top cpu and one for top memory
def get_top_processes(n = 5):
    top_cpu, top_mem, _ = layer2_process.collect_process_telemetry()
    
    top_cpu_filtered = []
    top_mem_filtered = []
    
    cpu_keys = ['pid', 'name', 'cpu_percent', 'thread_count', 'status']
    mem_keys = ['pid', 'name', 'memory_percent', 'thread_count', 'status']
    
    top_cpu_filtered = [{key: d[key] for key in cpu_keys if key in d} for d in top_cpu]
    top_mem_filtered = [{key: d[key] for key in mem_keys if key in d} for d in top_mem]
    
    return top_cpu_filtered, top_mem_filtered

    
#layer 1 must also be run as a daemon to get all outputs
if __name__ == "__main__":
    
    import asyncio
    async def collector_test():
        print("Testing collector as sandbox\nPress Ctrl + C to finish test run\n")
        count = 0
        try:
            while True:
                start_time = asyncio.get_event_loop().time()
                count+=1
                
                snapshot = collect_snapshot(conn)
                print(snapshot)                
                foreground_app = get_foreground_app()
                print(foreground_app)
                
                """if count%5 == 0:
                    top_cpu, top_mem = get_top_processes(n = 5)
                    print(top_cpu)
                    print(top_mem)"""
                    
                print("_"*30)
                execution_time = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, 1.0 - execution_time)
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            print("Task cancelled")
        finally:
            conn.close()
            print("Finished execution")
            
    try:
        asyncio.run(collector_test())
    except KeyboardInterrupt:
        print("Finished collector test run")