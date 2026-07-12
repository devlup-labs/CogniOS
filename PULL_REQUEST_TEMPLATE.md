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
- [ ] Shuttle

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
| n_estimators | |
| contamination | |
| max_samples | |
| max_features | |
| random_state | |

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

<img width="346" height="333" alt="Screenshot From 2026-07-13 01-02-23" src="https://github.com/user-attachments/assets/1881f2dd-a619-4670-b601-6e4a9071c814" />
<img width="182" height="160" alt="Screenshot From 2026-07-13 01-02-34" src="https://github.com/user-attachments/assets/2912244b-f897-4319-a244-05c6abf86acc" />
<img width="219" height="161" alt="Screenshot From 2026-07-13 01-02-46" src="https://github.com/user-attachments/assets/2564afe3-2768-48dd-9927-238c6d3a050b" />
<img width="343" height="168" alt="Screenshot From 2026-07-13 01-02-58" src="https://github.com/user-attachments/assets/04a2a0af-6ddf-4fed-ac2f-12e3609b71af" />


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

- [ ] Code runs successfully
- [ ] Notebook (`.ipynb`) included
- [ ] Code is well-commented
- [ ] README/documentation updated
- [ ] At least **2 plots** included
- [ ] PR is linked to the corresponding issue
