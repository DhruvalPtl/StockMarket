
"""
make_walkfolds_and_export_csv.py

Reads master_labeled.parquet (or .csv), writes a CSV copy, and produces walk-forward folds.

Usage:
    python make_walkfolds_and_export_csv.py --in master_labeled.parquet \
         --out_csv master_labeled.csv \
         --folds_csv walk_folds.csv \
         --train_months 12 --test_months 1 --step_months 1

Defaults:
 - train_months=12 (12 months of history)
 - test_months=1   (1 month test window)
 - step_months=1   (move forward by 1 month each fold)
"""
import argparse
from pathlib import Path
import pandas as pd

def month_floor(ts):
    return pd.Timestamp(year=ts.year, month=ts.month, day=1).tz_localize(ts.tz) if ts.tz else pd.Timestamp(year=ts.year, month=ts.month, day=1)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="infile", required=True, help="Input labeled parquet or csv (master_labeled.parquet)")
    p.add_argument("--out_csv", default="master_labeled.csv", help="Output CSV filename")
    p.add_argument("--folds_csv", default="walk_folds.csv", help="Output folds CSV filename")
    p.add_argument("--train_months", type=int, default=12, help="Training window in months")
    p.add_argument("--test_months", type=int, default=1, help="Test window in months")
    p.add_argument("--step_months", type=int, default=1, help="Step between folds in months")
    args = p.parse_args()

    inp = Path(args.infile)
    if not inp.exists():
        raise SystemExit(f"Input file not found: {inp}")

    # 1) load
    if inp.suffix.lower() in (".parquet", ".pq"):
        df = pd.read_parquet(inp)
    else:
        df = pd.read_csv(inp)

    # 2) ensure timestamp
    if 'timestamp' not in df.columns:
        raise SystemExit("timestamp column missing")
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    # keep timezone info if present; otherwise treat as naive UTC-like local times.

    # 3) Save CSV copy (no index)
    out_csv = Path(args.out_csv)
    print(f"Writing CSV copy to: {out_csv}  (this may be large)")
    df.to_csv(out_csv, index=False)
    print("CSV written.")

    # 4) Build walk-forward folds by calendar months
    # Determine min and max timestamps
    min_ts = df['timestamp'].min()
    max_ts = df['timestamp'].max()
    print("Data time range:", min_ts, "->", max_ts)

    # floor to first day of month for anchor points
    # If tz-aware, preserve tz
    tz = min_ts.tz if hasattr(min_ts, 'tz') else None
    start_month = pd.Timestamp(min_ts.year, min_ts.month, 1, tz=tz)
    end_month = pd.Timestamp(max_ts.year, max_ts.month, 1, tz=tz)

    train_m = args.train_months
    test_m  = args.test_months
    step_m  = args.step_months

    folds = []
    cur_test_start = start_month + pd.DateOffset(months=train_m)
    last_possible_test_start = end_month - pd.DateOffset(months=test_m) + pd.DateOffset(days=0)

    fold_id = 0
    while cur_test_start <= last_possible_test_start:
        train_start = cur_test_start - pd.DateOffset(months=train_m)
        train_end   = cur_test_start - pd.DateOffset(minutes=1)  # up to minute before test start
        test_start  = cur_test_start
        test_end    = (cur_test_start + pd.DateOffset(months=test_m)) - pd.DateOffset(minutes=1)

        # convert to naive ISO strings for CSV readability
        folds.append({
            "fold_id": fold_id,
            "train_start": train_start.isoformat(),
            "train_end": train_end.isoformat(),
            "test_start": test_start.isoformat(),
            "test_end": test_end.isoformat()
        })

        fold_id += 1
        cur_test_start = cur_test_start + pd.DateOffset(months=step_m)

    folds_df = pd.DataFrame(folds)
    if folds_df.empty:
        print("No folds created: adjust train_months/test_months/step_months or check date range.")
    else:
        folds_csv = Path(args.folds_csv)
        folds_df.to_csv(folds_csv, index=False)
        print(f"Saved walk-forward folds to: {folds_csv}")
        print("Sample folds:")
        print(folds_df.head())

    # 5) Optionally, compute numeric row-index ranges for each fold (train_idx/test_idx)
    # This maps the timestamps back to dataframe integer positions (useful for fast slicing).
    idx_rows = []
    df_indexed = df.sort_values('timestamp').reset_index(drop=True)
    for r in folds:
        ts_train_start = pd.to_datetime(r['train_start'])
        ts_train_end   = pd.to_datetime(r['train_end'])
        ts_test_start  = pd.to_datetime(r['test_start'])
        ts_test_end    = pd.to_datetime(r['test_end'])

        train_idx_start = df_indexed['timestamp'].searchsorted(ts_train_start, side='left')
        train_idx_end   = df_indexed['timestamp'].searchsorted(ts_train_end, side='right') - 1
        test_idx_start  = df_indexed['timestamp'].searchsorted(ts_test_start, side='left')
        test_idx_end    = df_indexed['timestamp'].searchsorted(ts_test_end, side='right') - 1

        idx_rows.append({
            "fold_id": r['fold_id'],
            "train_idx_start": int(train_idx_start),
            "train_idx_end": int(train_idx_end),
            "test_idx_start": int(test_idx_start),
            "test_idx_end": int(test_idx_end),
            "train_start_ts": r['train_start'],
            "train_end_ts": r['train_end'],
            "test_start_ts": r['test_start'],
            "test_end_ts": r['test_end'],
        })

    idx_df = pd.DataFrame(idx_rows)
    idx_out = Path(args.folds_csv).with_name(Path(args.folds_csv).stem + "_with_idx.csv")
    idx_df.to_csv(idx_out, index=False)
    print(f"Saved folds with index bounds to: {idx_out}")
    print("Done.")

if __name__ == "__main__":
    main()
