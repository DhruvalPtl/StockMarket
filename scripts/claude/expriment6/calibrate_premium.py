"""
CALIBRATE PREMIUM SCRIPT
Run this to statistically determine the correct Bias thresholds.
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import BotConfig, get_future_symbol
    from growwapi import GrowwAPI
except ImportError:
    print("❌ Critical Error: Could not import config or growwapi.")
    print("Make sure you run this from the experiment6 folder.")
    sys.exit(1)

def calibrate():
    print("\n🔬 PREMIUM CALIBRATION TOOL")
    print("===========================")
    
    # 1. Connect
    print("🔑 Connecting to Groww...")
    groww = GrowwAPI(BotConfig.API_KEY)
    
    # 2. Settings
    days_to_fetch = 10
    timeframe = "1minute"
    
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days_to_fetch)
    
    # 3. Fetch Spot Data
    print(f"📊 Fetching NIFTY SPOT data (Last {days_to_fetch} days)...")
    resp_spot = groww.get_historical_candles(
        "NSE", "CASH", "NSE-NIFTY",
        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        timeframe
    )
    
    if not resp_spot or not resp_spot.get('candles'):
        print("❌ Error: No Spot data received.")
        return

    df_spot = pd.DataFrame(resp_spot['candles'])
    df_spot.columns = ['t', 'o', 'h', 'l', 'c', 'v'][:len(df_spot.columns)]
    df_spot['t'] = pd.to_datetime(df_spot['t'])
    df_spot = df_spot.set_index('t')[['c']].rename(columns={'c': 'spot_close'})

    # 4. Fetch Future Data
    # Use the future expiry from config
    fut_symbol = get_future_symbol(BotConfig.FUTURE_EXPIRY)
    print(f"📊 Fetching FUTURE data ({fut_symbol})...")
    
    resp_fut = groww.get_historical_candles(
        "NSE", "FNO", fut_symbol,
        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        timeframe
    )
    
    if not resp_fut or not resp_fut.get('candles'):
        print(f"❌ Error: No Future data received for {fut_symbol}.")
        return

    df_fut = pd.DataFrame(resp_fut['candles'])
    df_fut.columns = ['t', 'o', 'h', 'l', 'c', 'v', 'oi'][:len(df_fut.columns)]
    df_fut['t'] = pd.to_datetime(df_fut['t'])
    df_fut = df_fut.set_index('t')[['c']].rename(columns={'c': 'fut_close'})

    # 5. Merge & Calculate Premium
    print("🧮 Calculating Premium statistics...")
    df = df_spot.join(df_fut, how='inner')
    
    if len(df) == 0:
        print("❌ Error: No overlapping timestamps found between Spot and Future.")
        return
        
    df['premium'] = df['fut_close'] - df['spot_close']
    
    # 6. Calculate Statistics
    avg_prem = df['premium'].mean()
    median_prem = df['premium'].median()
    std_prem = df['premium'].std()
    
    # Percentiles
    p10 = np.percentile(df['premium'], 10)  # Strong Bearish Threshold
    p25 = np.percentile(df['premium'], 25)  # Bearish Threshold
    p75 = np.percentile(df['premium'], 75)  # Bullish Threshold
    p90 = np.percentile(df['premium'], 90)  # Strong Bullish Threshold
    
    print("\n✅ ANALYSIS COMPLETE")
    print(f"   Data Points: {len(df)}")
    print(f"   Average Premium: {avg_prem:.2f}")
    print(f"   Median Premium:  {median_prem:.2f}")
    print(f"   Std Deviation:   {std_prem:.2f}")
    print("-" * 30)
    print(f"   Min: {df['premium'].min():.2f} | Max: {df['premium'].max():.2f}")
    
    print("\n📋 RECOMMENDED CONFIGURATION")
    print("============================")
    print("Update the 'Bias' class in config.py with these values:\n")
    
    print(f"    PREMIUM_STRONG_BULLISH = {int(p90)}   # (Top 10% of values)")
    print(f"    PREMIUM_BULLISH        = {int(p75)}   # (Top 25% of values)")
    print(f"    PREMIUM_NEUTRAL_LOW    = {int(p25)}   # (Bottom 25% of values)")
    print(f"    PREMIUM_BEARISH        = {int(p10)}   # (Bottom 10% of values)")
    print("\n============================")

if __name__ == "__main__":
    calibrate()