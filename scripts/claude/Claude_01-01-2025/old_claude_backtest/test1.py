import pandas as pd

# Load your data
df = pd.read_csv("D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\data\\nifty_complete_1min.csv")

print("=" * 60)
print("DATA VERIFICATION")
print("=" * 60)

# 1. Check columns
print("\n📋 COLUMNS:")
print(df.columns.tolist())

# 2. Check first 10 rows
print("\n📊 FIRST 10 ROWS:")
print(df. head(10).to_string())

# 3. Check data types
print("\n📝 DATA TYPES:")
print(df. dtypes)

# 4. Check for NaN/missing
print("\n❓ MISSING VALUES:")
print(df. isnull().sum())

# 5. Check VWAP calculation
print("\n📈 VWAP CHECK (first day):")
df['datetime'] = pd.to_datetime(df['datetime'])
first_day = df[df['datetime']. dt.date == df['datetime'].dt. date.iloc[0]]
print(f"   First VWAP: {first_day['vwap'].iloc[0]}")
print(f"   Last VWAP:  {first_day['vwap'].iloc[-1]}")
print(f"   Does VWAP change? {first_day['vwap']. iloc[0] != first_day['vwap'].iloc[-1]}")

# 6. Check if we have separate spot and futures
print("\n📊 SPOT vs FUTURES:")
if 'fut_close' in df.columns:
    print(f"   Has fut_close: YES")
    print(f"   Spot close sample: {df['close'].iloc[50]}")
    print(f"   Fut close sample: {df['fut_close']. iloc[50]}")
    print(f"   Difference: {df['fut_close'].iloc[50] - df['close'].iloc[50]}")
else:
    print(f"   Has fut_close: NO ⚠️")

# 7. Check one option file
print("\n📁 OPTION CACHE CHECK:")
import os
cache_dir = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\option_cache"
if os.path.exists(cache_dir):
    files = os.listdir(cache_dir)[: 3]
    print(f"   Found {len(os.listdir(cache_dir))} cache files")
    print(f"   Sample files: {files}")
    
    # Check one file
    if files:
        sample_file = os. path.join(cache_dir, files[0])
        opt_df = pd.read_csv(sample_file)
        print(f"\n   Sample option file: {files[0]}")
        print(f"   Columns: {opt_df.columns.tolist()}")
        print(f"   Has OI column: {'oi' in opt_df.columns}")
        if 'oi' in opt_df.columns:
            print(f"   OI sample: {opt_df['oi'].head().tolist()}")
            print(f"   OI has data: {opt_df['oi'].sum() > 0}")
else:
    print(f"   Cache dir not found!  ⚠️")

print("\n" + "=" * 60)