"""Isolation Forest anomaly model for OS Doctor."""
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pandas as pd
from sqlalchemy import create_engine
import os
import joblib
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import shap

expected_columns = [
    "id",                              

    "cpu_usage_percent_gradient",
    "cpu_usage_percent",
    "cpu_iowait_time_gradient",
    "cpu_iowait_time",            
    "memory_percent_gradient",
    "memory_percent",             
    "disk_read_mb_s_gradient",
    "disk_read_mb_s",             
    "disk_write_mb_s_gradient",
    "disk_write_mb_s",            
    "net_rate_mb_s_gradient",
    "net_rate_mb_s",               
    "running_processes_gradient",
    "running_processes",
    "cpu_usage_percent_deviation", 
    "cpu_ctx_switches_deviation",
    "cpu_ctx_switches",          
    "memory_percent_deviation",            
    "swap_percent_deviation",
    "swap_percent",              
    "load_avg_1_deviation",
    "load_avg_1",                
    "avg_temp_deviation",
    "avg_temp",
    "num_threads_deviation",
    "num_threads",
    "psi_metrics_cpu_deviation",
    "psi_metrics_cpu",
    "psi_metrics_mem_deviation",
    "psi_metrics_mem",
    "psi_metrics_io_deviation",
    "psi_metrics_io",             

    "timestamp", 
                   
    "cpu_1_cpu_peak_gradient",
    "cpu_1_cpu_peak",             
    "cpu_2_cpu_peak_gradient",
    "cpu_2_cpu_peak",             
    "cpu_3_cpu_peak_gradient",
    "cpu_3_cpu_peak",             
    "cpu_4_cpu_peak_gradient",
    "cpu_4_cpu_peak",             
    "cpu_5_cpu_peak_gradient",
    "cpu_5_cpu_peak",             
    "ram_1_peak_gradient",
    "ram_1_peak",                 
    "ram_1_open_fds_gradient",
    "ram_1_open_fds",             
    "ram_2_peak_gradient",
    "ram_2_peak",                 
    "ram_2_open_fds_gradient",
    "ram_2_open_fds",             
    "ram_3_peak_gradient",
    "ram_3_peak",                 
    "ram_3_open_fds_gradient",
    "ram_3_open_fds",             
    "ram_4_peak_gradient",
    "ram_4_peak",                 
    "ram_4_open_fds_gradient",
    "ram_4_open_fds",             
    "ram_5_peak_gradient",
    "ram_5_peak",                 
    "ram_5_open_fds_gradient",
    "ram_5_open_fds"
]

# Convert SQL-Table to Pandas DataFrame
def train_isolation_forest_model():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    db_path = os.path.join(parent_dir, "os_doctor_copy.db")
    engine = create_engine(f"sqlite:///{db_path}")

    df = pd.read_sql_table(
        table_name="os_doctor_train",
        con=engine,
    )

    # Dropping timestamp as it is TEXT
    # print("Columns before dropping timestamp and id:", df.columns)
    df.columns = expected_columns
    features = df[expected_columns]
    features = features.drop(columns=["timestamp", "id"])

    # Dropping rows with any cell = Null
    features = features.dropna()
    # print(df.info)

    # Scaling
    scaler = StandardScaler()
    scaler.set_output(transform="pandas")  # To get dataframe as output instead of numpy array
    features = scaler.fit_transform(features)
    # print(df)

    #HyperParameters 
    n_estimators = 100
    contamination = 0.1
    sample_size = 256
    random_state = 42
    max_features = 7 # It is better to set max_features = sqrt(total features)
    model = IsolationForest(n_estimators=n_estimators, contamination=contamination,
                                max_samples=sample_size, random_state=random_state, max_features=max_features)

    # print(df)
    model.fit(features)

    # joblib.dump(scaler, 'scaler.joblib')
    # joblib.dump(model, 'iso_forest_model.joblib')
    # print("Model saved successfully.")

    df['anomaly'] = model.predict(features)
    df['anomaly_score'] = model.decision_function(features)
    df['anomaly'].value_counts()

    normal = df[df['anomaly'] == 1]
    anomalies = df[df["anomaly"] == -1]

    # print(normal.describe())

    normal_sample = normal_sample = np.random.choice(normal.index,size=220,replace=False)
    sample = np.append(anomalies.index,normal_sample)

    # print(len(sample))

    # masker = shap.maskers.Tabular(max_samples=246)
    explainer = shap.Explainer(model.decision_function, features)
    shap_values = explainer(features.iloc[sample])

    abs_shap = np.abs(shap_values.values)

    global_mean = abs_shap.mean(axis=0)

    df_global_importance = pd.DataFrame({
        'feauture': features.columns,
        'global_importance': global_mean
    })

    df_global = df_global_importance.sort_values(by='global_importance')

    print(df_global.describe())

    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)

# Print your full DataFrame
    print(df_global)

# Optional: Reset the options back to default afterwards
    pd.reset_option('display.max_rows')
    pd.reset_option('display.max_columns')
    pd.reset_option('display.width')

    # # shap.plots.waterfall(shap_values[0])
    # # # shap.plots.waterfall(shap_values[100])
    # # # shap.plots.waterfall(shap_values[20])
    # plt.figure(figsize=(14,20))
    # shap.plots.waterfall(shap_values, max_display=62, show=False)
    # plt.tight_layout()
    # plt.show()

