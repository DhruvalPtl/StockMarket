#!/usr/bin/env python3
"""
fix_timestamps_batch.py

Usage:
  python fix_timestamps_batch.py --input_dir "raw_folder" --out_dir "fixed_folder" [--fill_missing]

Processes all .csv files in input_dir using robust timestamp parsing and writes fixed CSVs to out_dir.
"""

import argparse, glob, os
from pathlib import Path
import pandas as pd
import numpy as np
import dateutil.parser
import pytz
from datetime import time

MARKET_TZ = "Asia/Kolkata"

def remove_repeated_header_rows(df):
    header = list(df.columns.astype(str))
    mask = []
    for i,row in df.iterrows():
        try:
            row_vals = [str(x).strip() for x in row.iloc[:len(header)].values]
            if row_vals == header:
                mask.append(i)
        except Exception:
            continue
    if mask:
        df = df.drop(index=mask).reset_index(drop=True)
    return df, len(mask)

def choose_best_ts_col(df):
    for c in df.columns:
        if str(c).lower() in ("timestamp","ts","time","datetime"):
            return c
    # heuristic on first 3 cols
    def looks_like_time(series):
        s = series.dropna().astype(str).head(10).tolist()
        if not s:
            return False
        iso_like = sum(1 for x in s if ('-' in x and ':' in x) or ('T' in x))
        numeric_like = sum(1 for x in s if x.isdigit())
        return iso_like >= max(1, len(s)//2) or numeric_like >= max(1, len(s)//2)
    for c in list(df.columns[:3]):
        if looks_like_time(df[c]):
            return c
    return df.columns[0]

def robust_parse_series(s):
    try:
        parsed = pd.to_datetime(s, utc=False, errors='coerce')
        na_frac = parsed.isna().mean()
        if na_frac > 0.25:
            def try_epoch(x):
                try:
                    x = float(x)
                except:
                    return pd.NaT
                if x > 1e12:
                    return pd.to_datetime(x, unit='ms', utc=False, errors='coerce')
                if x > 1e9:
                    return pd.to_datetime(x, unit='s', utc=False, errors='coerce')
                return pd.NaT
            parsed2 = s.apply(try_epoch)
            parsed = pd.to_datetime(parsed2, errors='coerce')
    except Exception:
        parsed = pd.Series([pd.NaT]*len(s), index=s.index)
    if parsed.isna().any():
        def try_dateutil(x):
            try:
                return pd.Timestamp(dateutil.parser.parse(str(x)))
            except Exception:
                return pd.NaT
        parsed = parsed.where(~parsed.isna(), s.apply(try_dateutil))
    return pd.to_datetime(parsed, errors='coerce')

def format_kolkata(ts):
    if pd.isna(ts):
        return ""
    mon = ts.month; day = ts.day; year = ts.year
    hour = ts.hour; minute = ts.minute; second = ts.second
    ampm = "AM" if hour < 12 else "PM"
    hour12 = hour % 12
    if hour12 == 0:
        hour12 = 12
    return f"{mon}/{day}/{year} {hour12}:{minute:02d}:{second:02d} {ampm}"

def process_and_save(inpath, outpath, fill_missing=False):
    p = Path(inpath)
    df = pd.read_csv(p, dtype=str)
    df, removed_headers = remove_repeated_header_rows(df)
    if removed_headers:
        print(f"  removed {removed_headers} repeated header rows")
    ts_col = choose_best_ts_col(df)
    raw_ts = df[ts_col].copy()
    parsed = robust_parse_series(raw_ts)
    # try alternatives if many NaT
    if parsed.isna().mean() > 0.5:
        for c in df.columns[:3]:
            if c == ts_col: continue
            parsed2 = robust_parse_series(df[c])
            if parsed2.notna().sum() > parsed.notna().sum():
                ts_col = c
                parsed = parsed2
                break
    if parsed.dropna().empty:
        print(f"  ERROR: could not parse timestamps in {p.name} - skipping")
        return {"file":p.name, "status":"failed", "reason":"no timestamps parsed"}
    # localize/convert to MARKET_TZ
    if parsed.dt.tz is not None:
        parsed = parsed.dt.tz_convert(MARKET_TZ)
    else:
        parsed = parsed.dt.tz_localize(MARKET_TZ)
    # format and replace
    df[ts_col] = parsed.apply(format_kolkata)
    outp = Path(outpath)
    df.to_csv(outp, index=False)
    # optional simple fill (only if requested and looks like 1-min)
    if fill_missing:
        # Build indexed DF using parsed timestamps
        df_indexed = df.copy()
        df_indexed['_parsed_ts'] = parsed
        # sort and set index
        df_indexed = df_indexed.set_index('_parsed_ts').sort_index()

        # quick check: median delta should be ~60s for 1-min files
        deltas = df_indexed.index.to_series().diff().dt.total_seconds().dropna()
        if deltas.empty or deltas.median() > 120:
            print("  Not a regular 1-minute file (median delta > 120s). Skipping reindex/fill.")
        else:
            all_days = sorted(set(df_indexed.index.date))
            out_frames = []
            skipped_days = 0
            for day in all_days:
                start = pd.Timestamp(f"{day} 09:15:00", tz=MARKET_TZ)
                end = pd.Timestamp(f"{day} 15:30:00", tz=MARKET_TZ)
                full_idx = pd.date_range(start=start, end=end, freq="1min", tz=MARKET_TZ)

                # take subframe for the day
                try:
                    sub = df_indexed.loc[df_indexed.index.date == day].copy()
                except Exception:
                    # defensive: if indexing fails, skip this day
                    skipped_days += 1
                    continue

                # DROP any duplicate minute timestamps before reindexing (keep last)
                if sub.index.duplicated().any():
                    dup_before = sub.index.duplicated().sum()
                    sub = sub[~sub.index.duplicated(keep='last')]
                    print(f"  Day {day}: removed {dup_before} duplicate minute rows before reindex")

                # Now reindex to full minute index and fill simple placeholders
                sub = sub.reindex(full_idx)
                sub = sub.fillna("")  # simple placeholder: empty strings for missing cells
                out_frames.append(sub)

            if not out_frames:
                print("  No day frames created during fill; nothing saved.")
            else:
                full = pd.concat(out_frames).sort_index()
                save_name = outp.with_name(outp.stem + "_filled" + outp.suffix)
                # reset index (parsed timestamps) to a column for CSV output
                full_reset = full.reset_index().rename(columns={'index': 'parsed_ts'})
                full_reset.to_csv(save_name, index=False)
                print(f"  reindexed/filled saved as {save_name.name}  (skipped_days: {skipped_days})")
    return {"file":p.name, "status":"ok", "rows":len(df)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_dir", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--fill_missing", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.input_dir, "*.csv")))
    report = []
    for f in files:
        print("Processing:", Path(f).name)
        outname = Path(args.out_dir) / (Path(f).stem + "_fixed.csv")
        r = process_and_save(f, outname, fill_missing=args.fill_missing)
        print("  ->", r)
        report.append(r)
    print("\nBatch finished. Processed files:", len(report))

if __name__ == "__main__":
    main()
