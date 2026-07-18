# Fill this in after reading inspect_clusters() output from cluster_trainer.py.
# Keys are cluster IDs from KMeans (always 0 to N_CLUSTERS-1 = 0 to 4)
# Values are the workload name that we will decided from reading the cluster summary

CLUSTER_TO_WORKLOAD = {
    0: "Coding",       # ← replace this based on our cluster_trainer output
    1: "Compiling",   
    2: "Idle",         
    3: "Video_Call",   
    4: "Gaming",       
}

#FUNCTION to check the correct mapping here
# Reverse mapping — useful for debugging
# e.g. WORKLOAD_TO_CLUSTER["Coding"] → 0
WORKLOAD_TO_CLUSTER = {v: k for k, v in CLUSTER_TO_WORKLOAD.items()}


VALID_WORKLOADS = list(CLUSTER_TO_WORKLOAD.values())# All valid workload names as a list



# OPTIMIZATION PROFILES

WORKLOAD_OPTIMIZATION_PROFILE = {
    "Coding": {
        "process_keywords":    ["code", "code-insiders", "vsls-agent", "sublime", "vim", "nvim"],
        "deprioritize_others": True,
        "nice_value":          -5,
        "description":         "Boosting editor and language server priority",
    },
    "Compiling": {
        "process_keywords":    ["gcc", "g++", "clang", "make", "ninja", "rustc", "javac", "cc1"],
        "deprioritize_others": True,
        "nice_value":          -10,
        # Compiling benefits most from CPU priority 
        "description":         "Boosting compiler processes for faster build times",
    },
    "Video_Call": {
        "process_keywords":    ["zoom", "teams", "chrome", "firefox", "brave", "msedge"],
        "deprioritize_others": True,
        "nice_value":          -5,
        "description":         "Boosting video call app for smooth audio and video",
    },
    "Gaming": {
        "process_keywords":    [],
        "deprioritize_others": True,
        "nice_value":          0,
        "description":         "Deprioritizing background processes for smoother gameplay",
    },
    "Idle": {
        "process_keywords":    [],
        "deprioritize_others": False,
        "nice_value":          0,
        # System is idle — no point changing priorities
        "description":         "System idle — no optimization applied",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS — imported by other modules
# ─────────────────────────────────────────────────────────────────────────────

def get_workload_name(cluster_id: int) -> str:
    """
    Converts a KMeans cluster ID (integer) to a workload name (string).
    RETURNS:
        Workload name string e.g. "Coding"
        Returns "Unknown_<id>" if cluster_id not in mapping 
    """
    return CLUSTER_TO_WORKLOAD.get(int(cluster_id), f"Unknown_{cluster_id}")


def get_cluster_id(workload_name: str) -> int:
    """
    Reverse of get_workload_name — converts workload name to cluster ID.
    RETURNS:
        cluster_id integer, or -1 if not found
    """
    return WORKLOAD_TO_CLUSTER.get(workload_name, -1)


def get_optimization_profile(workload_name: str) -> dict:
    """
    Returns the optimization profile for a given workload name.
    RETURNS:
        dict with keys: process_keywords, deprioritize_others,
                        nice_value, description
        Returns a safe no-op profile for unknown workloads.
    """
    return WORKLOAD_OPTIMIZATION_PROFILE.get(workload_name, {
        "process_keywords":    [],
        "deprioritize_others": False,
        "nice_value":          0,
        "description":         f"Unknown workload '{workload_name}' — no optimization",
    })


def validate_mapping() -> bool:
    """
    Sanity check that your CLUSTER_TO_WORKLOAD is properly filled in.
 RETURNS:
        True if everything looks good, False if there are issues.
    """
    # Import here to avoid circular import issues at module load time
    try:
        from focusos.models.cluster_trainer import N_CLUSTERS
    except ImportError:
        N_CLUSTERS = 5  # fallback

    all_ok = True

    # Check 1: correct cluster IDs present
    expected_ids = set(range(N_CLUSTERS))
    actual_ids   = set(CLUSTER_TO_WORKLOAD.keys())
    if expected_ids != actual_ids:
        print(f"[label_mapper] ERROR: Expected IDs {expected_ids}, got {actual_ids}")
        print(f"  Missing: {expected_ids - actual_ids}")
        print(f"  Extra:   {actual_ids - expected_ids}")
        all_ok = False

    # Check 2: no duplicate workload names
    names = list(CLUSTER_TO_WORKLOAD.values())
    if len(names) != len(set(names)):
        duplicates = [n for n in names if names.count(n) > 1]
        print(f"[label_mapper] ERROR: Duplicate workload names: {duplicates}")
        all_ok = False

    # Check 3: all workloads have optimization profiles
    for name in names:
        if name not in WORKLOAD_OPTIMIZATION_PROFILE:
            print(f"[label_mapper] WARNING: '{name}' has no optimization profile. "
                  f"Optimizer will apply no-op for this workload.")

    # Check 4: no placeholder names
    placeholder_check = [n for n in names if n.startswith("Unknown") or n == ""]
    if placeholder_check:
        print(f"[label_mapper] WARNING: Placeholder names found: {placeholder_check}")
        print(f"  Did you forget to fill in CLUSTER_TO_WORKLOAD?")
        all_ok = False

    if all_ok:
        print(f"[label_mapper] Mapping OK: {CLUSTER_TO_WORKLOAD}")

    return all_ok


#running the file
if __name__ == "__main__":
    print("Validating label_mapper.py...\n")
    validate_mapping()

    print("\nTesting get_workload_name():")
    for cid in range(5):
        name = get_workload_name(cid)
        profile = get_optimization_profile(name)
        print(f"  Cluster {cid} → '{name}'  |  nice={profile['nice_value']}  "
              f"|  keywords={profile['process_keywords'][:2]}...")
