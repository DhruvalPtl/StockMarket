"""
Compare OLD (unrealistic) vs NEW (realistic) backtest results
"""

import pandas as pd
import os

def load_old_results():
    """Load results from previous backtest"""
    old_results = {
        "A_1min": {"initial": 10000, "final": 10607.50, "return": 6.1},
        "A_3min": {"initial": 10000, "final": 23548.75, "return": 135.5},
        "A_5min": {"initial": 10000, "final": 40240.00, "return": 302.4},
        "B_1min": {"initial": 10000, "final": 19258.75, "return": 92.6},
        "B_3min": {"initial": 10000, "final": 39272.50, "return": 292.7},
        "B_5min": {"initial": 10000, "final": 33175.00, "return": 231.8},
        "C_1min": {"initial": 10000, "final": 16337.50, "return": 63.4},
        "C_3min": {"initial": 10000, "final": 48197.50, "return": 382.0},
        "C_5min": {"initial": 10000, "final": 49228.75, "return": 392.3},
    }
    return old_results

def print_comparison():
    """Print side-by-side comparison"""
    old = load_old_results()
    
    print("\n" + "="*100)
    print("📊 OLD (UNREALISTIC) vs NEW (REALISTIC) - EXPECTED COMPARISON")
    print("="*100)
    print(f"{'Strategy':<12} | {'OLD Return':<12} | {'NEW Return':<12} | {'Difference':<12} | {'Status'}")
    print("-"*100)
    
    expected_impact = {
        "A_1min": -0.5,  # 50% drop (many trades, high slippage impact)
        "A_3min": -0.40, # 40% drop
        "A_5min": -0.35, # 35% drop (fewer trades, less impact)
        "B_1min": -0.45,
        "B_3min": -0.38,
        "B_5min": -0.38,
        "C_1min": -0.42,
        "C_3min": -0.40,
        "C_5min": -0.38,
    }
    
    for strategy, old_data in old.items():
        old_return = old_data['return']
        impact = expected_impact.get(strategy, -0.4)
        
        # Calculate expected new return
        if old_return > 0:
            new_return = old_return * (1 + impact)
        else:
            new_return = old_return * (1 - impact)
        
        new_final = 10000 * (1 + new_return/100)
        
        diff = new_return - old_return
        
        # Status
        if new_return > 50:
            status = "🟢 Excellent"
        elif new_return > 20:
            status = "🟡 Good"
        elif new_return > 0:
            status = "🟠 Marginal"
        else:
            status = "🔴 Loss"
        
        print(f"{strategy:<12} | {old_return:>10.1f}% | {new_return:>10.1f}% | {diff:>10.1f}% | {status}")
    
    print("-"*100)
    print("\n💡 KEY CHANGES IN REALISTIC VERSION:")
    print("   ✅ Entry/Exit on NEXT candle (no look-ahead)")
    print("   ✅ Slippage: 0.5-1 point per trade")
    print("   ✅ Transaction costs: ₹40-50 per trade")
    print("   ✅ Realistic price execution")
    print("\n📉 EXPECTED IMPACT:")
    print("   • 1-min strategies: 40-50% reduction (more trades = more costs)")
    print("   • 3-min strategies: 35-40% reduction")
    print("   • 5-min strategies: 30-38% reduction (fewer trades = less impact)")
    print("\n🎯 REALISTIC EXPECTATIONS:")
    print("   • 50-150% annual return = EXCELLENT for options")
    print("   • 20-50% annual return = GOOD")
    print("   • 0-20% annual return = ACCEPTABLE")
    print("   • 300%+ annual return = UNREALISTIC (old results)")
    print("="*100)
    
    print("\n📋 WHAT TO CHECK AFTER RUNNING NEW BACKTEST:")
    print("   1. Win rate should drop by 5-10%")
    print("   2. Average win should be similar")
    print("   3. Average loss should be ~₹50 worse")
    print("   4. Total transaction costs visible in results")
    print("   5. Entry/exit timing delays visible in trades CSV")
    print("\n🚀 Run the new backtest with:")
    print("   python run_backtest_v4.py")
    print("\n")

if __name__ == "__main__":
    print_comparison()
