"""
RUN BACKTEST V4 - Interactive runner
"""

import os
import sys
import pandas as pd
from datetime import datetime

from config import Config, STRATEGY_INFO, TIMEFRAME_INFO
from backtester import Backtester


def clear_screen():
    """Clear console screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print header"""
    print("\n" + "=" * 60)
    print("🚀 NIFTY OPTIONS SCALPING BOT - BACKTEST V4")
    print("=" * 60)


def select_timeframe() -> str:
    """Interactive timeframe selection"""
    print("\n📊 SELECT TIMEFRAME:")
    print("-" * 40)
    for key, info in TIMEFRAME_INFO.items():
        print(f"{key.replace('min', '')}.{key} - {info['description']}")
    print("-" * 40)
    
    while True:
        choice = input("\nEnter choice (1/3/5):").strip()
        
        if choice == "1":
            return "1min"
        elif choice == "3":
            return "3min"
        elif choice == "5":
            return "5min"
        else:
            print("❌ Invalid choice.Enter 1, 3, or 5")


def select_strategy() -> str:
    """Interactive strategy selection"""
    print("\n🎯 SELECT STRATEGY:")
    print("-" * 40)
    for key, info in STRATEGY_INFO.items():
        print(f"{key}.{info['name']} ({info['type']})")
        print(f"{info['description']}")
    print("-" * 40)
    
    while True:
        choice = input("\nEnter choice (A/B/C):").strip().upper()
        
        if choice in ["A", "B", "C"]:
            return choice
        else:
            print("❌ Invalid choice.Enter A, B, or C")


def show_config(config:Config, timeframe:str, strategy:str):
    """Display configuration"""
    print("\n" + "=" * 60)
    print("⚙️ CONFIGURATION")
    print("=" * 60)
    print(f"   Timeframe:{timeframe}")
    print(f"   Strategy: {strategy} - {STRATEGY_INFO[strategy]['name']}")
    print("-" * 40)
    print(f"   Capital:        ₹{config.capital:,.0f}")
    print(f"   Lot Size: {config.lot_size}")
    print("-" * 40)
    print(f"   Target:          ₹{config.target_points * config.lot_size:.0f} ({config.target_points} pts)")
    print(f"   Stop Loss:      ₹{config.stop_loss_points * config.lot_size:.0f} ({config.stop_loss_points} pts)")
    print(f"   Trailing:        Trigger +{config.trailing_trigger_points} pts, Stop {config.trailing_stop_points} pts")
    print("-" * 40)
    print(f"   Max Daily Loss: ₹{config.max_daily_loss:,.0f}")
    print(f"   Daily Target:   ₹{config.daily_target:,.0f}")
    print("-" * 40)
    print(f"   Market Hours: {config.market_start} - {config.force_exit_time}")
    print(f"   Max Hold Time:{config.max_hold_minutes} minutes")
    print("=" * 60)


def print_results(results:dict):
    """Print backtest results"""
    print("\n" + "=" * 60)
    print("📊 BACKTEST RESULTS")
    print("=" * 60)
    
    if "error" in results:
        print(f"\n❌ Error:{results['error']}")
        return
    
    print("\n💰 CAPITAL")
    print("-" * 40)
    print(f"   Initial:        ₹{results['initial_capital']:>12,.2f}")
    print(f"   Final:           ₹{results['final_capital']:>12,.2f}")
    print(f"   Net P&L:         ₹{results['net_pnl']:>+12,.2f}")
    print(f"   Return:{results['return_pct']:>+12.2f}%")
    
    print("\n📈 TRADES")
    print("-" * 40)
    print(f"   Total Trades:{results['total_trades']:>12}")
    print(f"   Winners:{results['winners']:>12}")
    print(f"   Losers:{results['losers']:>12}")
    print(f"   Win Rate: {results['win_rate']:>11.1f}%")
    
    print("\n💵 PROFIT/LOSS")
    print("-" * 40)
    print(f"   Gross Profit:   ₹{results['gross_profit']:>12,.2f}")
    print(f"   Gross Loss:     ₹{results['gross_loss']:>12,.2f}")
    print(f"   Profit Factor:{results['profit_factor']:>12.2f}")
    print(f"   Avg Win:         ₹{results['avg_win']:>12,.2f}")
    print(f"   Avg Loss:       ₹{results['avg_loss']:>12,.2f}")
    
    print("\n📉 RISK")
    print("-" * 40)
    print(f"   Max Drawdown:{results['max_drawdown']:>11.2f}%")
    
    print("\n" + "=" * 60)


