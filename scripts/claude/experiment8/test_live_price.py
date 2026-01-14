"""
LIVE PRICE FETCH TEST - Test real-time price fetching speed
"""

import sys
import os
import time
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from data.data_engine import DataEngine
from config import BotConfig


def format_ms(seconds: float) -> str:
    """Format seconds as milliseconds."""
    return f"{seconds * 1000:.1f}ms"


print("=" * 80)
print("⚡ LIVE PRICE FETCHING TEST")
print("=" * 80)
print(f"\nTest Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Initialize
print("🔧 Initializing...")
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

print("✅ Connected!\n")

# First do a full update to get candles
print("=" * 80)
print("📊 FIRST UPDATE - Full Fetch (with historical candles)")
print("=" * 80)

start = time.time()
success = engine.update(full_fetch=True)
elapsed = time.time() - start

if success:
    print(f"\n✅ Full update completed in {format_ms(elapsed)}")
    print(f"\n   Timing breakdown:")
    print(f"   • Spot candles:    {format_ms(engine.timing_stats['spot_fetch'])}")
    print(f"   • Future candles:  {format_ms(engine.timing_stats['future_fetch'])}")
    print(f"   • Option chain:    {format_ms(engine.timing_stats['option_fetch'])}")
    print(f"   • Total:           {format_ms(engine.timing_stats['total_update'])}")
    
    print(f"\n   📈 Data:")
    print(f"   • Spot LTP:    ₹{engine.spot_ltp:.2f}")
    print(f"   • Future LTP:  ₹{engine.fut_ltp:.2f}")
    print(f"   • ATM Strike:  {engine.atm_strike}")
    print(f"   • ATM CE:      ₹{engine.atm_ce_ltp:.2f}")
    print(f"   • ATM PE:      ₹{engine.atm_pe_ltp:.2f}")
    print(f"   • Option strikes: {len(engine.strikes_data)}")

# Now test live price fetching
print("\n" + "=" * 80)
print("⚡ LIVE PRICE UPDATES (fast mode - no candle fetch)")
print("=" * 80)

for i in range(5):
    print(f"\n🔄 Update {i+1}/5")
    print("-" * 80)
    
    start = time.time()
    success = engine.update(full_fetch=False)  # Use cached candles
    elapsed = time.time() - start
    
    if success:
        print(f"   ⚡ Update time: {format_ms(elapsed)}")
        print(f"   • Live prices:  {format_ms(engine.timing_stats.get('live_prices', 0))}")
        print(f"   • Options:      {format_ms(engine.timing_stats['option_fetch'])}")
        print(f"   • Total:        {format_ms(engine.timing_stats['total_update'])}")
        
        print(f"\n   📊 Current prices:")
        print(f"   • Spot:    ₹{engine.spot_ltp:.2f}")
        print(f"   • Future:  ₹{engine.fut_ltp:.2f}")
        print(f"   • ATM CE:  ₹{engine.atm_ce_ltp:.2f}")
        print(f"   • ATM PE:  ₹{engine.atm_pe_ltp:.2f}")
    
    time.sleep(2)  # 2 second interval

# Test pure live price fetch
print("\n" + "=" * 80)
print("🚀 PURE LIVE PRICE FETCH (fastest mode)")
print("=" * 80)

print("\nTesting get_live_prices() method (no options)...\n")

for i in range(3):
    start = time.time()
    success = engine.get_live_prices()
    elapsed = time.time() - start
    
    if success:
        print(f"   Update {i+1}: {format_ms(elapsed):>8} | Spot: ₹{engine.spot_ltp:.2f} | Future: ₹{engine.fut_ltp:.2f}")
    
    time.sleep(1)

print("\n" + "=" * 80)
print("📊 PERFORMANCE SUMMARY")
print("=" * 80)

print("""
   ⏱️  Speed Comparison:
   
   📦 Full Fetch (candles + options):     ~60-70 seconds
      → Use once per 5 minutes for indicators
      
   ⚡ Hybrid Mode (live prices + options): ~5-10 seconds  
      → Use every 1 minute for trading
      
   🚀 Pure Live (just spot/future LTP):    ~200-500ms
      → Use for rapid price monitoring
      
   💡 Recommended Strategy:
      • Full fetch: Every 5 minutes (for RSI, EMA, VWAP)
      • Hybrid mode: Every 30-60 seconds (for trading)
      • Pure live: As needed for instant price checks
""")

print("=" * 80)
print("✅ Test complete!")
print("=" * 80)
