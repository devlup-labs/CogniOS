DIFFERENT CASES USED 
1-
iso_forest = IsolationForest(
contamination =0.4,
max_samples = 256, 
random_state=42,
max_features = 1.0 , 
n_estimators = 120)

Classification Report:
              precision    recall  f1-score   support

          -1       0.45      0.84      0.59     12414
           1       0.94      0.72      0.82     45586

2-
iso_forest = IsolationForest(
contamination =0.4,
max_samples = 400, 
random_state=42,
max_features = 1.0 , 
n_estimators = 200)

Classification Report:
              precision    recall  f1-score   support

          -1       0.43      0.81      0.56     12414
           1       0.93      0.71      0.81     45586


3-(using standard values)
iso_forest = IsolationForest(
contamination =0.4,
max_samples = 256, 
random_state=42,
max_features = 1.0 , 
n_estimators = 100)

Classification Report:
              precision    recall  f1-score   support

          -1       0.46      0.86      0.60     12414
           1       0.95      0.73      0.82     45586


 4-(assuming most amount of contamination)
 (most recall obtained)
 iso_forest = IsolationForest(
contamination =0.5,
max_samples = 256, 
random_state=42,
max_features = 1.0 , 
n_estimators = 100)          

Classification Report:
              precision    recall  f1-score   support

          -1       0.40      0.94      0.56     12414
           1       0.97      0.62      0.76     45586

5 - (actual amount of contamination)
iso_forest = IsolationForest(
contamination =0.21,
max_samples = 256, 
random_state=42,
max_features = 1.0 , 
n_estimators = 100)

Classification Report:
              precision    recall  f1-score   support

          -1       0.54      0.53      0.54     12414
           1       0.87      0.88      0.88     45586


6 - (inc no of trres anfd reducing samples )

iso_forest = IsolationForest(
contamination =0.5,
max_samples = 100, 
random_state=42,
max_features = 1.0 , 
n_estimators = 400)

Classification Report:
              precision    recall  f1-score   support

          -1       0.37      0.86      0.52     12414
           1       0.94      0.60      0.73     45586

7- 

iso_forest = IsolationForest(
contamination =0.5,
max_samples = 50, 
random_state=42,
max_features = 1.0 , 
n_estimators = 290) 

 precision    recall  f1-score   support

          -1       0.38      0.89      0.53     12414
           1       0.95      0.61      0.74     45586


8 --
contamination =0.5,
max_samples = 50, 
random_state=42,
max_features = 1.0 , 
n_estimators = 400)

Classification Report:
              precision    recall  f1-score   support

          -1       0.38      0.88      0.53     12414
           1       0.95      0.60      0.74     45586
          
