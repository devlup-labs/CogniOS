import joblib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import shap

model = joblib.load('iso_forest_model.joblib')
scaler = joblib.load('scaler.joblib')

