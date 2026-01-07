"""
FLATTRADE DATA FETCHER TEST
============================
Fetches last 7 days of NIFTY data from Flattrade and saves to CSV.
Run this when market is closed to verify API connection.

Usage:
    python test_flattrade_data.py
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config import BotConfig, get_future_symbol
from utils.flattrade_wrapper import FlattradeWrapper


def test_flattrade_connection():
    """Test Flattrade API connection and data fetching"""
    
    print("\n" + "="*60)
    print("🧪 FLATTRADE API TEST")
    print("="*60)
    
    # 1. Connect to Flattrade
    print("\n📡 Step 1: Connecting to Flattrade...")
    try:
        api = FlattradeWrapper(
            user_id=BotConfig.USER_ID,
            user_token=BotConfig.USER_TOKEN
        )
        
        if not api.is_connected:
            print("❌ Connection Failed. Check your token in config.py")
            print("💡 Run: python gettoken.py")
            return
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return
    
    # 2. Calculate date range (last 7 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    print(f"\n📅 Step 2: Fetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # 3. Fetch NIFTY SPOT data
    print("\n📊 Step 3: Fetching NIFTY SPOT data...")
    spot_data = fetch_historical_data(
        api=api,
        symbol="NSE-NIFTY",
        exchange="NSE",
        start_date=start_date,
        end_date=end_date,
        interval="5minute"
    )
    
    if spot_data is not None and len(spot_data) > 0:
        csv_file = os.path.join(current_dir, "flattrade_spot_test.csv")
        spot_data.to_csv(csv_file, index=False)
        print(f"✅ SPOT Data saved: {csv_file}")
        print(f"   Rows: {len(spot_data)}")
        print(f"   Columns: {list(spot_data.columns)}")
        print(f"\n📈 Sample Data (Last 5 rows):")
        print(spot_data.tail())
    else:
        print("❌ No SPOT data received")
    
    # 4. Fetch NIFTY FUTURES data
    print(f"\n📊 Step 4: Fetching NIFTY FUTURES data...")
    
    # Generate future symbol
    fut_symbol = get_future_symbol(BotConfig.FUTURE_EXPIRY)
    print(f"   Future Symbol: {fut_symbol}")
    
    future_data = fetch_historical_data(
        api=api,
        symbol=fut_symbol,
        exchange="NSE",
        start_date=start_date,
        end_date=end_date,
        interval="5minute"
    )
    
    if future_data is not None and len(future_data) > 0:
        csv_file = os.path.join(current_dir, "flattrade_future_test.csv")
        future_data.to_csv(csv_file, index=False)
        print(f"✅ FUTURE Data saved: {csv_file}")
        print(f"   Rows: {len(future_data)}")
        print(f"\n📈 Sample Data (Last 5 rows):")
        print(future_data.tail())
    else:
        print("❌ No FUTURE data received")
    
    # 5. Summary
    print("\n" + "="*60)
    print("✅ TEST COMPLETE")
    print("="*60)
    if spot_data is not None and len(spot_data) > 0:
        print(f"✅ SPOT: {len(spot_data)} candles fetched")
    if future_data is not None and len(future_data) > 0:
        print(f"✅ FUTURE: {len(future_data)} candles fetched")
    print("\n📁 Check CSV files in the flatetrade folder!")
    print("="*60)


def fetch_historical_data(api, symbol, exchange, start_date, end_date, interval):
    """Fetch historical data and return as DataFrame"""
    
    all_candles = []
    current_date = start_date
    
    while current_date <= end_date:
        # Skip weekends
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
        
        # Fetch one day at a time
        day_start = current_date.replace(hour=9, minute=15, second=0, microsecond=0)
        day_end = current_date.replace(hour=15, minute=30, second=0, microsecond=0)
        
        try:
            resp = api.get_historical_candles(
                exchange=exchange,
                segment="CASH" if "FUT" not in symbol else "FNO",
                symbol=symbol,
                start_time=day_start.strftime("%Y-%m-%d %H:%M:%S"),
                end_time=day_end.strftime("%Y-%m-%d %H:%M:%S"),
                interval=interval
            )
            
            if resp and 'candles' in resp and len(resp['candles']) > 0:
                all_candles.extend(resp['candles'])
                print(f"   ✓ {current_date.strftime('%Y-%m-%d')}: {len(resp['candles'])} candles")
            else:
                print(f"   ✗ {current_date.strftime('%Y-%m-%d')}: No data (holiday/weekend)")
                
        except Exception as e:
            print(f"   ✗ {current_date.strftime('%Y-%m-%d')}: Error - {e}")
        
        current_date += timedelta(days=1)
    
    # Convert to DataFrame
    if len(all_candles) == 0:
        return None
    
    df = pd.DataFrame(all_candles)
    df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'][:len(df.columns)]
    
    # Sort by time
    df = df.sort_values('timestamp')
    
    return df


if __name__ == "__main__":
    test_flattrade_connection()
