# Pull Request

## Related Issue

Closes # 

---

## Task Summary

Provide a brief overview of your implementation.

- What did you implement?
Implemented the Isolation Forest model for detecting anomalous mammography data

- What approach did you follow?
I extracted the data from a csv file,
selected the features to detect the anomaly
used dropna() to eliminate rows with missing values
used StandardScaler to scale features
split the data into test and train (test=0.1)
trained the isolation forest model
used iso_forest.predict() to get the number of anomaly

---

## Dataset

- [x] Mammography
- [ ] Shuttle

Dataset Source: OpenML

---

## Preprocessing

Describe any preprocessing performed.

Handled missing values with pandas' built in function df.dropna()
which drops rows with NaN

Selected only first 6 rows for isolation forest model as
originally the dataset was created for classification and the 7th column contained labels

Used Standard Scaler for scaling the data for better accuracy
Examples:
- Missing value handling
- Feature scaling
- Encoding
- Feature selection

---

## Model Configuration

List the important hyperparameters used.

| Hyperparameter | Value |
|---------------|-------|
| n_estimators | 100 |
| contamination | 0.009 |
| max_samples | 256 |
| max_features | 6 |
| random_state | 42 |

---

## Evaluation Results

| Metric | Value |
|--------|-------|
| Precision | |
| Recall | |
| F1-score | |
| ROC-AUC (Optional) | |

---

## Visualizations

Attach **at least 2 plots** from your analysis.
![alt text](image.png)
Examples:
- PCA visualization
- Anomaly score distribution
- Confusion Matrix
- Correlation heatmap
- Feature distributions
- Hyperparameter comparison
- Precision/Recall/F1 comparison

---

## Key Observations

Briefly summarize:

- What worked well?
- Which hyperparameter had the biggest impact?
Contamination had the biggest impact, as it directly affects the number of anomalies detected
- Any interesting findings?
- Challenges faced (if any)

---

## Checklist

- [x] Code runs successfully
- [ ] Notebook (`.ipynb`) included
- [x] Code is well-commented
- [ ] README/documentation updated
- [ ] At least **2 plots** included
- [ ] PR is linked to the corresponding issue