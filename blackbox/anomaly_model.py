#Isolation Forest wrapper (sklearn)

import numpy as np
import pickle
from pathlib import Path
from sklearn.ensemble import IsolationForest
from blackbox.feature_engineering import extract_feature_vector, FEATURE_NAMES


MODEL_PATH = "blackbox/if_model.pkl"


def train(normal_feature_vectors: list[list[float]],
          contamination: float = 0.05) -> IsolationForest:
    X = np.array(normal_feature_vectors)
    model = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100
    )
    model.fit(X)
    return model


def predict(model: IsolationForest,
            feature_vector: list[float]) -> tuple[int, float]:
    X = np.array([feature_vector])
    label = int(model.predict(X)[0])
    score = float(model.decision_function(X)[0])
    return label, round(score, 4)


def anomaly_severity(score: float) -> int:
    return max(0, min(100, int((-score + 0.5) * 100)))


def save_model(model: IsolationForest,
               path: str = MODEL_PATH) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(model, f)
    print(f"Model saved: {path}")


def load_model(path: str = MODEL_PATH) -> IsolationForest:
    with open(path, 'rb') as f:
        return pickle.load(f)