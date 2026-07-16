"""Isolation Forest anomaly model for OS Doctor."""
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix, precision_recall_curve, average_precision_score
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import os
import matplotlib.pyplot as plt
import seaborn as sns

# Convert SQL-Table to Pandas DataFrame

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
db_path = os.path.join(parent_dir, "os_doctor.db")
engine = create_engine(f"sqlite:///{db_path}")

df = pd.read_sql_table(
    table_name="os_doctor_train",
    con=engine,
)

# print(df)

# Dropping timestamp as it is TEXT
df = df.drop(columns=["timestamp", "id"])

# Dropping Columns with all values = 0.0
df = df.loc[:, (df != 0.0).any(axis=0)]

#HyperParameters 
n_estimators = 100
contamination = 0.1
sample_size = 256
random_state = 42

iso_forest = IsolationForest(n_estimators=n_estimators, contamination=contamination,
                             max_samples=sample_size, random_state=random_state, max_features=10)

iso_forest.fit(df)