"""
FocusOS CPU Topology Detection Module
Inspects Linux kernel sysfs (/sys/devices/system/cpu) and /proc/cpuinfo to determine
exact physical core count, logical CPUs, SMT/hyperthreading topology, and truthfully
identifies heterogeneous (Intel hybrid P/E or ARM big.LITTLE) vs homogeneous architectures.
"""

import os
import re
from typing import Dict, List, Optional, Tuple, NamedTuple


class CpuTopologyInfo:
    def __init__(
        self,
        logical_cpus: int,
        physical_cores: int,
        sockets: int,
        threads_per_core: int,
        core_map: Dict[int, List[int]],
        is_hybrid: bool,
        architecture_type: str,
        p_cores: List[int],
        e_cores: List[int],
        model_name: str,
        vendor_id: str,
        frequencies_khz: Dict[int, int],
        raw_data_available: bool,
    ):
        self.logical_cpus = logical_cpus
        self.physical_cores = physical_cores
        self.sockets = sockets
        self.threads_per_core = threads_per_core
        self.core_map = core_map
        self.is_hybrid = is_hybrid
        self.architecture_type = architecture_type
        self.p_cores = p_cores
        self.e_cores = e_cores
        self.model_name = model_name
        self.vendor_id = vendor_id
        self.frequencies_khz = frequencies_khz
        self.raw_data_available = raw_data_available

    def to_dict(self) -> dict:
        return {
            "logical_cpus": self.logical_cpus,
            "physical_cores": self.physical_cores,
            "sockets": self.sockets,
            "threads_per_core": self.threads_per_core,
            "core_map": self.core_map,
            "is_hybrid": self.is_hybrid,
            "architecture_type": self.architecture_type,
            "p_cores": self.p_cores,
            "e_cores": self.e_cores,
            "model_name": self.model_name,
            "vendor_id": self.vendor_id,
            "frequencies_khz": self.frequencies_khz,
            "raw_data_available": self.raw_data_available,
        }


