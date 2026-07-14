import pandas as pd
from scipy.io import arff
import matplotlib.pyplot as plt
from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, ConfusionMatrixDisplay

#Loading the shuttle dataset
data, meta = arff.loadarff("shuttle.arff")
df = pd.DataFrame(data)
target = pd.Series(df['class']).astype(int)

#Class 1 and 4 make up 93.94% of observations, hence they are classified as normal or 1
anomalies = target.apply(lambda x: 1 if x == 1 or x == 4 else -1)

#Dropping the class column as it is not needed for the model
df.drop('class', axis = 'columns', inplace = True)


#Scaling the data using RobustScaler
scale = RobustScaler().set_output(transform = "pandas")
df_scaled = scale.fit_transform(df)

#Calculating actual contamination:
total_entries = len(target)
no_of_anomalies = (anomalies == -1).sum()
contamination = no_of_anomalies/total_entries


#Applying isolation forest model, using approximate contamination of 6.05%
iso_forest = IsolationForest(n_estimators = 100, contamination = 0.0605, max_samples = 256, random_state = 42)
iso_forest.fit(df_scaled)
data = df.loc[df.index].copy()   #data stores the input data along with corresponding predicted labels
data['anomaly_score'] = iso_forest.decision_function(df_scaled)
data['anomaly'] = iso_forest.predict(df_scaled)


print("Here are the number of normal and anomaly values:")
print(data['anomaly'].value_counts())

#Now calculating precision, recall, f1 score, ROC-AUC value
precision = precision_score(anomalies, data['anomaly'], pos_label = -1)
print("Precision: ", precision)

recall = recall_score(anomalies, data['anomaly'], pos_label = -1)
print("Recall: ", recall)

f1 = f1_score(anomalies, data['anomaly'], pos_label = -1)
print("F1 Score: ", f1)

roc_auc = roc_auc_score(anomalies, data['anomaly_score'])
print("ROC-AUC value: ", roc_auc)


#Plotting a Confusion Matrix
ConfusionMatrixDisplay.from_predictions(anomalies, data['anomaly'], display_labels=["Anomaly", "Normal"], cmap=plt.cm.Blues)


# Visualization of the results through a scatter plot

plt.figure(figsize=(15, 10))

#'normal' stores all instances that are classified as (1)
normal = data[data['anomaly'] == 1]
plt.scatter(normal.index, normal['anomaly_score'], label='Normal', alpha=0.2)

#'anomalies' stores all instances that are classified as (-1)
anomalies = data[data['anomaly'] == -1]

plt.scatter(anomalies.index, anomalies['anomaly_score'], label='Anomaly', alpha=0.3)
plt.xlabel("Instance")
plt.ylabel("Anomaly Score")
plt.legend()
plt.show()