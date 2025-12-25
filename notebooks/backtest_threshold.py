# backtest_sweep_and_sl.py
# Sweeps thresholds, targets (1m,3m), and simple SL/TP. VS Code friendly.
import pandas as pd, numpy as np
from pathlib import Path

PRED_FILE = "lgb_results/all_predictions.csv"
MASTER_FILE = "master_labeled.parquet"
OUT_DIR = Path("backtest_outputs"); OUT_DIR.mkdir(exist_ok=True)
MERGE_TOL = pd.Timedelta("30s")
SLIPPAGE_ROUNDTRIP_PCT = 0.00015
COMMISSION_ROUNDTRIP = 40.0
POINT_TO_RUPEE = 1.0

THRESHOLDS = np.round(np.arange(0.50, 0.901, 0.02), 2)
TARGETS = [1, 3]   # minutes (we expect 3-min to give larger moves)
# SL/TP expressed in index points (absolute) or %: we'll use percent of index as defaults
SL_LIST = [None, 0.0003, 0.0005]   # 0.03% (~8 pts at 26000), 0.05%
TP_LIST = [None, 0.0006, 0.001]    # 0.06%, 0.1%

def to_utc_naive(series, assumed_tz="Asia/Kolkata"):
    s = pd.to_datetime(series, errors='coerce')
    if s.isna().all(): return s
    sample_idx = s.first_valid_index()
    if sample_idx is None: return s
    sample = s.loc[sample_idx]
    try:
        if sample.tzinfo is None:
            s = s.dt.tz_localize(assumed_tz, ambiguous='NaT', nonexistent='shift_forward')
        s = s.dt.tz_convert("UTC").dt.tz_localize(None)
    except Exception:
        try: s = pd.to_datetime(series, errors='coerce').dt.tz_localize(None)
        except: s = pd.to_datetime(series, errors='coerce')
    return s

print("Loading preds & master...")
preds = pd.read_csv(PRED_FILE)
master = pd.read_parquet(MASTER_FILE)
# create both 1m and 3m future columns if not present
if 'future_close_1m' not in master.columns:
    raise SystemExit("master_labeled.parquet missing future_close_1m")
if 'future_close_3m' not in master.columns:
    # compute approx: shift by 3 rows per minute per continuous minutes might already exist; if not try to use future_close_3m column
    if 'future_ret_3m' in master.columns and 'nifty_close' in master.columns:
        master['future_close_3m'] = (1 + master['future_ret_3m']).values * master['nifty_close'].values
    else:
        raise SystemExit("master missing future_close_3m and can't compute it.")

# normalize timestamps
preds['ts_norm'] = to_utc_naive(preds.get('timestamp', preds.columns[0]))
master['ts_norm'] = to_utc_naive(master['timestamp'])
preds = preds.dropna(subset=['ts_norm']).sort_values('ts_norm').reset_index(drop=True)
master = master.dropna(subset=['ts_norm']).sort_values('ts_norm').reset_index(drop=True)

# merge once (nearest)
merged = pd.merge_asof(preds, master, left_on='ts_norm', right_on='ts_norm', direction='nearest', tolerance=MERGE_TOL)
matched = merged['future_ret_1m'].notna().sum()
print(f"Preds {len(preds):,} matched {matched:,} with tol {MERGE_TOL}")

rows = []
total_days = ((master['ts_norm'].max() - master['ts_norm'].min()).days + 1)

for tgt in TARGETS:
    fut_col = f'future_close_{tgt}m'
    if fut_col not in merged.columns:
        # fallback mapping
        if tgt == 1: fut_col = 'future_close_1m'
        elif tgt == 3: fut_col = 'future_close_3m'
    for th in THRESHOLDS:
        sel_base = merged[merged['y_pred'] >= th].copy()
        if len(sel_base)==0:
            rows.append((tgt, th, None, None, 0,0,0,0,0,0))
            continue
        for sl in SL_LIST:
            for tp in TP_LIST:
                sel = sel_base.copy()
                # compute raw points depending on target
                sel['entry'] = sel['nifty_close'].astype(float)
                sel['exit_raw'] = sel.get(fut_col)
                sel['points_raw'] = sel['exit_raw'] - sel['entry']
                # now apply SL/TP: if both None => use raw exit; if provided, cap results
                if sl is not None or tp is not None:
                    # SL/TP in fraction of entry price; convert to points
                    sl_points = None if sl is None else (sel['entry'] * sl)
                    tp_points = None if tp is None else (sel['entry'] * tp)
                    # simulate: if raw points >= tp_points -> take tp_points; if raw points <= -sl_points -> take -sl_points; else raw
                    if tp is not None:
                        sel['points_after'] = np.where(sel['points_raw']>=tp_points, tp_points, sel['points_raw'])
                    else:
                        sel['points_after'] = sel['points_raw']
                    if sl is not None:
                        sel['points_after'] = np.where(sel['points_after']<=-sl_points, -sl_points, sel['points_after'])
                else:
                    sel['points_after'] = sel['points_raw']

                avg_price = sel['entry'].mean()
                slippage_points = avg_price * SLIPPAGE_ROUNDTRIP_PCT
                sel['cost'] = slippage_points * POINT_TO_RUPEE + COMMISSION_ROUNDTRIP
                sel['pnl'] = sel['points_after'] * POINT_TO_RUPEE - sel['cost']

                trades = len(sel)
                wins = (sel['pnl']>0).sum()
                precision = wins/trades if trades>0 else 0
                avg_pnl = sel['pnl'].mean()
                trades_per_day = trades / total_days
                total_pnl = sel['pnl'].sum()

                rows.append((tgt, th, sl, tp, trades, wins, precision, trades_per_day, avg_pnl, total_pnl))

# assemble
cols = ['target_min','threshold','sl_frac','tp_frac','trades','wins','precision','trades_per_day','avg_pnl','total_pnl']
res = pd.DataFrame(rows, columns=cols)
res = res.sort_values(['target_min','threshold','avg_pnl'], ascending=[True,False,False])
res.to_csv(OUT_DIR/"sweep_results.csv", index=False)
print("Saved sweep_results.csv to backtest_outputs/")

# print top candidates
print("\nTop positive avg_pnl candidates (avg_pnl > 0):")
print(res[res['avg_pnl']>0].sort_values('avg_pnl', ascending=False).head(20).to_string(index=False))

print("\nIf none printed above: no setting beat costs. Try increasing target to 5-10 minutes, use futures (lower commission), or raise threshold.")
