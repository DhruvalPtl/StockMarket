"""
make_features.py

Reads a cleaned master dataset (parquet or csv) and produces a feature-rich parquet
file ready for modeling.

Usage:
    python make_features.py --in master_ml_dataset.parquet --out master_features.parquet
"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np

MARKET_TZ = "Asia/Kolkata"

def rolling_z(s, w):
    mu = s.rolling(window=w, min_periods=1).mean()
    sd = s.rolling(window=w, min_periods=1).std(ddof=0).replace(0, np.nan)
    return (s - mu) / (sd + 1e-9)

def ensure_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

def add_lags(df, cols, lags=(1,2,3)):
    for c in cols:
        for l in lags:
            df[f"{c}_lag{l}"] = df[c].shift(l)
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True, help="Input cleaned parquet/csv")
    ap.add_argument("--out", dest="outfile", required=True, help="Output features parquet")
    args = ap.parse_args()

    inp = Path(args.infile)
    out = Path(args.outfile)

    # 1. load
    if inp.suffix.lower() in (".parquet", ".pq"):
        df = pd.read_parquet(inp)
    else:
        df = pd.read_csv(inp)

    # 2. ensure timestamp is datetime and tz-aware
    if 'timestamp' not in df.columns:
        raise SystemExit("timestamp column not found")
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize(MARKET_TZ)
    else:
        df['timestamp'] = df['timestamp'].dt.tz_convert(MARKET_TZ)

    # sort by time
    df = df.sort_values('timestamp').reset_index(drop=True)

    # 3. ensure numeric columns
    numeric_cols = [
        'nifty_open','nifty_high','nifty_low','nifty_close',
        'atm_ce_ltp','atm_pe_ltp','itm_ce_ltp','itm_pe_ltp',
        'atm_ce_oi','atm_pe_oi','itm_ce_oi','itm_pe_oi'
    ]
    ensure_numeric(df, numeric_cols)

    # 4. create basic returns (spot + options)
    df['nifty_ret_1'] = df['nifty_close'].pct_change(1)
    df['nifty_ret_3'] = df['nifty_close'].pct_change(3)
    df['ce_ret_1'] = df['atm_ce_ltp'].pct_change(1)
    df['pe_ret_1'] = df['atm_pe_ltp'].pct_change(1)
    df['itm_ce_ret_1'] = df['itm_ce_ltp'].pct_change(1)
    df['itm_pe_ret_1'] = df['itm_pe_ltp'].pct_change(1)

    # 5. CE/PE ratio & difference
    df['ce_pe_ratio'] = df['atm_ce_ltp'] / (df['atm_pe_ltp'] + 1e-9)
    df['ce_minus_pe'] = df['atm_ce_ltp'] - df['atm_pe_ltp']

    # 6. ATM-ITM spreads
    df['atm_itm_spread_ce'] = df['atm_ce_ltp'] - df['itm_ce_ltp']
    df['atm_itm_spread_pe'] = df['atm_pe_ltp'] - df['itm_pe_ltp']

    # 7. rolling vol (use pct returns)
    df['nifty_vol_5'] = df['nifty_ret_1'].rolling(window=5, min_periods=1).std(ddof=0)
    df['nifty_vol_15'] = df['nifty_ret_1'].rolling(window=15, min_periods=1).std(ddof=0)

    # 8. ATR-like short range (range = high - low)
    df['range_1'] = df['nifty_high'] - df['nifty_low']
    df['atr_5'] = df['range_1'].rolling(window=5, min_periods=1).mean()

    # 9. volatility regime
    df['vol_regime'] = df['atr_5'] / (df['nifty_vol_15'] + 1e-9)

    # 10. option OI rolling z-score per expiry (60-min window) - if expiry exists
    if 'expiry' in df.columns:
        # ensure expiry standardized
        df['expiry'] = df['expiry'].astype(str)
        for col in ['atm_ce_oi','atm_pe_oi','itm_ce_oi','itm_pe_oi']:
            if col in df.columns:
                df[col + '_z60'] = df.groupby('expiry')[col].transform(lambda s: rolling_z(s.fillna(), 60))
    else:
        # fallback global rolling z
        for col in ['atm_ce_oi','atm_pe_oi','itm_ce_oi','itm_pe_oi']:
            if col in df.columns:
                df[col + '_z60'] = rolling_z(df[col].fillna(), 60)

    # 11. OI change rates (short)
    df['oi_ce_change_1'] = df['atm_ce_oi'].pct_change(1)
    df['oi_pe_change_1'] = df['atm_pe_oi'].pct_change(1)

    # 12. atm_shift (if atm_strike exists)
    if 'atm_strike' in df.columns:
        df['atm_shift'] = df['atm_strike'].diff().abs().fillna(0) / 50.0
    else:
        df['atm_shift'] = 0.0

    # 13. minute_of_day & cyclic seasonality
    df['minute_of_day'] = df['timestamp'].dt.hour * 60 + df['timestamp'].dt.minute
    df['sin_md'] = np.sin(2 * np.pi * df['minute_of_day'] / 390.0)
    df['cos_md'] = np.cos(2 * np.pi * df['minute_of_day'] / 390.0)

    # 14. rolling high/low breakouts (15-min)
    df['high_15'] = df['nifty_high'].rolling(window=15, min_periods=1).max()
    df['low_15'] = df['nifty_low'].rolling(window=15, min_periods=1).min()
    df['above_breakout_15'] = (df['nifty_close'] > df['high_15']).astype(int)
    df['below_breakout_15'] = (df['nifty_close'] < df['low_15']).astype(int)

    # 15. atm vs itm pressure ratios
    df['atm_itm_ce_ratio'] = df['atm_ce_ltp'] / (df['itm_ce_ltp'] + 1e-9)
    df['atm_itm_pe_ratio'] = df['atm_pe_ltp'] / (df['itm_pe_ltp'] + 1e-9)

    # 16. momentum deltas & interaction features
    df['mom_delta'] = df['ce_ret_1'] - df['pe_ret_1']
    df['mom_3_sum'] = df['ce_ret_1'].rolling(3, min_periods=1).sum() + df['pe_ret_1'].rolling(3, min_periods=1).sum()

    # 17. lags for key features (spot and options)
    lag_cols = [
        'nifty_ret_1','nifty_ret_3',
        'ce_ret_1','pe_ret_1','itm_ce_ret_1','itm_pe_ret_1',
        'ce_pe_ratio','ce_minus_pe','atm_itm_spread_ce','atm_itm_spread_pe',
        'atm_ce_oi_z60','atm_pe_oi_z60','itm_ce_oi_z60','itm_pe_oi_z60'
    ]
    df = add_lags(df, [c for c in lag_cols if c in df.columns], lags=(1,2,3))

    # 18. small cleanups: replace inf and huge values
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    # optionally fill remaining NaNs in feature columns with 0 (safe for many models)
    feature_cols = [
        # core
        'nifty_ret_1','nifty_ret_3','ce_ret_1','pe_ret_1','itm_ce_ret_1','itm_pe_ret_1',
        'ce_pe_ratio','ce_minus_pe','atm_itm_spread_ce','atm_itm_spread_pe',
        'atm_ce_oi_z60','atm_pe_oi_z60','itm_ce_oi_z60','itm_pe_oi_z60',
        'oi_ce_change_1','oi_pe_change_1','atm_shift',
        'nifty_vol_5','nifty_vol_15','atr_5','vol_regime',
        'sin_md','cos_md','minute_of_day',
        'above_breakout_15','below_breakout_15','atm_itm_ce_ratio','atm_itm_pe_ratio',
        'mom_delta','mom_3_sum'
    ]
    # keep only those that exist
    feature_cols = [c for c in feature_cols if c in df.columns]
    df[feature_cols] = df[feature_cols].fillna(0)

    # 19. save (parquet)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print("Saved features to", out)
    print("Rows:", len(df))
    print("Example features:", feature_cols[:20])

if __name__ == "__main__":
    main()
