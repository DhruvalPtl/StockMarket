import pandas as pd
import pytz

# load 1m saved file
df = pd.read_csv("nifty_spot_1m.csv")
# robust timestamp conversion (handles string or epoch)
if df["timestamp"].dtype == "O":
    df["timestamp"] = pd.to_datetime(df["timestamp"])
else:
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s')

# If timestamps are naive, assume Asia/Kolkata (market timezone)
if df["timestamp"].dt.tz is None:
    df["timestamp"] = df["timestamp"].dt.tz_localize("Asia/Kolkata")
# convert to Asia/Kolkata for resampling convenience
df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Kolkata")

df = df.set_index("timestamp").sort_index()

def resample_and_save(df, rule, fname):
    ohlc = df['open'].resample(rule).first().to_frame('open')
    ohlc['high']  = df['high'].resample(rule).max()
    ohlc['low']   = df['low'].resample(rule).min()
    ohlc['close'] = df['close'].resample(rule).last()
    # volume: sum
    if 'volume' in df.columns:
        ohlc['volume'] = df['volume'].resample(rule).sum()
    # drop intervals with no trades (no close)
    ohlc = ohlc.dropna(subset=['close'])
    ohlc.to_csv(fname)
    print("Saved:", fname, "rows:", len(ohlc))

# common rules:
resample_and_save(df, "5T", "nifty_spot_5m.csv")      # 5 minutes
resample_and_save(df, "10T", "nifty_spot_10m.csv")    # 10 minutes
resample_and_save(df, "15T", "nifty_spot_15m.csv")    # 15 minutes
resample_and_save(df, "60T", "nifty_spot_1h.csv")     # 1 hour
resample_and_save(df, "1D", "nifty_spot_1d.csv")      # 1 day
# weekly candle — use market-close week (Friday)
resample_and_save(df, "W-FRI", "nifty_spot_1w.csv")
