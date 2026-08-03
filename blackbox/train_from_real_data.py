import sys
import json
from pathlib import Path

sys.path.insert(0, '.')

from blackbox.anomaly_model import train, save_model, predict, load_model, MODEL_PATH
from blackbox.feature_engineering import FEATURE_NAMES
from config import TRAINING_DATA_PATH


def load_vectors():
    path = Path(TRAINING_DATA_PATH)
    if not path.exists():
        print(f"[train] ERROR: {TRAINING_DATA_PATH} not found. "
              f"Run the collector first: python3 -m blackbox.collect_training_data")
        sys.exit(1)

    vectors = []
    timestamps = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            vectors.append(record["vector"])
            timestamps.append(record["timestamp"])
    return vectors, timestamps


def main():
    vectors, timestamps = load_vectors()
    n = len(vectors)
    hours = n * 30 / 3600  # 30s interval per vector

    print(f"[train] Loaded {n} vectors (~{hours:.1f}h of real usage)")

    if n < 30:
        print("[train] WARNING: very little data — model quality will be poor. "
              "Consider collecting more before relying on this model.")

    print("[train] Training Isolation Forest...")
    model = train(vectors)
    save_model(model, MODEL_PATH)
    print(f"[train] Model saved to {MODEL_PATH}")

    # Quick sanity check: predict on the training data itself
    print("\n[train] Sanity check — predicting on training data:")
    labels = [predict(model, v)[0] for v in vectors]
    n_anomaly = sum(1 for l in labels if l == -1)
    pct_anomaly = 100 * n_anomaly / n
    print(f"  {n_anomaly}/{n} vectors flagged as anomalous ({pct_anomaly:.1f}%)")
    print(f"  (contamination=0.05 was requested, so ~5% is expected — "
          f"far more suggests noisy/varied data, far less suggests very uniform data)")

    # Show a few example predictions with details
    print("\n[train] Sample predictions:")
    for i in range(0, n, max(1, n // 5)):
        label, score = predict(model, vectors[i])
        tag = "ANOMALY" if label == -1 else "normal "
        cpu_mean = vectors[i][FEATURE_NAMES.index("mean_cpu")]
        cpu_max = vectors[i][FEATURE_NAMES.index("max_cpu")]
        print(f"  [{tag}] score={score:+.4f}  mean_cpu={cpu_mean:.1f}%  max_cpu={cpu_max:.1f}%")

    print("\n[train] Done. Model is ready for use in the daemon.")


if __name__ == "__main__":
    main()