import enum
import glob
import logging
import psutil
import time
from datetime import datetime,timezone
import sys
import os
#adding path to locate the utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils
from utils.helpers import rate_mb_s

logger = logging.getLogger(__name__)

# a dictionary to store previous values
_last = {
    "time": None,
    "disk_read_bytes": None,
    "disk_write_bytes": None,
    "net_bytes_sent": None,
    "net_bytes_recv": None,
    # OS Doctor counters (cumulative kernel counters -> turned into rates)
    "invol_by_pid": None,      # {pid: involuntary ctx switches}
    "cpu_iowait": None,
    "cpu_total": None,
    "disk_read_count": None,
    "disk_write_count": None,
    "disk_read_time": None,
    "disk_write_time": None,
    "swap_sout": None,
    "allocstall": None,
    "pgmajfault": None,
    "throttle": None,
    "tcp_retrans": None,
}

# ---------------- OS Doctor readers (Linux only) ----------------
# Every reader returns None when the file is missing. None is stored as NULL
# in the DB and becomes 0.0 only later, in featuring.py.

_warned = set()

def _warn_once(source, message):
    # Log a missing source only once, not every second.
    if source not in _warned:
        _warned.add(source)
        logger.warning(message)


def _read_procs_running():
    # /proc/stat line: "procs_running 3"
    try:
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("procs_running"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    _warn_once("procs_running", "/proc/stat procs_running not readable; nr_running_per_core will be 0.")
    return None


def _read_psi(resource):
    # /proc/pressure/<resource> lines:
    #   some avg10=0.02 avg60=0.10 avg300=0.07 total=954949
    #   full avg10=0.00 avg60=0.00 avg300=0.00 total=0
    result = {"some": None, "full": None}
    try:
        with open(f"/proc/pressure/{resource}") as f:
            for line in f:
                parts = line.split()
                for part in parts[1:]:
                    if part.startswith("avg10="):
                        result[parts[0]] = float(part.split("=")[1])
    except (OSError, ValueError, IndexError):
        _warn_once(f"psi_{resource}", f"/proc/pressure/{resource} not readable "
                   "(PSI disabled in kernel?); its PSI features will be 0.")
    return result


def _read_vmstat():
    # Returns (allocstall_total, pgmajfault). Newer kernels split allocstall by
    # zone (allocstall_normal, allocstall_movable, ...), so sum all of them.
    allocstall, pgmajfault = None, None
    try:
        with open("/proc/vmstat") as f:
            for line in f:
                key, value = line.split()
                if key.startswith("allocstall"):
                    allocstall = (allocstall or 0) + int(value)
                elif key == "pgmajfault":
                    pgmajfault = int(value)
    except (OSError, ValueError):
        pass
    if allocstall is None or pgmajfault is None:
        _warn_once("vmstat", "/proc/vmstat counters missing; reclaim/major-fault rates will be 0.")
    return allocstall, pgmajfault


def _read_tcp_retrans():
    # /proc/net/snmp has two "Tcp:" lines: a header line and a values line.
    try:
        with open("/proc/net/snmp") as f:
            tcp_lines = [line.split() for line in f if line.startswith("Tcp:")]
        header, values = tcp_lines[0], tcp_lines[1]
        return int(values[header.index("RetransSegs")])
    except (OSError, ValueError, IndexError):
        _warn_once("tcp", "/proc/net/snmp RetransSegs not readable; tcp_retrans_rate will be 0.")
        return None


def _read_system_open_fds():
    # /proc/sys/fs/file-nr: "<allocated> <free> <max>"
    try:
        with open("/proc/sys/fs/file-nr") as f:
            return int(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        _warn_once("file_nr", "/proc/sys/fs/file-nr not readable; open_fds_gradient will be 0.")
        return None


def _read_throttle_count():
    # Intel only. Sum of per-CPU core throttle counters (cumulative).
    paths = glob.glob("/sys/devices/system/cpu/cpu[0-9]*/thermal_throttle/core_throttle_count")
    if not paths:
        _warn_once("throttle", "No thermal_throttle counters in /sys (e.g. AMD CPU or VM); "
                   "thermal_throttling_events will be 0.")
        return None
    total = 0
    for path in paths:
        try:
            with open(path) as f:
                total += int(f.read().strip())
        except (OSError, ValueError):
            pass
    return total


def _counter_rate(current, key, elapsed):
    # Rate of a cumulative counter: (now - previous) / seconds.
    # Negative deltas (counter reset) are clamped to 0.
    previous = _last[key]
    if current is None or previous is None or not elapsed:
        return None
    return max(0.0, (current - previous) / elapsed)
# collects metriics 
def collect_layer1_metrics():
    now = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()
    # seconds since the previous tick; None on the first tick after start.
    # Computed here because _last["time"] is overwritten in the network section.
    elapsed = (now - _last["time"]) if _last["time"] else None

    invol_by_pid = {}   # {pid: involuntary context switches}, filled below
    #process
    try:
        procs = {}
        for p in psutil.process_iter(["name", "memory_percent"]):
            try:
                p.cpu_percent()
                procs[p.pid] = p
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(0.1)
        process_data = []
        num_threads=[]
        for pid, p in procs.items():
            try:
                # oneshot() reads /proc/<pid>/status once for num_threads and
                # num_ctx_switches instead of twice
                with p.oneshot():
                    cpu = round(p.cpu_percent(), 2)
                    mem = round(p.info.get("memory_percent") or 0.0, 2)
                    if cpu > 0.5 or mem > 0.5:
                        process_data.append((p.info.get("name"), cpu, mem))
                    num_threads.append(p.num_threads())
                    try:
                        invol_by_pid[pid] = p.num_ctx_switches().involuntary
                    except psutil.AccessDenied:
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        process_data = []
        num_threads= []

    # Involuntary context switch rate. Only PIDs present in both ticks count,
    # so a process that exits does not make the total drop (fake negative rate).
    involuntary_context_switch_rate = None
    prev_invol = _last["invol_by_pid"]
    if prev_invol is not None and elapsed:
        delta = 0
        for pid, count in invol_by_pid.items():
            if pid in prev_invol:
                delta += max(0, count - prev_invol[pid])
        involuntary_context_switch_rate = delta / elapsed
    _last["invol_by_pid"] = invol_by_pid
    # CPU Metrics
    cpu_usage_percent = psutil.cpu_percent(interval=None)
    cpu_times = psutil.cpu_times()
    cpu_user_time = cpu_times.user
    cpu_system_time = cpu_times.system
    cpu_idle_time = cpu_times.idle
    cpu_iowait_time = getattr(cpu_times, 'iowait', None)  # iowait for Linux only
    cpu_busy_time=cpu_user_time + cpu_system_time

    # iowait as a percent of all CPU time in the last tick.
    # cpu_iowait_time above is seconds since boot and only grows.
    # guest/guest_nice are already inside user/nice, so they are not added twice.
    cpu_total = sum(v for k, v in cpu_times._asdict().items() if k not in ("guest", "guest_nice"))
    cpu_iowait_percent = None
    if cpu_iowait_time is not None and _last["cpu_iowait"] is not None:
        total_delta = cpu_total - _last["cpu_total"]
        if total_delta > 0:
            cpu_iowait_percent = max(0.0, (cpu_iowait_time - _last["cpu_iowait"]) / total_delta * 100)
    _last["cpu_iowait"] = cpu_iowait_time
    _last["cpu_total"] = cpu_total

    # Runnable tasks per CPU core
    procs_running = _read_procs_running()
    cores = os.cpu_count() or 1
    nr_running_per_core = (procs_running / cores) if procs_running is not None else None

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

    # Swap-out rate in MB/s (swap_sout is cumulative bytes since boot)
    swap_out_rate = rate_mb_s(swap_sout, _last["swap_sout"], elapsed or 0)
    _last["swap_sout"] = swap_sout

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
    io_latency=None

    if disk_io is not None:
        elapsed_time = (now - _last["time"]) if _last["time"] else 0
        disk_read = rate_mb_s(disk_io.read_bytes, _last["disk_read_bytes"], elapsed_time)
        disk_write = rate_mb_s(disk_io.write_bytes, _last["disk_write_bytes"], elapsed_time)
        disk_read_time = getattr(disk_io, 'read_time', None)
        disk_write_time = getattr(disk_io, 'write_time', None)

        _last["disk_read_bytes"] = disk_io.read_bytes
        _last["disk_write_bytes"] = disk_io.write_bytes

        # Average ms per disk operation in the last tick:
        # (change in read+write time) / (change in read+write count)
        if _last["disk_read_count"] is not None and elapsed:
            ops = (disk_io.read_count - _last["disk_read_count"]) + (disk_io.write_count - _last["disk_write_count"])
            busy_ms = (disk_io.read_time - _last["disk_read_time"]) + (disk_io.write_time - _last["disk_write_time"])
            io_latency = max(0.0, busy_ms / ops) if ops > 0 else 0.0   # no operations -> no waiting
        _last["disk_read_count"] = disk_io.read_count
        _last["disk_write_count"] = disk_io.write_count
        _last["disk_read_time"] = disk_io.read_time
        _last["disk_write_time"] = disk_io.write_time


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
    uninterruptible_d_state_count = 0   # D state: blocked in the kernel, usually on I/O
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
            elif status==psutil.STATUS_DISK_SLEEP:
                uninterruptible_d_state_count+=1
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

    # Pressure stall information (avg10 = average over the last 10 seconds)
    cpu_psi = _read_psi("cpu")
    memory_psi = _read_psi("memory")
    io_psi = _read_psi("io")

    # /proc/vmstat counters -> per-second rates
    allocstall, pgmajfault = _read_vmstat()
    direct_reclaim_rate = _counter_rate(allocstall, "allocstall", elapsed)
    major_page_fault_rate = _counter_rate(pgmajfault, "pgmajfault", elapsed)
    _last["allocstall"] = allocstall
    _last["pgmajfault"] = pgmajfault

    # TCP retransmissions per second
    tcp_retrans = _read_tcp_retrans()
    tcp_retrans_rate = _counter_rate(tcp_retrans, "tcp_retrans", elapsed)
    _last["tcp_retrans"] = tcp_retrans

    # Thermal throttle events per second (Intel only; None elsewhere)
    throttle = _read_throttle_count()
    thermal_throttling_events = _counter_rate(throttle, "throttle", elapsed)
    _last["throttle"] = throttle

    # System-wide allocated file handles (the gradient is taken in featuring.py)
    system_open_fds = _read_system_open_fds()

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

        "net_rate_mb_s":net_rate_mb_s,
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
        "battery_percent":battery_percent,
        "process_data":process_data,
        "num_threads":num_threads,

        # OS Doctor inputs. Keys match db.LAYER1_NEW_COLUMNS exactly.
        "nr_running_per_core": nr_running_per_core,
        "involuntary_context_switch_rate": involuntary_context_switch_rate,
        "uninterruptible_d_state_count": uninterruptible_d_state_count,
        "cpu_iowait_percent": cpu_iowait_percent,
        "cpu_psi_some_avg10": cpu_psi["some"],
        "memory_psi_full_avg10": memory_psi["full"],
        "io_psi_some_avg10": io_psi["some"],
        "io_psi_full_avg10": io_psi["full"],
        "direct_reclaim_rate": direct_reclaim_rate,
        "major_page_fault_rate": major_page_fault_rate,
        "swap_out_rate": swap_out_rate,
        "io_latency": io_latency,
        "system_open_fds": system_open_fds,
        "thermal_throttling_events": thermal_throttling_events,
        "tcp_retrans_rate": tcp_retrans_rate,
    }

if __name__ == "__main__":
    import json
    from db import create_connection, write_layer1, LAYER1_NEW_COLUMNS
    from config import DB_PATH

    metrics = collect_layer1_metrics()
    print("Gathered metrics:")
    print(json.dumps(metrics, indent=4))

    print("\nSaving metrics to database...")
    try:
        conn = create_connection(DB_PATH)
        write_layer1(
            conn, 
            metrics['timestamp'], 
            metrics['cpu_usage_percent'], 
            metrics['cpu_current_freq'], 
            metrics['cpu_user_time'], 
            metrics['cpu_system_time'], 
            metrics['cpu_idle_time'], 
            metrics['cpu_iowait_time'], 
            metrics['cpu_busy_time'], 
            metrics['cpu_ctx_switches'], 
            metrics['memory_percent'], 
            metrics['memory_used'], 
            metrics['memory_available'], 
            metrics['memory_cached'], 
            metrics['memory_buffers'], 
            metrics['swap_percent'], 
            metrics['swap_sin'], 
            metrics['swap_sout'], 
            metrics['disk_usage_percent'], 
            metrics['disk_read'], 
            metrics['disk_write'], 
            metrics['disk_read_time'], 
            metrics['disk_write_time'], 
            metrics['load_avg1'], 
            metrics['load_avg5'], 
            metrics['load_avg15'], 
            metrics['total_processes'], 
            metrics['running_processes'], 
            metrics['sleeping_processes'], 
            metrics['zombie_processes'], 
            metrics['avg_temp'], 
            metrics['max_temp'], 
            metrics['battery_percent'],
            metrics['net_rate_mb_s'],
            metrics['net_bytes_sent'],
            metrics['net_bytes_received'],
            metrics['net_packets_sent'],
            metrics['net_packets_received'],
            metrics['net_errs'],
            metrics['net_drops'],
            json.dumps(metrics['process_data']),
            sum(metrics["num_threads"]),   # was json.dumps(list) -> text in an INTEGER column
            **{col: metrics.get(col) for col in LAYER1_NEW_COLUMNS}
        )
        print(f"Successfully saved Layer 1 metrics to database table 'layer1_sys' in {DB_PATH}!")
    except Exception as e:
        print(f"Error saving to database: {e}")