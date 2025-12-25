#!/usr/bin/env python3
"""
fix_timestamp_single_file.py

Usage:
  python fix_timestamp_single_file.py --in "raw.csv" --out "fixed.csv" [--fill_missing True]

What it does:
- Load single CSV
- Remove internal repeated header rows (rows where the first N cells equal the header)
- Detect timestamp column (or two) and pick the best non-null column
- Parse timestamps robustly (ISO / epoch / common formats)
- Localize to Asia/Kolkata and convert to that tz
- Format timestamp to: M/D/YYYY h:mm:ss AM/PM  (e.g. 12/8/2025 12:17:00 PM)
- Save to output CSV (keeps other columns untouched)

Note: It will print a small report. It does not rename your other columns.
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import dateutil.parser
import pytz
from datetime import time

MARKET_TZ = "Asia/Kolkata"

def remove_repeated_header_rows(df):
    # Detect rows that equal the header text (common when CSVs have repeated header lines)
    header = list(df.columns.astype(str))
    mask = []
    for i,row in df.iterrows():
        # Compare first len(header) columns to header strings
        try:
            row_vals = [str(x).strip() for x in row.iloc[:len(header)].values]
            if row_vals == header:
                mask.append(i)
        except Exception:
            continue
    if mask:
        df = df.drop(index=mask).reset_index(drop=True)
    return df, len(mask)

def find_timestamp_column(df):
    # Prefer column named timestamp/ts/time/datetime (case-insensitive)
    for c in df.columns:
        if str(c).lower() in ("timestamp","ts","time","datetime"):
            return c
    # else, check first two columns if they look like times
    candidates = list(df.columns[:3])
    def looks_like_time(series):
        s = series.dropna().astype(str).head(10).tolist()
        if not s:
            return False
        # If many strings contain '-' and 'T' or ':' assume datetime strings
        iso_like = sum(1 for x in s if ('-' in x and ':' in x) or ('T' in x))
        numeric_like = sum(1 for x in s if x.isdigit())
        # heuristics
        return iso_like >= max(1, len(s)//2) or numeric_like >= max(1, len(s)//2)
    for c in candidates:
        if looks_like_time(df[c]):
            return c
    # fallback: first column
    return df.columns[0]

def choose_best_ts_col(df):
    # If there are multiple timestamp-like cols, choose the one with most non-nulls after parse attempt
    ts_cols = []
    for c in df.columns:
        s = df[c].astype(str).fillna("")
        if s.str.contains("[:\-T]").any() or s.str.match(r'^\d{9,}$').any():
            ts_cols.append(c)
    if not ts_cols:
        # fallback
        return find_timestamp_column(df)
    # choose column with most non-empty values
    counts = {c: df[c].notna().sum() for c in ts_cols}
    best = max(counts, key=counts.get)
    return best

def robust_parse_series(s):
    """
    s: pd.Series of strings or numbers
    Returns pd.DatetimeIndex tz-localized to Asia/Kolkata (naive timestamps treated as LOCAL)
    """
    # Try direct pandas parse first
    try:
        parsed = pd.to_datetime(s, utc=False, errors='coerce')
        # If many values are NaT, try epoch parse
        na_frac = parsed.isna().mean()
        if na_frac > 0.25:
            # try numeric epoch parse
            # if values are numeric-like large ints (10-digit/13-digit)
            def try_epoch(x):
                try:
                    x = float(x)
                except:
                    return pd.NaT
                # determine if seconds or ms
                if x > 1e12:
                    return pd.to_datetime(x, unit='ms', utc=False, errors='coerce')
                if x > 1e9:
                    return pd.to_datetime(x, unit='s', utc=False, errors='coerce')
                return pd.NaT
            parsed2 = s.apply(try_epoch)
            parsed = pd.to_datetime(parsed2, errors='coerce')
    except Exception:
        parsed = pd.Series([pd.NaT]*len(s), index=s.index)
    # Final fallback: try dateutil per element for remaining NaT (slower)
    if parsed.isna().any():
        for i,val in parsed[parsed.isna()].index:
            pass
        # vectorized attempt for remaining
        def try_dateutil(x):
            try:
                return pd.Timestamp(dateutil.parser.parse(str(x)))
            except Exception:
                return pd.NaT
        parsed = parsed.where(~parsed.isna(), s.apply(try_dateutil))
    return pd.to_datetime(parsed, errors='coerce')

def process_one_file(in_path, out_path, fill_missing=False):
    p = Path(in_path)
    print("Loading:", p)
    df = pd.read_csv(p, dtype=str)  # load everything as string to be safe
    print("Raw rows:", len(df), "cols:", list(df.columns)[:8])
    # Remove repeated header rows if any
    df, removed_headers = remove_repeated_header_rows(df)
    if removed_headers:
        print(f"Removed {removed_headers} repeated header rows inside file.")
    # Detect best timestamp column
    ts_col = choose_best_ts_col(df)
    print("Detected timestamp column:", ts_col)
    # Keep original ts values for debug
    raw_ts = df[ts_col].copy()
    # Parse
    parsed = robust_parse_series(raw_ts)
    # If parsing failed heavily (most NaT), try alternate columns if present
    if parsed.isna().mean() > 0.5:
        # try other candidates (first 3 columns)
        tried = [ts_col]
        for c in df.columns[:3]:
            if c in tried:
                continue
            parsed2 = robust_parse_series(df[c])
            if parsed2.notna().sum() > parsed.notna().sum():
                print("Alternate timestamp column", c, "parsed better. Switching.")
                ts_col = c
                parsed = parsed2
                break
    # Final check: ensure we have at least some parsed datetimes
    if parsed.dropna().empty:
        raise ValueError("Could not parse any timestamps in file. Please inspect file manually.")
    # Localize/convert to Asia/Kolkata
    # If parsed tz-aware, convert; if naive, assume MARKET_TZ
    if parsed.dt.tz is not None:
        parsed = parsed.dt.tz_convert(MARKET_TZ)
    else:
        parsed = parsed.dt.tz_localize(MARKET_TZ)
    # Replace timestamp column with formatted string
    # Desired format example: 12/8/2025 12:17:00 PM -> strftime: %-m/%-d/%Y %-I:%M:%S %p
    # But Windows Python doesn't support '-' flags; use robust approach:
    def format_kolkata(ts):
        if pd.isna(ts):
            return ""
        # convert to naive localized time for formatting components
        # We will produce month/day without zero pad manually
        mon = ts.month
        day = ts.day
        year = ts.year
        hour = ts.hour
        minute = ts.minute
        second = ts.second
        ampm = "AM" if hour < 12 else "PM"
        hour12 = hour % 12
        if hour12 == 0:
            hour12 = 12
        return f"{mon}/{day}/{year} {hour12}:{minute:02d}:{second:02d} {ampm}"
    formatted = parsed.apply(format_kolkata)
    # Write back to df (replace ts_col)
    df[ts_col] = formatted
    # Save output (no index)
    outp = Path(out_path)
    df.to_csv(outp, index=False)
    print("Saved fixed file:", outp, "rows:", len(df))
    # Optional: if fill_missing True and inferred frequency ~1min, reindex and save extra file
    if fill_missing:
        # Try to build DataFrame with parsed as index to reindex minute range
        df_indexed = df.copy()
        df_indexed['_parsed_ts'] = parsed
        df_indexed = df_indexed.set_index('_parsed_ts').sort_index()
        # detect if median delta ~60s
        deltas = df_indexed.index.to_series().diff().dt.total_seconds().dropna()
        if deltas.empty or deltas.median() > 120:
            print("Not a regular 1-minute file; skipping reindex/fill.")
        else:
            # build full minute range per day between 09:15 and 15:30
            all_days = sorted(set(df_indexed.index.date))
            rows_added = 0
            out_frames = []
            for day in all_days:
                start = pd.Timestamp(f"{day} 09:15:00", tz=MARKET_TZ)
                end = pd.Timestamp(f"{day} 15:30:00", tz=MARKET_TZ)
                full_idx = pd.date_range(start=start, end=end, freq="1min", tz=MARKET_TZ)
                sub = df_indexed.loc[(df_indexed.index.date == day)].reindex(full_idx)
                # Fill strategy: forward-fill string columns? we skip complex fill here
                sub = sub.fillna("")  # simple placeholder; user can post-process
                out_frames.append(sub)
                rows_added += sub.isna().sum().sum()
            if out_frames:
                full = pd.concat(out_frames)
                # remove the index column before saving
                full_reset = full.reset_index().rename(columns={'index':'_parsed_ts'})
                save_name = outp.with_name(outp.stem + "_filled" + outp.suffix)
                full_reset.to_csv(save_name, index=False)
                print("Saved reindexed/filled file:", save_name)
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True, help="input CSV path")
    ap.add_argument("--out", dest="outfile", required=True, help="output CSV path")
    ap.add_argument("--fill_missing", action="store_true", help="optional: create reindexed filled 1-min file (simple fill)")
    args = ap.parse_args()
    process_one_file(args.infile, args.outfile, fill_missing=args.fill_missing)

if __name__ == "__main__":
    main()

