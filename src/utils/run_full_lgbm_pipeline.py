# run_full_lgbm_pipeline.py
# End-to-end LightGBM pipeline for target = +0.05% in 1 minute.
# Usage: python run_full_lgbm_pipeline.py
# Requirements: pandas, numpy, lightgbm, scikit-learn, joblib, (optional shap, matplotlib)

import pandas as pd
import numpy as np
import lightgbm as lgb
import joblib
from sklearn.metrics import roc_auc_score
import math, os, warnings, datetime
warnings.filterwarnings("ignore")

# ---------------- CONFIG ----------------
INPUT = "features_final.csv"   # your features file
OUTPUT_PREFIX = "wf_0p05"
TARGET_NAME = "target_up_1m_0p05"
THRESH = 0.0005  # 0.05%
HORIZON = 1

# Walk-forward params
TRAIN_DAYS = 8
TEST_DAYS = 3

# Trading sim params
INITIAL_CAPITAL = 100000.0
RISK_PER_TRADE = 0.005
SL_PCT = 0.002
TP_PCT = 0.005
COMMISSION_PER_TRADE = 20
SLIPPAGE_PCT = 0.0005
MAX_LOOK_MIN = 15

# Model params
lgb_params = {
    'objective': 'binary','boosting_type': 'gbdt','n_estimators': 600,'learning_rate': 0.05,
    'num_leaves': 64,'max_depth': 8,'min_data_in_leaf': 20,'feature_fraction': 0.8,
    'bagging_fraction': 0.8,'bagging_freq': 5,'verbose': -1,'random_state': 42
}

# Threshold scan (probabilities to evaluate)
THRESHOLDS_TO_TEST = np.linspace(0.45, 0.85, 9)  # scan 0.55..0.85

# ---------------- HELPERS ----------------
def ensure_numeric_and_targets(df):
    # timestamp
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Create days_to_expiry numeric if expiry present
    if 'expiry' in df.columns:
        try:
            df['expiry_dt'] = pd.to_datetime(df['expiry'], errors='coerce')
            if 'timestamp' in df.columns:
                df['days_to_expiry'] = (df['expiry_dt'] - df['timestamp']).dt.total_seconds()/(24*3600)
            else:
                df['days_to_expiry'] = (df['expiry_dt'] - pd.Timestamp("1970-01-01")).dt.total_seconds()/(24*3600)
            df['days_to_expiry'] = df['days_to_expiry'].fillna(0.0).astype(float)
            print("Converted expiry -> days_to_expiry")
        except Exception as e:
            print("Could not convert expiry:", e)
        df = df.drop(columns=['expiry','expiry_dt'], errors='ignore')
    # Drop symbol columns (text)
    for col in ['ce_symbol','pe_symbol','atm_strike','atm_ce_ltp','atm_pe_ltp','nifty_ltp']:
        if col in df.columns:
            # atm_ce_ltp/atm_pe_ltp are numeric in your set — drop only if object
            if df[col].dtype == 'O':
                df = df.drop(columns=[col], errors='ignore')
    # Convert any remaining object columns where possible, otherwise drop
    obj_cols = df.select_dtypes(include=['object']).columns.tolist()
    dropped = []
    for col in obj_cols:
        if col in ['date']:  # skip if it's a date str we'll create
            continue
        try:
            df[col] = pd.to_numeric(df[col], errors='raise')
            print(f"Converted {col} -> numeric")
        except:
            # try parse datetime
            try:
                dt = pd.to_datetime(df[col], errors='coerce')
                if dt.notna().sum() > 0:
                    if 'timestamp' in df.columns:
                        df[col + "_days"] = (dt - df['timestamp']).dt.total_seconds()/(24*3600)
                    else:
                        df[col + "_days"] = (dt - pd.Timestamp("1970-01-01")).dt.total_seconds()/(24*3600)
                    df = df.drop(columns=[col], errors='ignore')
                    print(f"Parsed datetime {col} -> {col + '_days'}")
                    continue
            except:
                pass
            dropped.append(col)
            df = df.drop(columns=[col], errors='ignore')
    if dropped:
        print("Dropped object cols:", dropped)
    # Fill numeric NaNs
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    df[num_cols] = df[num_cols].fillna(method='ffill').fillna(0.0)
    return df

def create_target_if_missing(df):
    # if target already exists, keep. Otherwise create
    if TARGET_NAME in df.columns:
        print("Target exists:", TARGET_NAME)
        return df
    price = df['close'].astype(float)
    future_price = price.shift(-HORIZON)
    ret = (future_price - price) / price
    df[TARGET_NAME] = (ret >= THRESH).astype(int)
    df[f"target_down_{HORIZON}m_0p05"] = (ret <= -THRESH).astype(int)
    df[f"target_1m_direction_0p05"] = 0
    df.loc[df[TARGET_NAME] == 1, f"target_1m_direction_0p05"] = 1
    df.loc[df[f"target_down_{HORIZON}m_0p05"] == 1, f"target_1m_direction_0p05"] = -1
    print("Created target:", TARGET_NAME, "positives:", df[TARGET_NAME].sum(), "rows:", len(df))
    return df

