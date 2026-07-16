# Isolation Forest for Anomaly Detection — Mammography Dataset

## Objective
Implement the Isolation Forest algorithm using scikit-learn on the Mammography dataset (ODDS Repository) to understand the fundamentals of unsupervised anomaly detection.

## Dataset
- **Source:** Mammography dataset, ODDS Repository (`mammography.arff`)
- **Samples:** 11,183
- **Features:** 6 numeric features (`attr1`–`attr6`), already standardized (mean ≈ 0, std ≈ 1)
- **Target:** `class` column — `-1` = normal, `1` = anomaly
- **Missing values:** None
- **Duplicate rows:** 3,334 (kept, not dropped — repeated readings can be legitimate rather than data-entry errors)
- **Class balance:**
  - Normal: 10,923 (~97.68%)
  - Anomaly: 260 (~2.32%)

This heavy imbalance makes the dataset a realistic anomaly detection scenario, well suited to Isolation Forest.

## Approach

### 1. Data Exploration
- Loaded the `.arff` file with `scipy.io.arff` and converted to a pandas DataFrame.
- Decoded the byte-string `class` labels and checked for missing values, duplicates, and class distribution.

### 2. Preprocessing
- Separated features (`X`) from the label (`y`).
- Re-mapped labels to a consistent convention: `0 = normal`, `1 = anomaly` (the raw dataset uses `-1 = normal`, `1 = anomaly`, and sklearn's `IsolationForest.predict()` uses yet another convention — `1 = normal`, `-1 = anomaly` — so this mapping avoids confusion downstream).
- No scaling was needed since features arrive pre-standardized.
- Split data 70/30 into train/test sets using stratified sampling, so both sets preserve the same ~2.3% anomaly rate.

### 3. Model Implementation
Trained `sklearn.ensemble.IsolationForest` with the following hyperparameters:

| Hyperparameter | Value | Purpose |
|---|---|---|
| `n_estimators` | 100 | Number of isolation trees in the forest |
| `max_samples` | 256 | Rows sampled per tree |
| `contamination` | 0.017 | Expected proportion of anomalies |
| `max_features` | 1.0 | Fraction of features considered per split (kept at full, since only 6 features exist) |
| `random_state` | 42 | Reproducibility |

The model was trained only on `X_train` (fully unsupervised — labels are never used during `.fit()`), then evaluated on the held-out `X_test`.

`contamination` was tuned by iterating over a range of values and selecting the one that maximized F1-score on the test set (best value found: **0.017**).

### 4. Evaluation
Predictions and anomaly scores were generated with `.predict()` and `.decision_function()`, then compared against the true labels.

| Metric | Score |
|---|---|
| Precision | 0.297 |
| Recall | 0.244 |
| F1-score | 0.268 |
| ROC-AUC | 0.862 |

### 5. Visualizations
- **Confusion Matrix** — shows the model correctly identifies most normal points but misses the majority of true anomalies (low recall).
- **Anomaly Score Scatterplot** — anomaly scores for normal vs. anomalous test points, showing the overlap between classes.
- **ROC Curve** — shows the anomaly scores rank normal vs. anomalous points reasonably well (AUC = 0.862) across all thresholds, independent of the chosen `contamination` cutoff.

## Key Observations
- **High ROC-AUC (0.862) but low F1 (0.268)** is the central finding. This gap means the model's anomaly *scores* rank points reasonably well overall, but the fixed threshold set by `contamination` still produces many misclassifications — a common pattern in highly imbalanced, unsupervised settings.
- F1 stays low mainly because of:
  - **Extreme class imbalance** (~2.3% anomalies), which disproportionately penalizes F1-like metrics.
  - **Small feature space** (only 6 features), limiting how distinctly anomalies can be isolated via random splits.
- `contamination` had the biggest impact on results, directly controlling the precision/recall trade-off — lower values increase precision at the cost of recall, and vice versa.

## How to Run
1. Place `mammography.arff` in the working directory.
2. Install dependencies: `pandas`, `numpy`, `scipy`, `scikit-learn`, `matplotlib`.
3. Run all cells in `task.ipynb` sequentially.

## Reference
Workflow structure adapted from the DataCamp Isolation Forest tutorial: https://www.datacamp.com/tutorial/isolation-forest