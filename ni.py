import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.ensemble import IsolationForest
# from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score

# CSV File has been directly downloaded from OpenML

# Convert CSV to DataFrame
df = pd.read_csv("mammography.csv", header=None)
df.columns = ['col1', 'col2', 'col3', 'col4', 'col5', 'col6', 'col7']
df['col7'] = df['col7'].astype(str).str.replace("'", "").astype(int) #

count = df['col7'].value_counts()
print(count)
# -1 -> 10923
# 1 -> 260

# Select Features
features = df[['col1', 'col2', 'col3', 'col4', 'col5', 'col6']]

# Drop rows with any missing values

features = features.dropna()

# Training Parameters
n_estimators = 100
contamination = 0.023
sample_size = 256

# Feature Scaling
# X_train, X_test = train_test_split(features, test_size=0,random_state=42)

scaler = StandardScaler()
scaler.fit_transform(features)

# X_train_scaled = scaler.fit_transform(X_train)
# X_test_scaled = scaler.transform(X_test)

# print(X_train_scaled)
# print(X_train_scaled.shape)

# print(X_test_scaled)
# print(X_test_scaled.shape)

# Training Isolation Forest Model

iso_forest = IsolationForest(n_estimators=n_estimators, contamination=contamination,
                             max_samples=sample_size, random_state=42)

iso_forest.fit(features)



# Trying Prediction

df = df.loc[features.index].copy()
df['anomaly'] = iso_forest.predict(features) # raw anomaly predictions
df['anomaly_score'] = iso_forest.decision_function(features)
anomaly_count = df['anomaly'].value_counts()
print(anomaly_count)

# Precision Score
df['anomaly_mapped'] = df['anomaly'].map({1: 0, -1: 1})

precision = precision_score(df['col7'], df['anomaly_mapped'])
print(precision)

# # Plotting Data

# plt.figure(figsize=(50,10))

# normal = df[df['anomaly'] == 1]
# plt.scatter(normal.index, normal['anomaly_score'] , label='Normal')

# anomaly = df[df['anomaly'] == -1]
# plt.scatter(anomaly.index, anomaly['anomaly_score'], label='Anomaly')

# plt.xlabel('Instance')
# plt.ylabel('Anomaly Score')
# plt.legend()
# plt.show()