# backtest_sweep_extended.py
# Extended sweep: targets 1,3,5,10,15 min; thresholds; SL/TP; two commission profiles.
import pandas as pd, numpy as np
from pathlib import Path

PRED_FILE = "lgb_results/all_predictions.csv"
MASTER_FILE = "master_labeled.parquet"
OUT_DIR = Path("backtest_outputs"); OUT_DIR.mkdir(exist_ok=True)
MERGE_TOL = pd.Timedelta("30s")
POINT_TO_RUPEE = 1.0

# thresholds and targets
THRESHOLDS = np.round(np.arange(0.50, 0.901, 0.02), 2)
TARGETS = [1, 3, 5, 10, 15]   # minutes
SL_LIST = [None, 0.0003, 0.0005]   # e.g., 0.03% ~ ~8 pts at 26000
TP_LIST = [None, 0.0006, 0.001]    # e.g., 0.06%, 0.1%

# commission scenarios (roundtrip rupees)
COMMISSION_SCENARIOS = {
    "current_broker": 40.0,   # your current setting
    "futures_like": 12.0      # simulate cheaper per-trade cost (approx futures)
}
# slippage percent (roundtrip) — keep same
SLIPPAGE_ROUNDTRIP_PCT = 0.00015

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

# ensure future_close_Nm columns exist or compute from future_ret_Nm
for t in TARGETS:
    fut_col = f"future_close_{t}m"
    ret_col = f"future_ret_{t}m"
    if fut_col not in master.columns:
        # try to compute from ret if available
        ret_col_alt = f"future_ret_{t}m"
        if ret_col_alt in master.columns:
            master[fut_col] = (1 + master[ret_col_alt]) * master['nifty_close']
        else:
            # fallback: for 3m we may have future_close_3m or future_ret_3m; if missing skip target later
            pass

# normalize timestamps and merge nearest
preds['ts_norm'] = to_utc_naive(preds.get('timestamp', preds.columns[0]))
master['ts_norm'] = to_utc_naive(master['timestamp'])
preds = preds.dropna(subset=['ts_norm']).sort_values('ts_norm').reset_index(drop=True)
master = master.dropna(subset=['ts_norm']).sort_values('ts_norm').reset_index(drop=True)
merged = pd.merge_asof(preds, master, left_on='ts_norm', right_on='ts_norm', direction='nearest', tolerance=MERGE_TOL)
matched = merged['nifty_close'].notna().sum()
print(f"Preds {len(preds):,} matched {matched:,} rows with tol {MERGE_TOL}")

rows=[]
total_days = ((master['ts_norm'].max() - master['ts_norm'].min()).days + 1)

for comm_name, comm_val in COMMISSION_SCENARIOS.items():
    for tgt in TARGETS:
        fut_col = f"future_close_{tgt}m"
        if fut_col not in merged.columns:
            # skip target if future column impossible
            continue
        for th in THRESHOLDS:
            sel_base = merged[merged['y_pred'] >= th].copy()
            if sel_base.empty:
                rows.append((comm_name, tgt, th, None, None, 0,0,0,0,0,0))
                continue
            for sl in SL_LIST:
                for tp in TP_LIST:
                    sel = sel_base.copy()
                    sel['entry'] = sel['nifty_close'].astype(float)
                    sel['exit_raw'] = sel[fut_col].astype(float)
                    sel['points_raw'] = sel['exit_raw'] - sel['entry']
                    # apply SL/TP if provided
                    if sl is not None or tp is not None:
                        sl_points = None if sl is None else (sel['entry'] * sl)
                        tp_points = None if tp is None else (sel['entry'] * tp)
                        # apply TP first: if raw >= tp -> take tp; else raw
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
                    sel['cost'] = slippage_points * POINT_TO_RUPEE + comm_val
                    sel['pnl'] = sel['points_after'] * POINT_TO_RUPEE - sel['cost']

                    trades = len(sel)
                    wins = (sel['pnl']>0).sum()
                    precision = wins/trades if trades>0 else 0
                    avg_pnl = sel['pnl'].mean()
                    trades_per_day = trades / total_days
                    total_pnl = sel['pnl'].sum()

                    rows.append((comm_name, tgt, th, sl, tp, trades, wins, precision, trades_per_day, avg_pnl, total_pnl))

cols = ['commission_profile','target_min','threshold','sl_frac','tp_frac','trades','wins','precision','trades_per_day','avg_pnl','total_pnl']
res = pd.DataFrame(rows, columns=cols)
res.to_csv(OUT_DIR/"sweep_extended.csv", index=False)
print("Saved sweep_extended.csv to backtest_outputs/")

# print positive avg_pnl rows if any
pos = res[res['avg_pnl']>0].sort_values(['commission_profile','avg_pnl'], ascending=[True,False])
if pos.empty:
    print("\nNo positive average-PnL combos found across tested targets and commission profiles.")
    print("Next recommendations (automated): test targets 20-60 minutes OR simulate using futures with even lower costs or trade only Open/Close windows.")
else:
    print("\nPositive avg_pnl candidates (top 20):")
    print(pos.head(20).to_string(index=False))
