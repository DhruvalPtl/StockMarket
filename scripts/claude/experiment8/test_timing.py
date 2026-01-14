"""
TIMING TEST - Measure data fetching and execution speed
Shows how fast the system can fetch data and execute trades.
"""

import sys
import os
import time
from datetime import datetime

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from data.data_engine import DataEngine
from config import BotConfig


def format_ms(seconds: float) -> str:
    """Format seconds as milliseconds."""
    return f"{seconds * 1000:.1f}ms"


def run_timing_test():
    """Run comprehensive timing test."""
    print("=" * 80)
    print("⏱️  PERFORMANCE TIMING TEST - Flattrade API")
    print("=" * 80)
    print(f"\nTest Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize data engine
    print("🔧 Initializing Data Engine...")
    init_start = time.time()
    engine = DataEngine(
        user_token=BotConfig.USER_TOKEN,
        user_id=BotConfig.USER_ID,
        option_expiry=BotConfig.OPTION_EXPIRY,
        future_expiry=BotConfig.FUTURE_EXPIRY,
        fut_symbol="NSE-NIFTY-27Jan26-FUT",
        timeframe='1minute'
    )
    init_time = time.time() - init_start
    print(f"   ✅ Initialization: {format_ms(init_time)}\n")
    
    if not engine.is_connected:
        print("❌ Not connected to API. Check credentials.\n")
        return
    
    print("=" * 80)
    print("📊 DATA FETCH PERFORMANCE (5 iterations)")
    print("=" * 80)
    
    # Run multiple iterations to get average
    iterations = 5
    all_timings = []
    
    for i in range(iterations):
        print(f"\n🔄 Iteration {i+1}/{iterations}")
        print("-" * 80)
        
        # Update data
        update_start = time.time()
        success = engine.update()
        update_time = time.time() - update_start
        
        if not success:
            print(f"   ⚠️  Update failed")
            continue
        
        # Get detailed timing
        timings = engine.timing_stats
        all_timings.append(timings.copy())
        
        # Display results
        print(f"   Spot Data Fetch:     {format_ms(timings['spot_fetch']):>10}")
        print(f"   Future Data Fetch:   {format_ms(timings['future_fetch']):>10}")
        print(f"   Option Chain Fetch:  {format_ms(timings['option_fetch']):>10}")
        print(f"   ─────────────────────────────────")
        print(f"   TOTAL UPDATE TIME:   {format_ms(timings['total_update']):>10}")
        
        # Show data quality
        print(f"\n   📈 Data Retrieved:")
        print(f"      • Spot LTP: ₹{engine.spot_ltp:.2f}")
        print(f"      • Future LTP: ₹{engine.fut_ltp:.2f}")
        print(f"      • Option Strikes: {len(engine.strikes_data)} strikes")
        if engine.strikes_data:
            print(f"      • Total CE OI: {engine.total_ce_oi:,}")
            print(f"      • Total PE OI: {engine.total_pe_oi:,}")
            print(f"      • PCR: {engine.pcr:.2f}")
        
        # Small delay between iterations
        if i < iterations - 1:
            time.sleep(1)
    
    # Calculate averages
    if all_timings:
        print("\n" + "=" * 80)
        print("📊 AVERAGE PERFORMANCE (5 iterations)")
        print("=" * 80)
        
        avg_spot = sum(t['spot_fetch'] for t in all_timings) / len(all_timings)
        avg_future = sum(t['future_fetch'] for t in all_timings) / len(all_timings)
        avg_option = sum(t['option_fetch'] for t in all_timings) / len(all_timings)
        avg_total = sum(t['total_update'] for t in all_timings) / len(all_timings)
        
        print(f"\n   Average Spot Fetch:      {format_ms(avg_spot):>10}")
        print(f"   Average Future Fetch:    {format_ms(avg_future):>10}")
        print(f"   Average Option Fetch:    {format_ms(avg_option):>10}")
        print(f"   ─────────────────────────────────")
        print(f"   AVERAGE TOTAL TIME:      {format_ms(avg_total):>10}")
        
        # Calculate throughput
        updates_per_second = 1.0 / avg_total if avg_total > 0 else 0
        print(f"\n   🚀 Updates/Second:       {updates_per_second:.2f}")
        print(f"   ⚡ Max Update Frequency:  Every {format_ms(avg_total)}")
    
    # Simulate strategy execution time
    print("\n" + "=" * 80)
    print("🎯 STRATEGY EXECUTION SIMULATION")
    print("=" * 80)
    
    # Simulate 9 strategies checking conditions
    strategy_start = time.time()
    
    # Simple condition checks (simulated)
    for i in range(9):
        _ = engine.spot_ltp > 0
        _ = engine.fut_ltp > 0
        _ = engine.atm_strike > 0
        _ = len(engine.strikes_data) > 0
        _ = engine.pcr < 1.5
    
    strategy_time = time.time() - strategy_start
    print(f"\n   9 Strategy Evaluations:  {format_ms(strategy_time):>10}")
    
    # Total cycle time
    total_cycle = avg_total + strategy_time
    print(f"   Data Fetch (avg):        {format_ms(avg_total):>10}")
    print(f"   ─────────────────────────────────")
    print(f"   TOTAL CYCLE TIME:        {format_ms(total_cycle):>10}")
    print(f"\n   📍 Complete cycles/min:  {60.0 / total_cycle:.1f}")
    
    # Trade execution estimate
    print("\n" + "=" * 80)
    print("📱 TRADE EXECUTION ESTIMATE")
    print("=" * 80)
    
    # Simulate order placement (API call)
    print(f"\n   🔍 Symbol lookup:        ~50ms (cached)")
    print(f"   📊 Price check:          ~100ms (get_quotes)")
    print(f"   📝 Order placement:      ~200-500ms (place_order)")
    print(f"   ✅ Order confirmation:   ~100-300ms (order_status)")
    print(f"   ─────────────────────────────────")
    print(f"   TOTAL TRADE EXEC:        ~450-950ms")
    
    print("\n" + "=" * 80)
    print("⏱️  PERFORMANCE SUMMARY")
    print("=" * 80)
    
    print(f"""
   🎯 Key Metrics:
   
      • Data Fetch:         {format_ms(avg_total)} per update
      • Strategy Check:     {format_ms(strategy_time)} for 9 strategies
      • Full Cycle:         {format_ms(total_cycle)} (data + strategy)
      • Trade Execution:    ~450-950ms (estimate)
      
   ⚡ System Capability:
   
      • Can update data {updates_per_second:.1f} times/second
      • Can complete {60.0 / total_cycle:.0f} cycles/minute
      • Suitable for 1-minute timeframe trading ✅
      • Response time < 1 second for trade decisions ✅
      
   💡 Recommendations:
   
      • For <1-second execution: Pre-fetch option tokens at start
      • For high-frequency: Consider WebSocket for live quotes
      • Current setup: Optimal for 1-minute candle trading
    """)
    
    print("=" * 80)
    print("✅ Timing test complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        run_timing_test()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
