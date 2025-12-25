#!/usr/bin/env python3
# make_targets.py
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

MARKET_TZ = "Asia/Kolkata"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True, help="Input features parquet (master_features.parquet)")
    ap.add_argument("--out", dest="outfile", required=True, help="Output labeled parquet (master_labeled.parquet)")
    # escape percent signs in help text by using %%
    ap.add_argument("--small_pct", type=float, default=0.0002,
                    help="Small move threshold (decimal). Default 0.0002 = 0.02%%")
    ap.add_argument("--med_pct", type=float, default=0.0005,
                    help="Medium move threshold over 3min (decimal). Default 0.0005 = 0.05%%")
    args = ap.parse_args()

    inp = Path(args.infile)
    outp = Path(args.outfile)

    # 1) load
    if not inp.exists():
        raise SystemExit(f"Input file not found: {inp}")
    df = pd.read_parquet(inp) if inp.suffix.lower() in (".parquet", ".pq") else pd.read_csv(inp)

    # 2) ensure timestamp
    if 'timestamp' not in df.columns:
        raise SystemExit("timestamp column missing")
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize(MARKET_TZ)
    else:
        df['timestamp'] = df['timestamp'].dt.tz_convert(MARKET_TZ)

    df = df.sort_values('timestamp').reset_index(drop=True)

    # 3) compute future returns (no leakage):
    # 1-minute forward return
    df['future_close_1m'] = df['nifty_close'].shift(-1)
    df['future_ret_1m'] = (df['future_close_1m'] - df['nifty_close']) / (df['nifty_close'] + 1e-9)

    # 3-minute forward return
    df['future_close_3m'] = df['nifty_close'].shift(-3)
    df['future_ret_3m'] = (df['future_close_3m'] - df['nifty_close']) / (df['nifty_close'] + 1e-9)

    # 4) create targets
    small_thr = args.small_pct
    med_thr = args.med_pct

    df['target_dir_1m'] = (df['future_ret_1m'] > 0).astype(int)               # direction: up vs not-up
    df['target_up_small_1m'] = (df['future_ret_1m'] >= small_thr).astype(int) # small upward move in 1m
    df['target_up_med_3m'] = (df['future_ret_3m'] >= med_thr).astype(int)    # medium upward move in 3m

    # Optionally you may want down-targets too (mirror). Create if desired:
    df['target_down_small_1m'] = (df['future_ret_1m'] <= -small_thr).astype(int)
    df['target_down_med_3m'] = (df['future_ret_3m'] <= -med_thr).astype(int)

    # 5) housekeeping: drop last rows where future returns are NaN (cannot compute target)
    before = len(df)
    df = df.dropna(subset=['future_ret_1m', 'future_ret_3m'])
    after = len(df)
    dropped = before - after

    # 6) quick class balance print
    def freq(col):
        vc = df[col].value_counts().to_dict()
        return {int(k): int(v) for k, v in vc.items()}

    print("Rows total (after drop):", len(df))
    print("Rows dropped (tail with no future):", dropped)
    print("Class counts:")
    print(" target_dir_1m:", freq('target_dir_1m'))
    print(" target_up_small_1m:", freq('target_up_small_1m'))
    print(" target_up_med_3m:", freq('target_up_med_3m'))
    print(" target_down_small_1m:", freq('target_down_small_1m'))
    print(" target_down_med_3m:", freq('target_down_med_3m'))

    # 7) save (keep everything, including features + targets)
    outp.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(outp, index=False)
    print("Saved labeled dataset to:", outp)

if __name__ == "__main__":
    main()
