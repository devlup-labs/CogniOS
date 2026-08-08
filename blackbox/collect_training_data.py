import sys
import time
import json
from pathlib import Path

sys.path.insert(0, '.')

from blackbox.recorder import get_blackbox_conn, get_recent_rows
from blackbox.feature_engineering import extract_feature_vector
from config import TRAINING_DATA_PATH, COLLECT_INTERVAL_SEC, ROWS_PER_VECTOR

def collect_and_append(conn) -> bool:
    """Extract one feature vector from the most recent rows and append it.
    Returns True if a vector was written, False if still warming up."""
    rows = get_recent_rows(conn, n=ROWS_PER_VECTOR)
    vec = extract_feature_vector(rows)
    if vec is None:
        return False

    record = {"timestamp": time.time(), "vector": vec}
    with open(TRAINING_DATA_PATH, 'a') as f:
        f.write(json.dumps(record) + "\n")
    return True


def count_existing_vectors() -> int:
    path = Path(TRAINING_DATA_PATH)
    if not path.exists():
        return 0
    with open(path) as f:
        return sum(1 for _ in f)


def main():
    conn = get_blackbox_conn()
    Path(TRAINING_DATA_PATH).parent.mkdir(parents=True, exist_ok=True)

    existing = count_existing_vectors()
    hours_so_far = existing * COLLECT_INTERVAL_SEC / 3600
    print(f"[collector] Starting. {existing} vectors already collected "
          f"(~{hours_so_far:.1f}h of prior data).")
    print(f"[collector] Writing to: {TRAINING_DATA_PATH}")
    print(f"[collector] Sampling every {COLLECT_INTERVAL_SEC}s. Ctrl+C to stop.\n")

    written = 0
    try:
        while True:
            ok = collect_and_append(conn)
            if ok:
                written += 1
                total = existing + written
                hours = total * COLLECT_INTERVAL_SEC / 3600
                if written % 20 == 0:  # progress ping every ~10 min
                    print(f"[collector] {total} vectors total (~{hours:.1f}h). Still running...")
            time.sleep(COLLECT_INTERVAL_SEC)
    except KeyboardInterrupt:
        total = existing + written
        hours = total * COLLECT_INTERVAL_SEC / 3600
        print(f"\n[collector] Stopped. {total} vectors saved (~{hours:.1f}h) "
              f"in {TRAINING_DATA_PATH}")


if __name__ == "__main__":
    main()