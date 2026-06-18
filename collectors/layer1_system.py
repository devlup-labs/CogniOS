import psutil
import time
from datetime import datetime,timezone
# collects metriics 
def collect_layer1_metrics():
    timestamp = datetime.now(timezone.utc).isoformat()
    cpu_usage_percent = psutil.cpu_percent(interval=None)
    cpu_times = psutil.cpu_times()
    cpu_user_time = cpu_times.user
    cpu_system_time = cpu_times.system
    cpu_idle_time = cpu_times.idle
    cpu_iowait_time = getattr(cpu_times, 'iowait', None)  # iowait for Linux only
    cpu_busy_time=cpu_user_time + cpu_system_time
    vmem=psutil.virtual_memory()
    memory_percent=vmem.percent
    memory_used=vmem.used
    memory_available=vmem.available
    memory_cached=getattr(vmem, 'cached', 0)    #cached and buffers not available in the mac and windows
    memory_buffers=getattr(vmem, 'buffers', 0)  
    swap=psutil.swap_memory()
    swap_percent=swap.percent
    swap_sin=swap.sin
    swap_sout=swap.sout
    disk_usage=psutil.disk_usage('/').percent
    disk_io=psutil.disk_io_counters()
    disk_read=disk_io.read_count / 1024 if disk_io else 0
    disk_write=disk_io.write_count / 1024 if disk_io else 0
    disk_read_time=disk_io.read_time if disk_io else 0
    disk_write_time=disk_io.write_time if disk_io else 0
    net_io=psutil.net_io_counters()
    net_bytes_sent=net_io.bytes_sent if net_io else 0
    net_bytes_received=net_io.bytes_recv if net_io else 0
    net_packets_sent=net_io.packets_sent if net_io else 0
    net_packets_received=net_io.packets_recv if net_io else 0
    net_errs=(net_io.errin + net_io.errout) if net_io else 0
    net_drops=(net_io.dropin + net_io.dropout) if net_io else 0
    try:
        load_avg1, load_avg5, load_avg15=psutil.getloadavg()
    except AttributeError:
        load_avg1=load_avg5=load_avg15=None
    #initialising the process_type_count variables
    total_processes=0
    running_processes=0
    sleeping_processes=0
    zombie_processes=0
    for p in psutil.process_iter(['status']):
        total_processes+= 1
        try:
            status=p.info['status']
            if status==psutil.STATUS_RUNNING:
                running_processes+=1
            elif status==psutil.STATUS_SLEEPING:
                sleeping_processes+=1
            elif status==psutil.STATUS_ZOMBIE:
                zombie_processes+=1
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            pass
    # putting temp vars in conditions sensors might not be available for all the syst
    try:
        temps=psutil.sensors_temperatures()
        if 'coretemp' in temps and temps['coretemp']:
            avg_temp=temps['coretemp'][0].current
            max_temp=temps['coretemp'][0].high
        else:
            avg_temp=None
            max_temp=None
    except Exception:
        avg_temp=None
        max_temp=None
    try:
        battery=psutil.sensors_battery()
        if battery:
            battery_percent=battery.percent
        else:
            battery_percent=None
    except Exception:
        battery_percent=None
# freq , ctx_switches are not available on all systems
    try:
        freq=psutil.cpu_freq()
        cpu_current_freq=freq.current if freq else None
    except Exception:
        cpu_current_freq=None
    
    try:
        cpu_ctx_switches=psutil.cpu_stats().ctx_switches
    except Exception:
        cpu_ctx_switches=None

    return {
        "timestamp": timestamp,
        "cpu_usage_percent": cpu_usage_percent,
        "cpu_current_freq": cpu_current_freq,
        "cpu_user_time": cpu_user_time,
        "cpu_system_time": cpu_system_time,
        "cpu_idle_time": cpu_idle_time,
        "cpu_iowait_time": cpu_iowait_time,
        "cpu_busy_time": cpu_busy_time,
        "cpu_ctx_switches": cpu_ctx_switches,
        "memory_percent": memory_percent,
        "memory_used":memory_used,
        "memory_available":memory_available,
        "memory_cached":memory_cached,
        "memory_buffers":memory_buffers,
        "swap_percent":swap_percent,
        "swap_sin":swap_sin,
        "swap_sout":swap_sout,
        "disk_usage_percent":disk_usage,
        "disk_read":disk_read,
        "disk_write":disk_write,
        "disk_read_time":disk_read_time,
        "disk_write_time":disk_write_time,
        "net_bytes_sent":net_bytes_sent,
        "net_bytes_received":net_bytes_received,
        "net_packets_sent":net_packets_sent,
        "net_packets_received":net_packets_received,
        "net_errs":net_errs,
        "net_drops":net_drops,
        "load_avg1":load_avg1,
        "load_avg5":load_avg5,
        "load_avg15":load_avg15,
        "total_processes":total_processes,
        "running_processes":running_processes,
        "sleeping_processes":sleeping_processes,
        "zombie_processes":zombie_processes,
        "avg_temp":avg_temp,
        "max_temp":max_temp,
        "battery_percent":battery_percent
    }
if __name__ == "__main__":
    import json
    metrics = collect_layer1_metrics()
    print(json.dumps(metrics, indent=4))