def save_results(results:dict, config:Config, timeframe:str, strategy: str):
    """Save trades and equity curve to CSV"""
    if "error" in results:
        return
    
    os.makedirs(config.output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save trades
    if results.get('trades'):
        trades_file = os.path.join(
            config.output_dir,
            f"trades_{strategy}_{timeframe}_{timestamp}.csv"
        )
        trades_df = pd.DataFrame(results['trades'])
        trades_df.to_csv(trades_file, index=False)
        print(f"\n✅ Trades saved: {trades_file}")
    
    # Save equity curve
    if results.get('equity_curve'):
        equity_file = os.path.join(
            config.output_dir,
            f"equity_{strategy}_{timeframe}_{timestamp}.csv"
        )
        equity_df = pd.DataFrame(results['equity_curve'])
        equity_df.to_csv(equity_file, index=False)
        print(f"✅ Equity curve saved:{equity_file}")


def print_trade_summary(results: dict):
    """Print summary of trades by exit reason"""
    if "error" in results or not results.get('trades'):
        return
    
    print("\n🎯 EXIT REASONS BREAKDOWN")
    print("-" * 40)
    
    exit_reasons = {}
    for trade in results['trades']:
        reason = trade['exit_reason']
        if reason not in exit_reasons:
            exit_reasons[reason] = {'count':0, 'pnl':0}
        exit_reasons[reason]['count'] += 1
        exit_reasons[reason]['pnl'] += trade['pnl_rupees']
    
    for reason, data in sorted(exit_reasons.items()):
        print(f"{reason:20} | Count:{data['count']:3} | PnL:₹{data['pnl']:+,.0f}")
    
    print("-" * 40)


def print_option_stats(results:dict):
    """Print CE vs PE performance"""
    if "error" in results or not results.get('trades'):
        return
    
    print("\n📞 CE vs PE PERFORMANCE")
    print("-" * 40)
    
    ce_trades = [t for t in results['trades'] if t['option_type'] == 'CE']
    pe_trades = [t for t in results['trades'] if t['option_type'] == 'PE']
    
    ce_pnl = sum(t['pnl_rupees'] for t in ce_trades)
    pe_pnl = sum(t['pnl_rupees'] for t in pe_trades)
    
    ce_winners = len([t for t in ce_trades if t['is_winner']])
    pe_winners = len([t for t in pe_trades if t['is_winner']])
    
    print(f"   CE Trades:{len(ce_trades):3} | Winners:{ce_winners:3} | PnL:₹{ce_pnl:+,.0f}")
    print(f"   PE Trades:{len(pe_trades):3} | Winners:{pe_winners:3} | PnL:₹{pe_pnl:+,.0f}")
    
    print("-" * 40)


def confirm_start() -> bool:
    """Ask user to confirm before starting"""
    print("\n" + "-" * 60)
    choice = input("Press ENTER to start backtest or 'q' to quit:").strip().lower()
    return choice != 'q'


def main():
    """Main function"""
    clear_screen()
    print_header()
    
    # Interactive selection
    timeframe = select_timeframe()
    strategy = select_strategy()
    
    # Load config
    config = Config()
    
    # Show configuration
    show_config(config, timeframe, strategy)
    
    # Confirm before starting
    if not confirm_start():
        print("\n👋 Backtest cancelled.Goodbye!")
        return
    
    # Run backtest
    try:
        backtester = Backtester(config, timeframe, strategy)
        results = backtester.run()
        
        # Print results
        print_results(results)
        print_trade_summary(results)
        print_option_stats(results)
        
        # Save results
        save_results(results, config, timeframe, strategy)
        
        # Print cache stats
        stats = backtester.option_fetcher.get_stats()
        print(f"\n📡 CACHE STATS")
        print(f"   Cache Hits:{stats['cache_hits']}")
        print(f"   Cache Misses: {stats['cache_misses']}")
        print(f"   Hit Rate: {stats['hit_rate']}%")
        
        print("\n" + "=" * 60)
        print("✅ BACKTEST COMPLETE!")
        print("=" * 60 + "\n")
        
    except FileNotFoundError as e:
        print(f"\n❌ File not found:{e}")
        print("   Make sure data files exist in the correct path.")
    except Exception as e:
        print(f"\n❌ Error during backtest:{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__": 
    main()