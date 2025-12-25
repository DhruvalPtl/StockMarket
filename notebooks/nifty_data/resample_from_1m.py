import pandas as pd
from pathlib import Path
import argparse

MARKET_TZ = "Asia/Kolkata"

def load_1m(path):
    df = pd.read_csv(path)
    ts_col = next((c for c in df.columns if c.lower() in ('timestamp','ts','time','datetime')), df.columns[0])

    # parse timestamp
    df[ts_col] = pd.to_datetime(df[ts_col], errors='coerce')

    # localize or convert to India timezone
    if df[ts_col].dt.tz is None:
        df[ts_col] = df[ts_col].dt.tz_localize(MARKET_TZ)
    else:
        df[ts_col] = df[ts_col].dt.tz_convert(MARKET_TZ)

    df = df.set_index(ts_col).sort_index()

    return df


def resample(df, rule, out_path):
    o = df['open'].resample(rule).first()
    h = df['high'].resample(rule).max()
    l = df['low'].resample(rule).min()
    c = df['close'].resample(rule).last()

    if 'volume' in df.columns:
        v = df['volume'].resample(rule).sum()
        out = pd.concat([o, h, l, c, v], axis=1)
        out.columns = ['open', 'high', 'low', 'close', 'volume']
    else:
        out = pd.concat([o, h, l, c], axis=1)
        out.columns = ['open', 'high', 'low', 'close']

    out = out.dropna(subset=['close'])  # drop intervals with no trading
    out.reset_index().to_csv(out_path, index=False)
    print(f"Saved {out_path} → {len(out)} rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_1m", required=True, help="Path to cleaned 1-minute file")
    ap.add_argument("--out_dir", required=True, help="Where to save resampled files")
    args = ap.parse_args()

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    df = load_1m(args.in_1m)

    # generate all timeframes
    resample(df, "5min", Path(args.out_dir) / "nifty_5m.csv")
    resample(df, "10min", Path(args.out_dir) / "nifty_10m.csv")
    resample(df, "15min", Path(args.out_dir) / "nifty_15m.csv")
    resample(df, "60min", Path(args.out_dir) / "nifty_1h.csv")
    resample(df, "1D", Path(args.out_dir) / "nifty_1d.csv")
    resample(df, "W-FRI", Path(args.out_dir) / "nifty_1w.csv")

if __name__ == "__main__":
    main()
