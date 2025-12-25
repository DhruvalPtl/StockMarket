# train_lightgbm_walkforward.py
# VS Code friendly — robust fold column handling + callback-based LightGBM

import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score

# ---------------- USER CONFIG ----------------
DATA_FILE = "master_labeled.parquet"
FOLDS_FILE = "walk_folds_with_idx.csv"   # produced by make_walkfolds_and_export_csv.py
OUTPUT_DIR = "lgb_results"
TARGET = "target_dir_1m"   # change to target_up_small_1m or target_up_med_3m if desired
# --------------------------------------------

CORE_FEATURES = [
    "nifty_ret_1","nifty_ret_3",
    "ce_ret_1","pe_ret_1","itm_ce_ret_1","itm_pe_ret_1",
    "ce_pe_ratio","ce_minus_pe",
    "atm_itm_spread_ce","atm_itm_spread_pe",
    "atm_ce_oi_z60","atm_pe_oi_z60","itm_ce_oi_z60","itm_pe_oi_z60",
    "oi_ce_change_1","oi_pe_change_1",
    "nifty_vol_5","nifty_vol_15","atr_5","vol_regime",
    "minute_of_day","sin_md","cos_md",
    "atm_shift","mom_delta","mom_3_sum",
    "atm_itm_ce_ratio","atm_itm_pe_ratio",
    "above_breakout_15","below_breakout_15"
]

def get_feature_columns(df):
    base = CORE_FEATURES.copy()
    lag_cols = [c for c in df.columns if "_lag" in c]
    base.extend(lag_cols)
    return [c for c in base if c in df.columns]

def _col(df_row, names):
    """Return first existing key from names list (works for a pd.Series row)."""
    for n in names:
        if n in df_row.index:
            return n
    return None

def slice_indices_from_fold(df, fold_row):
    """
    Return integer index start/end for train and test.
    Handles multiple column-name variants and also timestamp fallback.
    """
    # candidate names
    train_start_col = _col(fold_row, ["train_idx_start","train_start_idx","train_idx_start"])
    train_end_col   = _col(fold_row, ["train_idx_end","train_end_idx","train_idx_end"])
    test_start_col  = _col(fold_row, ["test_idx_start","test_start_idx","test_idx_start"])
    test_end_col    = _col(fold_row, ["test_idx_end","test_end_idx","test_idx_end"])

    if train_start_col and train_end_col and test_start_col and test_end_col:
        tr_s = int(fold_row[train_start_col])
        tr_e = int(fold_row[train_end_col])
        te_s = int(fold_row[test_start_col])
        te_e = int(fold_row[test_end_col])
        return tr_s, tr_e, te_s, te_e

    # fallback: look for timestamp-based columns (ISO strings)
    ts_train_start_col = _col(fold_row, ["train_start_ts","train_start","train_start_ts"])
    ts_train_end_col   = _col(fold_row, ["train_end_ts","train_end","train_end_ts"])
    ts_test_start_col  = _col(fold_row, ["test_start_ts","test_start","test_start_ts"])
    ts_test_end_col    = _col(fold_row, ["test_end_ts","test_end","test_end_ts"])

    if ts_train_start_col and ts_train_end_col and ts_test_start_col and ts_test_end_col:
        # parse timestamps
        train_start_ts = pd.to_datetime(fold_row[ts_train_start_col])
        train_end_ts   = pd.to_datetime(fold_row[ts_train_end_col])
        test_start_ts  = pd.to_datetime(fold_row[ts_test_start_col])
        test_end_ts    = pd.to_datetime(fold_row[ts_test_end_col])

        df_sorted = df.sort_values("timestamp").reset_index(drop=True)
        tr_s = int(df_sorted['timestamp'].searchsorted(train_start_ts, side='left'))
        tr_e = int(df_sorted['timestamp'].searchsorted(train_end_ts, side='right')) - 1
        te_s = int(df_sorted['timestamp'].searchsorted(test_start_ts, side='left'))
        te_e = int(df_sorted['timestamp'].searchsorted(test_end_ts, side='right')) - 1
        return tr_s, tr_e, te_s, te_e

    raise KeyError("Fold row does not contain usable index or timestamp columns. Check walk_folds_with_idx.csv")

