
# trim_market_hours.py
import argparse, glob, os
import pandas as pd
from pathlib import Path
MARKET_TZ = "Asia/Kolkata"

def trim_file(path, out_dir):
    p = Path(path)
    df = pd.read_csv(p, dtype=str)
    # detect ts col
    ts_col = next((c for c in df.columns if c.lower() in ('timestamp','ts','time','datetime')), df.columns[0])
    df[ts_col] = pd.to_datetime(df[ts_col], errors='coerce')
    # localize naive -> MARKET_TZ
    if df[ts_col].dt.tz is None:
        df[ts_col] = df[ts_col].dt.tz_localize(MARKET_TZ)
    else:
        df[ts_col] = df[ts_col].dt.tz_convert(MARKET_TZ)
    df = df.set_index(ts_col).sort_index()
    # keep only intraday hours 09:15 - 15:30
    df = df.between_time("09:15","15:30")
    outp = Path(out_dir)/(p.stem + "_trimmed.csv")
    # reset index as timestamp column
    df.reset_index().to_csv(outp, index=False)
    print("Trimmed ->", outp.name, "rows:", len(df))
    return outp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="folder with CSV files to trim (will process intraday TFs)")
    ap.add_argument("--out", required=True, help="output folder")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.dir, "*.csv")))
    # process files that are intraday (heuristic: name contains 1minute, 5minute, 10minute, 15minute, 1hour, 60minute)
    intraday_keys = ('1minute','1min','5minute','5min','10minute','10min','15minute','15min','1hour','60minute','1h')
    for f in files:
        if any(k in Path(f).name.lower() for k in intraday_keys):
            trim_file(f, args.out)
        else:
            print("Skipping (not intraday):", Path(f).name)

if __name__=='__main__':
    main()