def simulate_trades_on_df(test_df, prob_col, threshold, equity_start):
    equity = equity_start
    trades = []
    idxs = list(test_df.index)
    for i, idx in enumerate(idxs):
        row = test_df.loc[idx]
        p = row[prob_col]
        if p < threshold:
            continue
        # optional trend filter could be applied here
        if row.get('liquidity_proxy', 0) < 0:
            continue
        price = float(row['close'])
        risk_cash = equity * RISK_PER_TRADE
        stop_loss_price = price * (1 - SL_PCT)
        target_price = price * (1 + TP_PCT)
        # qty
        qty = math.floor(risk_cash / (price - stop_loss_price + 1e-12))
        if qty <= 0:
            continue
        entry_price = price * (1 + SLIPPAGE_PCT)
        # forward search
        outcome = None
        exit_price = None
        exit_time = None
        for j in range(1, MAX_LOOK_MIN+1):
            if i + j >= len(idxs):
                break
            fidx = idxs[i + j]
            fr = test_df.loc[fidx]
            high = fr.get('high', fr['close'])
            low = fr.get('low', fr['close'])
            if high >= target_price:
                exit_price = target_price * (1 - SLIPPAGE_PCT)
                outcome = 'TP'
                exit_time = fidx
                break
            if low <= stop_loss_price:
                exit_price = stop_loss_price * (1 + SLIPPAGE_PCT)
                outcome = 'SL'
                exit_time = fidx
                break
        if outcome is None:
            last_idx = idxs[min(i + MAX_LOOK_MIN, len(idxs)-1)]
            exit_price = float(test_df.loc[last_idx]['close']) * (1 - SLIPPAGE_PCT)
            exit_time = last_idx
            outcome = 'HOLD_EXIT'
        pnl = (exit_price - entry_price) * qty - COMMISSION_PER_TRADE
        equity += pnl
        trades.append({
            'entry_time': idx, 'exit_time': exit_time, 'entry_price': entry_price,
            'exit_price': exit_price, 'qty': qty, 'pnl': pnl, 'outcome': outcome,
            'proba': p, 'date': pd.to_datetime(idx).date()
        })
    return trades, equity

# ---------------- LOAD ----------------
print("Loading:", INPUT)
df = pd.read_csv(INPUT)
if 'timestamp' in df.columns:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
if 'date' not in df.columns and 'timestamp' in df.columns:
    df['date'] = df['timestamp'].dt.date

# Ensure clean numeric and create target
df = ensure_numeric_and_targets(df)
df = create_target_if_missing(df)

# drop final NaNs (tail)
df = df.dropna().copy()
print("Rows after cleaning:", len(df))

# Prepare features (exclude label columns and obvious non-feature names)
exclude = [TARGET_NAME, f"target_down_{HORIZON}m_0p05", f"target_1m_direction_0p05",
           'timestamp','date','ce_symbol','pe_symbol','atm_strike','atm_ce_ltp','atm_pe_ltp','nifty_ltp']
features = [c for c in df.columns if c not in exclude and c not in ['target_up_1m','target_down_1m']]

print("Feature count:", len(features))
print("Sample features:", features[:10])

# Day list for walk-forward
unique_days = sorted(df['date'].unique())
print("Total days:", len(unique_days))
if len(unique_days) < (TRAIN_DAYS + TEST_DAYS):
    print("Warning: not enough days for configured TRAIN/TEST windows. Consider reducing TRAIN_DAYS/TEST_DAYS.")

# Walk-forward
all_trades = []
wf_results = []
equity = INITIAL_CAPITAL
equity_curve = [equity]

