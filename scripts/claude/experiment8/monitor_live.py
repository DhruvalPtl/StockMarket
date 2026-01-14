"""
LIVE MONITOR - Clean terminal display for live trading
Shows market data in a trading terminal format
"""

import sys
import os
import time
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from data.data_engine import DataEngine
from config import BotConfig


print("=" * 75)
print("⚡ LIVE MARKET MONITOR - Flattrade API")
print("=" * 75)
print(f"\nStarting: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Initialize
print("\n🔧 Initializing connection...")
engine = DataEngine(
    user_token=BotConfig.USER_TOKEN,
    user_id=BotConfig.USER_ID,
    option_expiry=BotConfig.OPTION_EXPIRY,
    future_expiry=BotConfig.FUTURE_EXPIRY,
    fut_symbol="NSE-NIFTY-27Jan26-FUT",
    timeframe='1minute'
)

if not engine.is_connected:
    print("❌ Not connected to API\n")
    exit(1)

print("✅ Connected! Starting live updates...\n")
print("Press Ctrl+C to stop\n")

# First full fetch
print("⏳ Initial data fetch (with candles)...")
engine.update(full_fetch=True)
engine.print_live_status(show_options=True)

# Live monitoring loop
update_count = 0
try:
    while True:
        time.sleep(5)  # Update every 5 seconds
        
        update_count += 1
        
        # Every 5 minutes do full fetch, otherwise just live prices
        full_fetch = (update_count % 60 == 0)  # 5 mins = 60 * 5 sec
        
        if full_fetch:
            print("\n🔄 Full refresh (indicators update)...")
        
        success = engine.update(full_fetch=full_fetch)
        
        if success:
            # Clear terminal (optional - comment out if you want history)
            # os.system('cls' if os.name == 'nt' else 'clear')
            
            engine.print_live_status(show_options=True)
        else:
            print(f"⚠️ Update failed at {datetime.now().strftime('%H:%M:%S')}")

except KeyboardInterrupt:
    print("\n\n🛑 Stopped by user")
    print(f"\nSession ended: {datetime.now().strftime('%H:%M:%S')}")
    print(f"Total updates: {update_count}")
    print(f"\nFinal prices:")
    print(f"  Spot:   ₹{engine.spot_ltp:,.2f}")
    print(f"  Future: ₹{engine.fut_ltp:,.2f}")
    print(f"  ATM:    {engine.atm_strike}")
    if engine.atm_strike in engine.strikes_data:
        data = engine.strikes_data[engine.atm_strike]
        print(f"  CE LTP: ₹{data.ce_ltp:.2f}")
        print(f"  PE LTP: ₹{data.pe_ltp:.2f}")
    print()

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