def train_one_fold(df, fold_row, feature_cols):
    fold_id = int(fold_row["fold_id"])

    # get integer index ranges
    tr_s, tr_e, te_s, te_e = slice_indices_from_fold(df, fold_row)

    # slice
    train_df = df.iloc[tr_s:tr_e+1].copy()
    test_df  = df.iloc[te_s:te_e+1].copy()

    # drop rows missing features/target
    train_df = train_df.dropna(subset=feature_cols + [TARGET])
    test_df  = test_df.dropna(subset=feature_cols + [TARGET])

    if len(train_df) < 50 or len(test_df) < 10:
        raise ValueError(f"Fold {fold_id} has too few rows after drop: train={len(train_df)}, test={len(test_df)}")

    X_train = train_df[feature_cols]
    y_train = train_df[TARGET].values
    X_test  = test_df[feature_cols]
    y_test  = test_df[TARGET].values

    # handle imbalance
    pos_weight = (len(y_train) - y_train.sum()) / (y_train.sum() + 1e-9)

    params = {
        "objective": "binary",
        "boosting_type": "gbdt",
        "learning_rate": 0.05,
        "num_leaves": 40,
        "max_depth": -1,
        "metric": "auc",
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
        "bagging_freq": 3,
        "min_data_in_leaf": 50,
        "lambda_l1": 0.1,
        "lambda_l2": 0.1,
        "scale_pos_weight": pos_weight,
        "verbose": -1,
    }

    train_set = lgb.Dataset(X_train, label=y_train)
    valid_set = lgb.Dataset(X_test, label=y_test, reference=train_set)

    callbacks = [
        lgb.early_stopping(stopping_rounds=50),
        # use period=0 only if your lightgbm supports it; safe fallback is period=50
        lgb.log_evaluation(period=0) if hasattr(lgb, "log_evaluation") else lgb.early_stopping(stopping_rounds=0)
    ]

    model = lgb.train(
        params,
        train_set,
        num_boost_round=2000,
        valid_sets=[train_set, valid_set],
        valid_names=["train", "valid"],
        callbacks=callbacks
    )

    best_iter = model.best_iteration if hasattr(model, "best_iteration") and model.best_iteration is not None else None
    if best_iter is None:
        # fallback: use num_boost_round
        best_iter = 2000

    preds_proba = model.predict(X_test, num_iteration=best_iter)
    preds_label = (preds_proba > 0.5).astype(int)

    auc = roc_auc_score(y_test, preds_proba)
    acc = accuracy_score(y_test, preds_label)
    prec = precision_score(y_test, preds_label, zero_division=0)
    rec = recall_score(y_test, preds_label, zero_division=0)

    importance_df = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importance(importance_type='gain'),
        "fold": fold_id
    })

    preds_df = pd.DataFrame({
        "timestamp": test_df["timestamp"].values,
        "y_true": y_test,
        "y_pred": preds_proba,
        "y_label": preds_label,
        "fold": fold_id
    })

    return {
        "fold_id": fold_id,
        "auc": auc,
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "importance": importance_df,
        "preds": preds_df
    }

def main():
    print("Loading dataset...")
    df = pd.read_parquet(DATA_FILE)

    print("Loading folds...")
    folds = pd.read_csv(FOLDS_FILE)

    out = Path(OUTPUT_DIR)
    out.mkdir(exist_ok=True, parents=True)

    feature_cols = get_feature_columns(df)
    print(f"Using {len(feature_cols)} features.")

    all_results = []
    all_preds = []
    all_imp = []

    for _, row in folds.iterrows():
        print(f"\nProcessing fold {int(row['fold_id'])} ...")
        r = train_one_fold(df, row, feature_cols)

        all_results.append({
            "fold_id": r["fold_id"],
            "auc": r["auc"],
            "accuracy": r["accuracy"],
            "precision": r["precision"],
            "recall": r["recall"]
        })
        all_preds.append(r["preds"])
        all_imp.append(r["importance"])

        print(f"Fold {r['fold_id']} -> AUC {r['auc']:.4f} ACC {r['accuracy']:.4f}")

    results_df = pd.DataFrame(all_results)
    results_df.to_csv(out / "fold_metrics.csv", index=False)

    pd.concat(all_preds).to_csv(out / "all_predictions.csv", index=False)
    pd.concat(all_imp).to_csv(out / "feature_importance.csv", index=False)

    print("\nAll done. Saved outputs to:", out)
    print(results_df)

if __name__ == "__main__":
    main()