def detect_cpu_topology(base_sysfs: str = "/sys/devices/system/cpu") -> CpuTopologyInfo:
    """
    Detects detailed CPU topology from Linux sysfs and /proc/cpuinfo.
    Returns honest representation of physical cores, logical threads, and core types.
    """
    logical_cpus = 0
    core_map: Dict[int, List[int]] = {}
    socket_set = set()
    frequencies: Dict[int, int] = {}
    model_name = "Unknown CPU"
    vendor_id = "Unknown"
    raw_available = False

    # 1. Parse /proc/cpuinfo for model name and vendor
    if os.path.exists("/proc/cpuinfo"):
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip()
                        v = v.strip()
                        if k == "model name" and model_name == "Unknown CPU":
                            model_name = v
                        elif k == "vendor_id" and vendor_id == "Unknown":
                            vendor_id = v
        except Exception:
            pass

    # 2. Inspect sysfs topology
    if os.path.exists(base_sysfs):
        try:
            entries = os.listdir(base_sysfs)
            cpu_dirs = sorted([d for d in entries if d.startswith("cpu") and d[3:].isdigit()], key=lambda x: int(x[3:]))
            if cpu_dirs:
                raw_available = True
                logical_cpus = len(cpu_dirs)

                for cdir in cpu_dirs:
                    cpu_idx = int(cdir[3:])
                    topo_dir = os.path.join(base_sysfs, cdir, "topology")

                    if os.path.exists(topo_dir):
                        # Core ID
                        cid_file = os.path.join(topo_dir, "core_id")
                        if os.path.exists(cid_file):
                            try:
                                with open(cid_file) as f:
                                    core_id = int(f.read().strip())
                                    core_map.setdefault(core_id, []).append(cpu_idx)
                            except Exception:
                                pass

                        # Socket / Package ID
                        pkg_file = os.path.join(topo_dir, "physical_package_id")
                        if os.path.exists(pkg_file):
                            try:
                                with open(pkg_file) as f:
                                    socket_set.add(int(f.read().strip()))
                            except Exception:
                                pass

                    # CPU Frequency
                    freq_file = os.path.join(base_sysfs, cdir, "cpufreq/cpuinfo_max_freq")
                    if os.path.exists(freq_file):
                        try:
                            with open(freq_file) as f:
                                frequencies[cpu_idx] = int(f.read().strip())
                        except Exception:
                            pass
        except Exception:
            raw_available = False

    # Fallbacks if sysfs is missing or incomplete
    if logical_cpus == 0:
        import multiprocessing
        logical_cpus = multiprocessing.cpu_count() or 1

    physical_cores = len(core_map) if core_map else logical_cpus
    sockets = len(socket_set) if socket_set else 1
    threads_per_core = max(1, logical_cpus // max(1, physical_cores))

    # Sort threads inside core map
    for cid in core_map:
        core_map[cid].sort()

    # 3. Detect Intel Hybrid Architecture via PMU sysfs
    p_cores: List[int] = []
    e_cores: List[int] = []
    is_hybrid = False
    arch_type = "HOMOGENEOUS"

    intel_core_file = "/sys/devices/cpu_core/cpus"
    intel_atom_file = "/sys/devices/cpu_atom/cpus"
    if os.path.exists(intel_core_file) and os.path.exists(intel_atom_file):
        try:
            with open(intel_core_file) as f:
                p_cores = _parse_cpu_list(f.read().strip())
            with open(intel_atom_file) as f:
                e_cores = _parse_cpu_list(f.read().strip())
            if p_cores and e_cores:
                is_hybrid = True
                arch_type = "HYBRID_INTEL"
        except Exception:
            pass

    # 4. Detect ARM big.LITTLE or heterogeneous capacities via cpu_capacity
    if not is_hybrid and os.path.exists(base_sysfs):
        capacities = {}
        for cdir in os.listdir(base_sysfs):
            if cdir.startswith("cpu") and cdir[3:].isdigit():
                c_idx = int(cdir[3:])
                cap_file = os.path.join(base_sysfs, cdir, "cpu_capacity")
                if os.path.exists(cap_file):
                    try:
                        with open(cap_file) as f:
                            capacities[c_idx] = int(f.read().strip())
                    except Exception:
                        pass
        if len(set(capacities.values())) > 1:
            max_cap = max(capacities.values())
            p_cores = [c for c, cap in capacities.items() if cap == max_cap]
            e_cores = [c for c, cap in capacities.items() if cap < max_cap]
            if p_cores and e_cores:
                is_hybrid = True
                arch_type = "HETEROGENEOUS_ARM"

    # 5. Detect heterogeneous frequencies as secondary indicator
    if not is_hybrid and len(set(frequencies.values())) > 1:
        max_freq = max(frequencies.values())
        min_freq = min(frequencies.values())
        # Only treat as distinct core types if frequency difference is significant (>25%)
        if max_freq > min_freq * 1.25:
            p_cores = [c for c, f in frequencies.items() if f == max_freq]
            e_cores = [c for c, f in frequencies.items() if f < max_freq]
            if p_cores and e_cores:
                is_hybrid = True
                arch_type = "HETEROGENEOUS_FREQ"

    # If architecture is homogeneous, truthfully represent all cores as unified
    if not is_hybrid:
        p_cores = list(range(logical_cpus))
        e_cores = []
        if threads_per_core > 1:
            arch_type = "HOMOGENEOUS_SMT"
        else:
            arch_type = "HOMOGENEOUS"

    return CpuTopologyInfo(
        logical_cpus=logical_cpus,
        physical_cores=physical_cores,
        sockets=sockets,
        threads_per_core=threads_per_core,
        core_map=core_map,
        is_hybrid=is_hybrid,
        architecture_type=arch_type,
        p_cores=p_cores,
        e_cores=e_cores,
        model_name=model_name,
        vendor_id=vendor_id,
        frequencies_khz=frequencies,
        raw_data_available=raw_available,
    )


def _parse_cpu_list(cpu_str: str) -> List[int]:
    """Parses a Linux sysfs CPU list string (e.g. '0-3,7,9-11') into a sorted integer list."""
    cpus = set()
    for item in cpu_str.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            start, end = map(int, item.split("-"))
            cpus.update(range(start, end + 1))
        else:
            cpus.add(int(item))
    return sorted(list(cpus))


# Singleton cache
_CACHED_TOPOLOGY: Optional[CpuTopologyInfo] = None


def get_topology() -> CpuTopologyInfo:
    """Returns cached CPU topology info (detected once at runtime)."""
    global _CACHED_TOPOLOGY
    if _CACHED_TOPOLOGY is None:
        _CACHED_TOPOLOGY = detect_cpu_topology()
    return _CACHED_TOPOLOGY
