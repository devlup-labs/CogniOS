"""Isolation Forest anomaly model for OS Doctor."""
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix, precision_recall_curve, average_precision_score
from sklearn.preprocessing import StandardScaler
from sklearn import set_config
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

# Dropping timestamp as it is TEXT
df = df.drop(columns=["timestamp", "id"])

# Dropping Columns with all values = 0.0
df = df.loc[:, (df != 0.0).any(axis=0)]

# Dropping rows with any cell = Null
df = df.dropna()
# print(df.info)

# Scaling
set_config(transform_output='pandas') # To get dataframe as output instead of numpy array
scaler = StandardScaler()
df = scaler.fit_transform(df)
# print(df)

# Correlation Matrix
correlation_matrix = df.corr()
print(correlation_matrix)
sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt=".2f")
plt.show()

#HyperParameters 
n_estimators = 100
contamination = 0.1
sample_size = 256
random_state = 42
max_features = 15 # It is better to set max_features = sqrt(total features)
iso_forest = IsolationForest(n_estimators=n_estimators, contamination=contamination,
                             max_samples=sample_size, random_state=random_state, max_features=max_features)

# iso_forest.fit(df)