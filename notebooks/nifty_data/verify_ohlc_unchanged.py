
"""
verify_ohlc_unchanged.py

Usage:
    python verify_ohlc_unchanged.py --raw_dir ".../raw_data" --fixed_dir ".../fixed"

Outputs a short report to console for each file pair.
"""

import argparse, glob, os
import pandas as pd
from pathlib import Path
import numpy as np
import dateutil.parser
import pytz

MARKET_TZ = "Asia/Kolkata"
OHLCV = ['open','high','low','close','volume']

def robust_parse_to_index(series):
    # try default parse, fallback to epoch ms/s, fallback to dateutil
    s = pd.to_datetime(series, errors='coerce')
    if s.isna().mean() > 0.5:
        # try numeric epoch (s or ms)
        def try_epoch(x):
            try:
                v = float(x)
            except:
                return pd.NaT
            if v > 1e12:
                return pd.to_datetime(v, unit='ms', errors='coerce')
            if v > 1e9:
                return pd.to_datetime(v, unit='s', errors='coerce')
            return pd.NaT
        s2 = series.apply(try_epoch)
        s = pd.to_datetime(s2, errors='coerce')
    # final fallback elementwise parse
    if s.isna().any():
        s = s.where(~s.isna(), series.apply(lambda x: pd.NaT if pd.isna(x) else pd.Timestamp(dateutil.parser.parse(str(x))) ))
    # localize naive -> MARKET_TZ; if tz-aware convert to MARKET_TZ
    if s.dt.tz is None:
        s = s.dt.tz_localize(MARKET_TZ)
    else:
        s = s.dt.tz_convert(MARKET_TZ)
    # floor to minute to be safe
    s = s.dt.floor('min')
    return s

def find_fixed_candidate(raw_path, fixed_dir):
    p = Path(raw_path)
    name = p.stem
    # try typical suffixes
    candidates = [
        Path(fixed_dir)/f"{name}_fixed.csv",
        Path(fixed_dir)/f"{name}_fixed_filled.csv",
        Path(fixed_dir)/f"{name}_filled.csv",
        Path(fixed_dir)/p.name  # same name may also exist in fixed folder
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # try any file that contains name
    for f in glob.glob(os.path.join(fixed_dir, "*.csv")):
        if name in Path(f).stem:
            return f
    return None

def compare_pair(raw_path, fixed_path, max_examples=10):
    print("Comparing:", Path(raw_path).name, "<->", Path(fixed_path).name)
    # load minimally (all columns as string to avoid dtype surprises)
    raw = pd.read_csv(raw_path, dtype=str)
    fixed = pd.read_csv(fixed_path, dtype=str)
    # detect timestamp columns (prefer 'timestamp' or first col)
    raw_ts_col = next((c for c in raw.columns if c.lower() in ('timestamp','ts','time','datetime')), raw.columns[0])
    fixed_ts_col = next((c for c in fixed.columns if c.lower() in ('timestamp','ts','time','datetime')), fixed.columns[0])
    # parse to index
    raw_idx = robust_parse_to_index(raw[raw_ts_col].astype(str))
    fixed_idx = robust_parse_to_index(fixed[fixed_ts_col].astype(str))
    raw = raw.copy().set_index(raw_idx)
    fixed = fixed.copy().set_index(fixed_idx)
    # Align on intersection of timestamps
    common_idx = raw.index.intersection(fixed.index)
    if len(common_idx) == 0:
        print("  No overlapping timestamps found. Skipping.")
        return {'file': Path(raw_path).name, 'overlap': 0, 'differences': None}
    raw_sub = raw.loc[common_idx]
    fixed_sub = fixed.loc[common_idx]
    # Normalize OHLCV columns presence & cast to numeric (NaN if not present)
    dif_mask = pd.Series(False, index=common_idx)
    dif_details = []
    for col in OHLCV:
        if col in raw_sub.columns and col in fixed_sub.columns:
            # convert to numeric
            rcol = pd.to_numeric(raw_sub[col].str.replace(',',''), errors='coerce')
            fcol = pd.to_numeric(fixed_sub[col].str.replace(',',''), errors='coerce')
            neq = ~(rcol.fillna(np.nan) == fcol.fillna(np.nan))
            neq = neq.fillna(False)
            dif_mask = dif_mask | neq
        else:
            # if column missing from either, mark as no-comparison for that col
            pass
    n_overlap = len(common_idx)
    n_diff = int(dif_mask.sum())
    print(f"  Overlap rows: {n_overlap:,}   Rows with any OHLCV difference: {n_diff:,}")
    if n_diff > 0:
        print("  Sample differences (up to", max_examples, "rows):")
        sample_idx = dif_mask[dif_mask].index[:max_examples]
        for ts in sample_idx:
            raw_vals = {c: (raw.loc[ts][c] if c in raw.columns else None) for c in OHLCV}
            fixed_vals = {c: (fixed.loc[ts][c] if c in fixed.columns else None) for c in OHLCV}
            print("   ", ts.strftime("%Y-%m-%d %H:%M"), "raw:", raw_vals, "fixed:", fixed_vals)
    else:
        print("  OK — no OHLCV differences on overlapping timestamps.")
    return {'file': Path(raw_path).name, 'overlap': n_overlap, 'differences': n_diff}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw_dir", required=True)
    ap.add_argument("--fixed_dir", required=True)
    args = ap.parse_args()
    raw_files = sorted(glob.glob(os.path.join(args.raw_dir, "*.csv")))
    report = []
    for rf in raw_files:
        fp = find_fixed_candidate(rf, args.fixed_dir)
        if not fp:
            print("No fixed file found for", Path(rf).name, "- skipping.")
            continue
        try:
            r = compare_pair(rf, fp)
            report.append(r)
        except Exception as e:
            print("Error comparing", rf, ":", e)
    # summary
    total = len(report)
    diffs = sum(1 for r in report if r['differences'] and r['differences']>0)
    print("\nSummary: files checked:", total, "files with differences:", diffs)
    for r in report:
        print(r)

if __name__ == "__main__":
    main()
