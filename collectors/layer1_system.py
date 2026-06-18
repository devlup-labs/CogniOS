import psutil
import time
from datetime import datetime,timezone
from utils.helpers import rate_mb_s

# a dictionary to store previous values
_last = {
    "time": None,
    "disk_read_bytes": None,
    "disk_write_bytes": None,
    "net_bytes_sent": None,
    "net_bytes_recv": None,
}


# collects metriics 
def collect_layer1_metrics():
    now = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()

    # CPU Metrics
    cpu_usage_percent = psutil.cpu_percent(interval=None)
    cpu_times = psutil.cpu_times()
    cpu_user_time = cpu_times.user
    cpu_system_time = cpu_times.system
    cpu_idle_time = cpu_times.idle
    cpu_iowait_time = getattr(cpu_times, 'iowait', None)  # iowait for Linux only
    cpu_busy_time=cpu_user_time + cpu_system_time

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

    # Memory Metrics

    vmem=psutil.virtual_memory()
    memory_percent=vmem.percent
    memory_used=vmem.used
    memory_available=vmem.available
    memory_cached=getattr(vmem, 'cached', None)    #cached and buffers not available in the mac and windows
    memory_buffers=getattr(vmem, 'buffers', None)  # None- like value nahi mili aur 0- ek valid value hai

    swap=psutil.swap_memory()
    swap_percent=swap.percent
    swap_sin=swap.sin
    swap_sout=swap.sout

    # Disk Metrics

    # same reason, in windows "/" is not valid
    try:
        disk_usage=psutil.disk_usage('/').percent
    except Exception:
        disk_usage=None

    try:
        disk_io = psutil.disk_io_counters()
    except Exception:
        disk_io=None

    disk_read=None
    disk_write=None
    disk_read_time=None
    disk_write_time=None

    if disk_io is not None:
        elapsed_time = (now - _last["time"]) if _last["time"] else 0
        disk_read = rate_mb_s(disk_io.read_bytes, _last["disk_read_bytes"], elapsed_time)
        disk_write = rate_mb_s(disk_io.write_bytes, _last["disk_write_bytes"], elapsed_time)
        disk_read_time = getattr(disk_io, 'read_time', None)
        disk_write_time = getattr(disk_io, 'write_time', None)

        _last["disk_read_bytes"] = disk_io.read_bytes
        _last["disk_write_bytes"] = disk_io.write_bytes


    # Network Metrics
    net_io=psutil.net_io_counters()
    net_bytes_sent=net_io.bytes_sent if net_io else 0
    net_bytes_received=net_io.bytes_recv if net_io else 0
    net_packets_sent=net_io.packets_sent if net_io else 0
    net_packets_received=net_io.packets_recv if net_io else 0
    net_errs=(net_io.errin + net_io.errout) if net_io else 0
    net_drops=(net_io.dropin + net_io.dropout) if net_io else 0

    net_rate_mb_s=None
    if _last["time"]:
        elapsed_time = now - _last["time"]
        sent_rate = rate_mb_s(net_bytes_sent, _last["net_bytes_sent"], elapsed_time)
        recv_rate = rate_mb_s(net_bytes_received, _last["net_bytes_recv"], elapsed_time)
        if sent_rate is not None and recv_rate is not None:
            net_rate_mb_s = sent_rate + recv_rate
    
    _last["net_bytes_sent"] = net_bytes_sent
    _last["net_bytes_recv"] = net_bytes_received
    _last["time"] = now


    #b Load Average Metrics 
    try:
        load_avg1, load_avg5, load_avg15=psutil.getloadavg()

    # except AttributeError: # catches specific error when getloadavg is not support 
    except Exception:
        load_avg1=load_avg5=load_avg15=None

    #initialising the process_type_count variables
    total_processes, running_processes, sleeping_processes, zombie_processes = 0, 0, 0, 0
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


    # Temperature and Battery Metrics (if available)
    temp_avg, temp_max = None, None
    try:
        temps=psutil.sensors_temperatures()
        all_temps=[t.current for sensors in temps.values() for t in sensors]
        if all_temps:
            temp_avg = sum(all_temps) / len(all_temps)
            temp_max = max(all_temps)
    except Exception:
        pass
    battery_percent=None
    try:
        battery=psutil.sensors_battery()
        if battery:
            battery_percent=battery.percent
    except Exception:
        pass

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
        "avg_temp":temp_avg,
        "max_temp":temp_max,
        "battery_percent":battery_percent
    }

if __name__ == "__main__":
    import json
    metrics = collect_layer1_metrics()
    print(json.dumps(metrics, indent=4))