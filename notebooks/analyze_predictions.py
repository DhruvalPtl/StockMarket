# analyze_predictions.py
import pandas as pd
import numpy as np
from pathlib import Path

# ---------- CONFIG ----------
PRED_FILE = "all_predictions.csv"            # from lgb_results
MASTER_FILE = "master_labeled.parquet"       # final labeled dataset
OUT_DIR = Path("analysis_outputs")
OUT_DIR.mkdir(exist_ok=True)
# bins for calibration
BINS = [0.0, 0.5, 0.55, 0.6, 0.62, 0.64, 0.66, 0.68, 0.70, 0.75, 1.0]
# transaction costs (tweak as needed)
SLIPPAGE_PCT = 0.00015   # 0.015% roundtrip slippage (you used earlier)
COMMISSION_RUPEES = 40   # roundtrip fixed commission (example)
# ---------- /CONFIG ----------

def main():
    print("Loading predictions:", PRED_FILE)
    preds = pd.read_csv(PRED_FILE, parse_dates=['timestamp'])
    print("Rows in predictions:", len(preds))

    print("Loading master labeled (sampling only needed cols)...")
    # load only needed columns to keep memory small
    need_cols = ['timestamp','future_ret_1m','future_ret_3m','nifty_close']
    master = pd.read_parquet(MASTER_FILE, columns=need_cols)
    print("Rows in master:", len(master))

    # normalize timestamps to string and merge on that (robust to tz differences)
    preds['ts_str'] = preds['timestamp'].astype(str)
    master['ts_str'] = master['timestamp'].astype(str)
    merged = preds.merge(master[['ts_str','future_ret_1m','future_ret_3m','nifty_close']],
                         on='ts_str', how='left')
    n_missing = merged['future_ret_1m'].isna().sum()
    print(f"Merged rows: {len(merged)}  missing future_ret_1m: {n_missing}")

    # basic check
    if n_missing > 0:
        print("Warning: some predictions did not find a matching master timestamp. Check timestamp formats/timezones.")
    # calibration bins
    merged['prob_bin'] = pd.cut(merged['y_pred'], bins=BINS)
    bin_stats = merged.groupby('prob_bin').agg(
        count=('y_true','size'),
        mean_pred=('y_pred','mean'),
        empirical_prob=('y_true','mean'),
        avg_ret_1m=('future_ret_1m','mean'),
        avg_ret_3m=('future_ret_3m','mean')
    ).reset_index()
    bin_stats = bin_stats.sort_values('mean_pred', ascending=False)
    bin_stats.to_csv(OUT_DIR / "bin_stats.csv", index=False)
    print("\n=== Calibration by bucket ===")
    print(bin_stats[['prob_bin','count','mean_pred','empirical_prob','avg_ret_1m','avg_ret_3m']])

    # threshold sweep
    thresholds = np.arange(0.50, 0.901, 0.01)
    rows=[]
    total_days = (merged['timestamp'].max() - merged['timestamp'].min()).days + 1
    avg_close = merged['nifty_close'].mean()
    for t in thresholds:
        sel = merged[merged['y_pred'] >= t]
        trades = len(sel)
        if trades == 0:
            rows.append((t,0,0,0,0,0,0))
            continue
        wins = int(sel['y_true'].sum())
        precision = wins / trades
        avg_ret_1m = sel['future_ret_1m'].mean()
        avg_ret_3m = sel['future_ret_3m'].mean()
        trades_per_day = trades / total_days
        # expected points per trade (index points ~= rupees)
        exp_points = avg_ret_1m * avg_close
        # cost per trade in rupees: slippage in points + commission (we treat index points == rupees)
        slippage_points = avg_close * SLIPPAGE_PCT
        cost_per_trade_rupees = slippage_points + COMMISSION_RUPEES
        exp_rupees_per_trade = exp_points - cost_per_trade_rupees
        rows.append((t, trades, wins, precision, avg_ret_1m, trades_per_day, exp_rupees_per_trade))

    th_df = pd.DataFrame(rows, columns=[
        'threshold','trades','wins','precision','avg_ret_1m','trades_per_day','exp_rupees_per_trade'
    ])
    th_df.to_csv(OUT_DIR / "thresholds_analysis.csv", index=False)

    # print human-friendly recommendations:
    print("\n=== Threshold sweep summary (sample rows) ===")
    display_df = th_df[(th_df['trades']>0)].copy()
    # choose three candidate thresholds:
    # a) high precision (>=0.62)
    cand_high = display_df[display_df['precision']>=0.62].sort_values('precision', ascending=False).head(3)
    # b) balanced
    cand_bal = display_df[(display_df['precision']>=0.56) & (display_df['precision']<0.62)].sort_values('precision', ascending=False).head(3)
    # c) moderate
    cand_mod = display_df[(display_df['precision']>=0.52) & (display_df['precision']<0.56)].sort_values('precision', ascending=False).head(3)

    print("\nHigh-precision candidate thresholds (precision>=0.62):")
    if len(cand_high):
        print(cand_high[['threshold','trades','precision','trades_per_day','exp_rupees_per_trade']])
    else:
        print(" none found (try lowering threshold)")

    print("\nBalanced candidate thresholds (precision 0.56-0.62):")
    print(cand_bal[['threshold','trades','precision','trades_per_day','exp_rupees_per_trade']])

    print("\nModerate candidate thresholds (precision 0.52-0.56):")
    print(cand_mod[['threshold','trades','precision','trades_per_day','exp_rupees_per_trade']])

    # also print best expected rupee per trade
    best_by_exp = display_df.sort_values('exp_rupees_per_trade', ascending=False).head(5)
    print("\nTop thresholds by expected rupees per trade (after costs):")
    print(best_by_exp[['threshold','trades','precision','trades_per_day','exp_rupees_per_trade']])

    print("\nOutputs saved in:", OUT_DIR)
    print("Files: bin_stats.csv, thresholds_analysis.csv")

if __name__ == "__main__":
    main()
