import os
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import umap

script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "focusos_training_data_v5.csv")
df = pd.read_csv(csv_path)
X = df.drop(columns=["workload_label"])
y = df["workload_label"]

Xs = StandardScaler().fit_transform(X)
sil = silhouette_score(Xs, y)
print("Silhouette (labels vs scaled features):", sil)

reducer = umap.UMAP(n_neighbors=15, min_dist=0.1, random_state=42)
emb = reducer.fit_transform(Xs)
# then scatter emb colored by y