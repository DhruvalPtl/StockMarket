"""
Test RSI calculation - Verify against TradingView
"""

import pandas as pd
import numpy as np
from config import Config
from indicators import Indicators

# Load your actual data
config = Config()
df = pd.read_csv(config.data_file)
df['datetime'] = pd.to_datetime(df['datetime'])

# Calculate indicators
indicators = Indicators(config)
df = indicators.calculate_all(df)

print("=" * 80)
print("RSI VERIFICATION - Compare with TradingView")
print("=" * 80)

# Show RSI for 2025-12-10 starting from 09:15
target_date = "2025-12-10"
target_data = df[df['datetime'].dt.strftime('%Y-%m-%d') == target_date]

print(f"\nRSI VALUES for {target_date} (First 20 candles)")
print("-" * 80)
print(f"{'Time':>8} | {'Close':>10} | {'RSI (Ours)':>12} | {'RSI (TV)':>12} | {'Diff':>8}")
print("-" * 80)

# Your TradingView values
tv_rsi_values = [
    58.76, 70.22, 70.60, 76.33, 74.87, 52.93, 58.79, 59.49, 62.42, 51.93,
    51.18, 59.96, 59.82, 60.89, 64.69, 68.37, 68.73, 70.21, 61.70, 65.30
]

for idx, (_, row) in enumerate(target_data.head(20).iterrows()):
    time_str = row['datetime'].strftime("%H:%M")
    tv_value = tv_rsi_values[idx] if idx < len(tv_rsi_values) else None
    our_value = row['rsi']
    
    if tv_value is not None:
        diff = our_value - tv_value
        match = "✓" if abs(diff) < 1.0 else "✗"
        print(f"{time_str} | {row['close']:10.2f} | {our_value:12.2f} | "
              f"{tv_value:12.2f} | {diff:+8.2f} {match}")
    else:
        print(f"{time_str} | {row['close']:10.2f} | {our_value:12.2f} | "
              f"{'N/A':>12} | {'N/A':>8}")

print("-" * 80)

# Calculate average difference for available comparisons
diffs = []
for idx, (_, row) in enumerate(target_data.head(len(tv_rsi_values)).iterrows()):
    if idx < len(tv_rsi_values):
        diffs.append(abs(row['rsi'] - tv_rsi_values[idx]))

if diffs:
    avg_diff = np.mean(diffs)
    max_diff = max(diffs)
    print(f"\nAverage difference: {avg_diff:.2f}")
    print(f"Maximum difference: {max_diff:.2f}")
    
    if avg_diff < 1.0:
        print("✅ RSI calculation is CORRECT (within 1 point tolerance)")
    elif avg_diff < 2.0:
        print("⚠️  RSI calculation is CLOSE (within 2 point tolerance)")
    else:
        print("❌ RSI calculation needs adjustment (difference > 2 points)")

print("=" * 80)

# Show first 30 candles for reference
print("\nRSI VALUES (First 30 candles from start of data)")
print("-" * 80)
print(f"{'#':>3} | {'Time':>8} | {'Close':>10} | {'RSI':>8}")
print("-" * 80)

for i in range(min(30, len(df))):
    row = df.iloc[i]
    time_str = row['datetime'].strftime("%H:%M:%S")
    print(f"{i+1:3d} | {time_str} | {row['close']:10.2f} | {row['rsi']:8.2f}")

print("-" * 80)

# RSI distribution
print("\n" + "=" * 80)
print("RSI DISTRIBUTION")
print("=" * 80)
print(f"Min RSI:   {df['rsi'].min():.2f}")
print(f"Max RSI:   {df['rsi'].max():.2f}")
print(f"Mean RSI:  {df['rsi'].mean():.2f}")
print(f"Std RSI:   {df['rsi'].std():.2f}")

print(f"\nRSI < 30 (Oversold):   {(df['rsi'] < 30).sum():5d} candles ({(df['rsi'] < 30).sum() / len(df) * 100:5.1f}%)")
print(f"RSI 30-70 (Neutral):   {((df['rsi'] >= 30) & (df['rsi'] <= 70)).sum():5d} candles ({((df['rsi'] >= 30) & (df['rsi'] <= 70)).sum() / len(df) * 100:5.1f}%)")
print(f"RSI > 70 (Overbought): {(df['rsi'] > 70).sum():5d} candles ({(df['rsi'] > 70).sum() / len(df) * 100:5.1f}%)")

print("=" * 80)