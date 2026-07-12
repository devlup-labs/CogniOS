# Pull Request

## Related Issue

Closes #16

---

## Task Summary

Provide a brief overview of your implementation.

- What did you implement?
- I trained a model on the shuttle ODDS dataset using the isolation forest to detect the the anomalies in the dataset. 
- What approach did you follow?
- Firstly after importing the data and converted the data into the DataFrame i looked for the missing valeus(NaN) luckily there weren't any so there was almost no preprocessing required.
  Major Challenge i faced  during training of the model was recalling the correct syntax and some libs, I took some help from the medium page.To decide the best parameters values like         n_estimators,contamination and sample size i did some hard yakka, by running the loops to decide the n_estimators in range(1,700,50) luckily i got the highest f1 scores for values 101 and 151 but i took 100 because it had higher f1_score as well as auc_value both tending to one if i took approximaiton upto 2 decimal places.

---

## Dataset

- [ ] Mammography
- [x] Shuttle

Dataset Source:

---

## Preprocessing

Describe any preprocessing performed.

- Missing value handling - No,It has nil NaN values confirmed it by df.isnull().sum()==0
- Feature scaling - No isolation forest can handle without scaling.
- Encoding - No data contained the numeric values so not needed.
- Feature selection - No verly low dimensionality.

---

## Model Configuration

List the important hyperparameters used.

| Hyperparameter | Value |
|---------------|-------|
| n_estimators |100|
| contamination |0.075|
| max_samples |256|
| max_features |1|
| random_state |42|

---

## Evaluation Results

| Metric | Value |
|--------|-------|
| Precision |0.9332|
| Recall |0.9789|
| F1-score |0.955|
| ROC-AUC (Optional) |0.9975|

---

## Visualizations

Attach **at least 2 plots** from your analysis.

<img width="3063" height="2957" alt="anomalyscore" src="https://github.com/user-attachments/assets/435f65ba-3713-4eee-a5f8-229dcdef624f" />
<img width="1591" height="1403" alt="confusionmatrix" src="https://github.com/user-attachments/assets/54dbf8b6-1e82-4dab-97b6-4145b6f24558" />
<img width="1872" height="1403" alt="roc_auc_curve" src="https://github.com/user-attachments/assets/c5072c8e-060b-46ea-9f78-674df0df1436" />
<img width="1191" height="180" alt="Screenshot From 2026-07-13 02-28-36" src="https://github.com/user-attachments/assets/7cacdab4-2405-4c2f-97e0-99eb5f9eb483" />


---

## Key Observations

Briefly summarize:

- What worked well?
 - Preprocessing there wasn't any.
- Which hyperparameter had the biggest impact?
 - Contamination value.increasing it slightly helped me achieved the good f1_score,recall slight more auc_val.
- Challenges faced (if any)
 - Since new to Isolation forest faced slight issues with syntax and libs.

---

## Checklist

- [x] Code runs successfully
- [x] Notebook (`.ipynb`) included
- [x] Code is well-commented
- [x] README/documentation updated
- [x] At least **2 plots** included
- [ ] PR is linked to the corresponding issue