for i in range(0, len(unique_days) - TRAIN_DAYS - TEST_DAYS + 1):
    train_days = unique_days[i:i+TRAIN_DAYS]
    test_days = unique_days[i+TRAIN_DAYS:i+TRAIN_DAYS+TEST_DAYS]
    train_df = df[df['date'].isin(train_days)]
    test_df = df[df['date'].isin(test_days)]
    if len(train_df) < 100 or len(test_df) < 50:
        continue

    X_train = train_df[features]
    y_train = train_df[TARGET_NAME]
    X_test = test_df[features]
    y_test = test_df[TARGET_NAME]

    # set scale_pos_weight for imbalance
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    scale = max(1, int(neg / (pos + 1e-9)))
    lgb_params['scale_pos_weight'] = scale
    print(f"Fold train days {train_days[0]} -> {train_days[-1]} | test {test_days[0]} -> {test_days[-1]} | pos {pos}/{len(y_train)} | scale {scale}")

    # Train
    dtrain = lgb.Dataset(X_train, label=y_train)
    model = lgb.train(lgb_params, dtrain)

    # Predict probabilities
    proba = model.predict(X_test)
    test_df = test_df.copy()
    test_df['proba'] = proba
    print("Proba stats (test): min", proba.min(), "25%", np.percentile(proba,25),
      "med", np.median(proba), "75%", np.percentile(proba,75), "max", proba.max())

    # Save model for last fold
    joblib.dump(model, f"{OUTPUT_PREFIX}_lgbm_model_fold_{i}.pkl")

    # threshold scan to pick best threshold on this fold
    best_thr = None
    best_expectancy = -1e9
    best_stats = None
    for thr in THRESHOLDS_TO_TEST:
        trades, eq_end = simulate_trades_on_df(test_df, 'proba', thr, equity)
        if len(trades) == 0:
            continue
        tdf = pd.DataFrame(trades)
        wins = tdf[tdf['pnl'] > 0]
        losses = tdf[tdf['pnl'] <= 0]
        win_rate = len(wins) / len(tdf)
        avg_win = wins['pnl'].mean() if len(wins) else 0
        avg_loss = losses['pnl'].mean() if len(losses) else 0
        expectancy = (win_rate * avg_win + (1 - win_rate) * avg_loss)
        if expectancy > best_expectancy:
            best_expectancy = expectancy
            best_thr = thr
            best_stats = {'thr': thr, 'trades': len(tdf), 'pnl': tdf['pnl'].sum(), 'win_rate': win_rate, 'expectancy': expectancy}
    if best_thr is None:
        print("No trades in this fold at tested thresholds.")
        wf_results.append({'train_start': train_days[0], 'train_end': train_days[-1],
                           'test_start': test_days[0], 'test_end': test_days[-1],
                           'auc': float('nan'), 'best_thr': None, 'equity': equity})
        continue

    # Use best_thr to run and append trades
    trades_fold, equity = simulate_trades_on_df(test_df, 'proba', best_thr, equity)
    equity_curve.append(equity)
    all_trades += trades_fold

    # compute auc
    try:
        auc = roc_auc_score(y_test, proba)
    except:
        auc = float('nan')

    wf_results.append({'train_start': train_days[0], 'train_end': train_days[-1],
                       'test_start': test_days[0], 'test_end': test_days[-1],
                       'auc': auc, 'best_thr': best_thr, 'equity': equity})

# Postprocess
trades_df = pd.DataFrame(all_trades)
if trades_df.empty:
    print("No trades executed across folds. Try lowering thresholds or changing config.")
else:
    trades_df.to_csv("backtest_trades.csv", index=False)
    daily = trades_df.groupby('date')['pnl'].sum().reset_index().rename(columns={'pnl':'daily_pnl'})
    daily.to_csv("backtest_daily_pnl.csv", index=False)
    pd.DataFrame(wf_results).to_csv("wf_results.csv", index=False)

    total_pnl = trades_df['pnl'].sum()
    wins = trades_df[trades_df['pnl'] > 0]
    losses = trades_df[trades_df['pnl'] <= 0]
    win_rate = len(wins) / len(trades_df)
    avg_win = wins['pnl'].mean() if len(wins) else 0
    avg_loss = losses['pnl'].mean() if len(losses) else 0
    profit_factor = (wins['pnl'].sum() / (-losses['pnl'].sum())) if (-losses['pnl'].sum()) != 0 else np.nan
    expectancy = (win_rate * avg_win + (1 - win_rate) * avg_loss)
    max_dd = (pd.Series([INITIAL_CAPITAL] + equity_curve).cummax() - pd.Series([INITIAL_CAPITAL] + equity_curve)).max()

    print("TOTAL TRADES:", len(trades_df))
    print("TOTAL PNL:", total_pnl)
    print("WIN RATE:", round(win_rate,3))
    print("PROFIT FACTOR:", round(profit_factor,3))
    print("EXPECTANCY (per trade):", round(expectancy,2))
    print("END EQUITY:", equity, "MAX DRAWDOWN (approx):", max_dd)

    # feature importance from last model
    fi = pd.DataFrame({'feature': features, 'gain': model.feature_importance(importance_type='gain')})
    fi = fi.sort_values('gain', ascending=False)
    fi.to_csv("feature_importance.csv", index=False)
    print("Saved feature_importance.csv")

    # optionally compute shap (if available)
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        X_for_shap = X_test.sample(min(200, len(X_test)), random_state=1)
        shap_values = explainer.shap_values(X_for_shap)
        np.save("shap_values.npy", shap_values)
        # quick interactive plot saved to html
        shap.initjs()
        shap.force_plot(explainer.expected_value, shap_values[1], X_for_shap, matplotlib=False, show=False, out_names=None)
        print("Computed SHAP values (saved shap_values.npy).")
    except Exception as e:
        print("SHAP not available or failed:", e)

print("WALK-FORWARD FINISHED. Results saved: backtest_trades.csv, backtest_daily_pnl.csv, wf_results.csv, feature_importance.csv")
