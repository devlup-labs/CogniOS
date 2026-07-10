# new things learnt
# precision_score(y_true, y_pred) both these values must be same for binary -> same tuple
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix, precision_recall_curve, average_precision_score

# CSV File has been directly downloaded from OpenML

# Convert CSV to DataFrame
df = pd.read_csv("mammography.csv", header=None)
df.columns = ['col1', 'col2', 'col3', 'col4', 'col5', 'col6', 'col7']
df['col7'] = df['col7'].astype(str).str.replace("'", "").astype(int) 

# count = df['col7'].value_counts()
# print(count)
# -1 -> 10923
# 1 -> 260

# Select Features
features = df[['col4', 'col5', 'col6']]

# Drop rows with any missing values

features = features.dropna()

# Training Parameters
n_estimators = 100
contamination = 0.023
sample_size = 256

# Feature Scaling

# scaler = StandardScaler()
# features = scaler.fit_transform(features)

# Train-Test split 
# No split applied for this dataset

# Training Isolation Forest Model

iso_forest = IsolationForest(n_estimators=n_estimators, contamination=contamination,
                             max_samples=sample_size, random_state=42, max_features=2)

iso_forest.fit(features)

# GETTING ANOMALY SCORES

df = df.loc[features.index].copy()
df['anomaly_score'] = iso_forest.decision_function(features)
df['scores'] = -df['anomaly_score']

# col7 encodes anomaly=1, normal=-1 (OpenML convention). Remap both the true
# labels and the model output (1=inlier, -1=outlier) to a shared 0/1 scale
# (1=anomaly) since sklearn's metrics require y_true and y_pred to share a
# label set, not just a matching pos_label.

df['y_true'] = df['col7'].map({1: 1, -1: 0})

# PRECISION RECALL CURVE

precisions, recalls, thresholds = precision_recall_curve(df['y_true'], df['scores'])

precisions = precisions[:-1] 
recalls = recalls[:-1]

f1_scores = 2 * ((precisions * recalls)/(precisions + recalls) + 1e-10)

best_idx = f1_scores.argmax()
best_threshold = thresholds[best_idx]

print(f"Best threshold: {best_threshold:.4f}")
print(f"Precision at best threshold: {precisions[best_idx]:.3f}")
print(f"Recall at best threshold: {recalls[best_idx]:.3f}")
print(f"F1 at best threshold: {f1_scores[best_idx]:.3f}")

# TESTING THE MODEL WITH "BEST THRESHOLD" VALUE
df['anomaly'] = np.where(df['scores'] >= best_threshold, 1, -1)

# CALCULATING EVALUATION SCORES

df['y_pred'] = df['anomaly'].map({1: 1, -1: 0})

p_score = precision_score(df['y_true'], df['y_pred'])
r_score = recall_score(df['y_true'], df['y_pred'])
f1 = f1_score(df['y_true'], df['y_pred'])
print(f"Precision: {p_score:.3f}")
print(f"Recall: {r_score:.3f}")
print(f"F1 Score: {f1:.3f}")

ap = average_precision_score(df['y_true'], df['scores'])
print(f"Average Precision: {ap:.3f}")

# PLOTTING CONFUSION MATRIX

cm = confusion_matrix(df['y_true'], df['y_pred'])

sns.heatmap(cm, annot=True, fmt= 'd', cmap='Blues')
plt.ylabel('actual')
plt.xlabel('predicted')

# SCATTERING DATA

plt.figure(figsize=(50,10))

normal = df[df['anomaly'] == -1]
plt.scatter(normal.index, normal['anomaly_score'] , label='Normal')

anomaly = df[df['anomaly'] == 1]
plt.scatter(anomaly.index, anomaly['anomaly_score'], label='Anomaly')

plt.xlabel('Instance')
plt.ylabel('Anomaly Score')
plt.legend()
plt.show()