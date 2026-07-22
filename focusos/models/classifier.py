import os
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import xgboost as xgb

CURRENT_FILE = os.path.abspath(__file__)
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(CURRENT_FILE)), "models_saved")
DATASET_PATH = os.path.join(MODELS_DIR, "pseudo_labeled_dataset.csv")

FEATURE_COLUMNS = [
    "cpu_mean",
    "cpu_max",
    "cpu_variance",
    "ram_mean",
    "ram_growth_rate",
    "network_mean",
    "disk_io_mean",
    "process_count_mean",
    "thread_count_mean",
    "vscode_active",
    "browser_active",
    "compiler_active",
]
class WorkloadPredictor:
    def __init__(self, models_dir=MODELS_DIR):
        self.models_dir = models_dir

        # Load scaler (cluster_trainer.py saves feature_scaler.pkl)
        scaler_path = os.path.join(models_dir, "feature_scaler.pkl")
        if not os.path.exists(scaler_path):
            scaler_path = os.path.join(models_dir, "scaler.pkl")

        if not os.path.exists(scaler_path):
            raise FileNotFoundError(
                f"[WorkloadPredictor] Scaler artifact missing in '{models_dir}'. Please run cluster_trainer.py first."
            )

        self.scaler = joblib.load(scaler_path)
        self.label_encoder = joblib.load(os.path.join(models_dir, "label_encoder.pkl"))
        self.kmeans = joblib.load(os.path.join(models_dir, "kmeans_model.pkl"))
        self.xgb = xgb.XGBClassifier()

        xgb_path = os.path.join(models_dir, "xgboost_model.json")
        if not os.path.exists(xgb_path):
            raise FileNotFoundError(
                f"[WorkloadPredictor] XGBoost model missing at '{xgb_path}'. Please run classifier.py training first."
            )
        self.xgb.load_model(xgb_path)

    def predict(self, features_df: pd.DataFrame) -> dict:
        if features_df is None or features_df.empty:
            return None

        # scaling the incoming feature_vector
        scaled = self.scaler.transform(features_df)
        
        # predicting the workload using xgboost
        probs = self.xgb.predict_proba(scaled)[0]
        pred_idx = int(np.argmax(probs))
        workload_name = str(self.label_encoder.inverse_transform([pred_idx])[0])

        # calculating the confidence
        confidence = float(probs[pred_idx] * 100)

        # predicting the cluster id
        cluster_id = int(self.kmeans.predict(scaled)[0])

        return {
            "workload": workload_name,
            "confidence": round(confidence, 2),
            "cluster_id": cluster_id,
        }



def train_classifier():
    print("\n" + "═"*60)
    print(" FocusOS — XGBoost Classifier Training")
    print("═"*60)
    
    if not os.path.exists(DATASET_PATH):
        print(f"[classifier] Error: Pseudo-labeled dataset not found at {DATASET_PATH}.")
        print("[classifier] Please run cluster_trainer(ref).py first to generate it.")
        return
        
    df = pd.read_csv(DATASET_PATH)
    print(f"[classifier] Loaded training dataset with {len(df)} samples.")
    
    # split features and labels
    X = df[FEATURE_COLUMNS].values
    y_raw = df["workload_label"].values

    # fix scale features before training 
    scaler_path=os.path.join(MODELS_DIR,"feature_scaler.pkl")
    if os.path.exists(scaler_path):
        scaler=joblib.load(scaler_path)
        X=scaler.transform(X_raw)
        print("[Classifier]Scaled feature using saved feature_scaler.pkl")
    else:
        print("[Classifier] WARNING!!! feature_scaler.pkl not found Training on unscaled features")
        X=X_raw

    
    # encode categorical labels to integers
    le = LabelEncoder()
    y = le.fit_transform(y_raw)
    # save the label encoder
    le_path = os.path.join(MODELS_DIR, "label_encoder.pkl")
    joblib.dump(le, le_path)
    print(f"[classifier] Saved LabelEncoder to {le_path}")
    
    # split into train and test sets (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"[classifier] Split data into {len(X_train)} training and {len(X_test)} testing samples.")
    
    # train XGBoost classifier
    print("[classifier] Fitting XGBClassifier...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
        eval_metric='mlogloss'
    )
    model.fit(X_train, y_train)
    
    # evaluate classifier
    y_pred = model.predict(X_test)
    accuracy = np.mean(y_pred == y_test)
    print(f"[classifier] Test Set Accuracy: {accuracy*100:.2f}%")
    
    print("\n[classifier] Classification Report:")
    target_names = [str(c) for c in le.classes_]
    print(classification_report(y_test, y_pred, target_names=target_names))
    
    print("\n[classifier] Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    
    # saving trained model
    model_path = os.path.join(MODELS_DIR, "xgboost_model.json")
    model.save_model(model_path)
    print(f"\n[classifier] Trained XGBoost model saved to {model_path}")

if __name__ == "__main__":
    train_classifier()
