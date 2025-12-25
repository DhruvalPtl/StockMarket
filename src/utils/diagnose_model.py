# diagnose_model.py
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import roc_auc_score
import math
import warnings
warnings.filterwarnings("ignore")

INPUT = "features_final.csv"  # same file used previously
TARGET = "target_up_1m"
EXCLUDE = ["target_1m_direction","target_up_1m","target_down_1m","target_up_2m","target_up_3m",
           "target_down_1m","target_down_2m","target_down_3m","ce_symbol","pe_symbol","atm_strike",
           "atm_ce_ltp","atm_pe_ltp","nifty_ltp","date","timestamp"]

# LightGBM params same as before (quick train)
lgb_params = {
    'objective': 'binary',
    'boosting_type': 'gbdt',
    'n_estimators': 300,
    'learning_rate': 0.05,
    'num_leaves': 64,
    'max_depth': 8,
    'min_data_in_leaf': 20,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'verbose': -1,
    'random_state': 42
}

df = pd.read_csv(INPUT)
# ensure timestamp if present
if 'timestamp' in df.columns:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
if 'date' not in df.columns:
    df['date'] = pd.to_datetime(df['timestamp']).dt.date if 'timestamp' in df.columns else pd.to_datetime(df.index).date

# Quick remove rows with NaN
df = df.dropna().copy()

# Feature list
features = [c for c in df.columns if c not in EXCLUDE and c != TARGET]
print("Number of features:", len(features))
print("Features sample:", features[:8])

# Class balance
pos = df[TARGET].sum()
tot = len(df)
print(f"Rows: {tot}, Positives: {pos}, Pos rate: {pos/tot:.4f}")

# Split by date: last N days as test
unique_days = sorted(df['date'].unique())
if len(unique_days) < 6:
    print("Warning: very few days in data:", len(unique_days))
train_days = unique_days[:-3] if len(unique_days) > 3 else unique_days[:-1]
test_days = unique_days[-3:] if len(unique_days) > 3 else unique_days[-1:]

train = df[df['date'].isin(train_days)]
test = df[df['date'].isin(test_days)]

print("Train days:", len(train_days), "Test days:", len(test_days))
print("Train rows:", len(train), "Test rows:", len(test))

X_train = train[features]
y_train = train[TARGET]
X_test = test[features]
y_test = test[TARGET]

# Train LightGBM
dtrain = lgb.Dataset(X_train, label=y_train)
model = lgb.train(lgb_params, dtrain, valid_sets=[dtrain], verbose_eval=False)

# Predict
proba_train = model.predict(X_train)
proba_test = model.predict(X_test)

# Metrics
try:
    auc_train = roc_auc_score(y_train, proba_train)
    auc_test = roc_auc_score(y_test, proba_test)
except:
    auc_train = auc_test = float('nan')
print("AUC train:", round(auc_train,4), "AUC test:", round(auc_test,4))

# Probability stats
for name, arr in [('train', proba_train), ('test', proba_test)]:
    print(f"\nProba stats ({name}): min {arr.min():.4f}, 25% {np.percentile(arr,25):.4f}, median {np.median(arr):.4f}, 75% {np.percentile(arr,75):.4f}, max {arr.max():.4f}")

# How many above thresholds in test
for thr in [0.9, 0.8, 0.7, 0.6, 0.5]:
    cnt = (proba_test >= thr).sum()
    print(f"Test rows with proba >= {thr}: {cnt}")

# Show top predicted rows
test = test.copy()
test['proba'] = proba_test
print("\nTop 10 predictions (test):")
print(test.sort_values('proba', ascending=False).head(10)[['proba','close','mom_3','ce_ret_1','pe_ret_1','trend_up','liquidity_proxy','target_up_1m']])

# Feature importance
fi = pd.DataFrame({'feature': features, 'imp': model.feature_importance(importance_type='gain')})
fi = fi.sort_values('imp', ascending=False).head(30)
print("\nTop features by gain:")
print(fi.to_string(index=False))

# Save a CSV with proba distribution for further inspection
test[['proba','close','mom_3','ce_ret_1','pe_ret_1','trend_up','liquidity_proxy','target_up_1m']].to_csv("diagnose_test_probas.csv", index=True)
print("\nSaved diagnose_test_probas.csv")
