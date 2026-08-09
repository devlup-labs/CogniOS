"""Isolation Forest anomaly model for OS Doctor."""
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pandas as pd
from sqlalchemy import create_engine
import os
import joblib

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
    db_path = os.path.join(parent_dir, "os_doctor.db")
    engine = create_engine(f"sqlite:///{db_path}")

    df = pd.read_sql_table(
        table_name="os_doctor_train",
        con=engine,
    )

    # Dropping timestamp as it is TEXT
    # print("Columns before dropping timestamp and id:", df.columns)
    df.columns = expected_columns
    df = df.drop(columns=["timestamp", "id"])

    # Dropping rows with any cell = Null
    df = df.dropna()
    # print(df.info)

    # Scaling
    scaler = StandardScaler()
    scaler.set_output(transform="pandas")  # To get dataframe as output instead of numpy array
    df = scaler.fit_transform(df)
    # print(df)

    #HyperParameters 
    n_estimators = 100
    contamination = 0.01
    sample_size = 256
    random_state = 42
    max_features = 7 # It is better to set max_features = sqrt(total features)
    model = IsolationForest(n_estimators=n_estimators, contamination=contamination,
                                max_samples=sample_size, random_state=random_state, max_features=max_features)

    # print(df)
    model.fit(df)

    joblib.dump(scaler, 'scaler.joblib')
    joblib.dump(model, 'iso_forest_model.joblib')
    print("Model saved successfully.")