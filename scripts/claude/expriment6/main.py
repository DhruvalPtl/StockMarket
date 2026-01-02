"""
EXPERIMENT 6 - MAIN ENTRY POINT

Intelligent Multi-Strategy Trading System
Run this file to start the trading bot.

Usage:
    python main.py
    python main.py --test    # Run in test mode
"""

import sys
import os
import time
import argparse
from datetime import datetime

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def print_banner():
    """Prints startup banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   ███████╗██╗  ██╗██████╗ ███████╗██████╗ ██╗███╗   ███╗     ║
    ║   ██╔════╝╚██╗██╔╝██╔══██╗██╔════╝██╔══██╗██║████╗ ████║     ║
    ║   █████╗   ╚███╔╝ ██████╔╝█████╗  ██████╔╝██║██╔████╔██║     ║
    ║   ██╔══╝   ██╔██╗ ██╔═══╝ ██╔══╝  ██╔══██╗██║██║╚██╔╝██║     ║
    ║   ███████╗██╔╝ ██╗██║     ███████╗██║  ██║██║██║ ╚═╝ ██║     ║
    ║   ╚══════╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝     ║
    ║                                                               ║
    ║          NIFTY OPTIONS ALGO BOT - Experiment 6                ║
    ║              Intelligent Multi-Strategy System                ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"    📅 Date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"    ⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 67)


def print_config_summary():
    """Prints configuration summary."""
    from config import BotConfig
    
    print("\n⚙️  CONFIGURATION SUMMARY")
    print("-" * 40)
    print(f"📊 Timeframes:      {len(BotConfig.TIMEFRAMES)} - {BotConfig.TIMEFRAMES}")
    print(f"🧠 Strategies:     {len(BotConfig.STRATEGIES_TO_RUN)}")
    for strat in BotConfig.STRATEGIES_TO_RUN: 
        print(f"                   • {strat}")
    print(f"💰 Capital/Strat:  ₹{BotConfig.Risk.CAPITAL_PER_STRATEGY: ,.0f}")
    print(f"📈 Max Positions:  {BotConfig.Risk.MAX_CONCURRENT_POSITIONS}")
    print(f"🎯 Option Expiry:  {BotConfig.OPTION_EXPIRY}")
    print(f"⚡ Total Bots:     {len(BotConfig.TIMEFRAMES) * len(BotConfig.STRATEGIES_TO_RUN)}")
    print("-" * 40)
    print("📝 MODE:  PAPER TRADING (No real money)")
    print("-" * 40)


def confirm_start() -> bool:
    """Gets user confirmation to start."""
    print("\n" + "=" * 40)
    try:
        response = input("🚀 Ready to launch?  (yes/no): ").strip().lower()
        return response in ['yes', 'y']
    except (KeyboardInterrupt, EOFError):
        return False


def run_test_mode():
    """Runs quick test to verify system."""
    print("\n🧪 RUNNING TEST MODE...\n")
    
    from config import BotConfig
    
    # Test config
    print("1.Testing Configuration...")
    try:
        BotConfig.validate()
        print("   ✅ Configuration valid")
    except Exception as e: 
        print(f"   ❌ Configuration error: {e}")
        return False
    
    # Test data engine
    print("\n2.Testing Data Engine...")
    try:
        from data.data_engine import DataEngine
        engine = DataEngine(
            api_key="test",
            api_secret="test",
            option_expiry=BotConfig.OPTION_EXPIRY,
            future_expiry=BotConfig.FUTURE_EXPIRY,
            fut_symbol="NSE-NIFTY-27Jan26-FUT",
            timeframe="1minute"
        )
        engine.update()
        print(f"   ✅ Data Engine working (Spot: {engine.spot_ltp:.2f})")
    except Exception as e:
        print(f"   ❌ Data Engine error: {e}")
        return False
    
    # Test intelligence modules
    print("\n3.Testing Market Intelligence...")
    try:
        from market_intelligence.regime_detector import RegimeDetector
        from market_intelligence.bias_calculator import BiasCalculator
        
        regime = RegimeDetector(BotConfig)
        bias = BiasCalculator(BotConfig)
        
        # Feed some data
        for _ in range(15):
            regime.update(engine.fut_high or 24000, engine.fut_low or 23950, engine.fut_ltp or 24000)
            bias.update(engine.spot_ltp or 24000, engine.fut_ltp or 24000, 
                       engine.vwap or 24000, engine.pcr or 1.0, engine.rsi or 50)
        
        print(f"   ✅ Regime Detector working")
        print(f"   ✅ Bias Calculator working")
    except Exception as e: 
        print(f"   ❌ Intelligence module error: {e}")
        return False
    
    # Test strategies
    print("\n4.Testing Strategies...")
    try:
        from strategies.trend_strategies import OriginalStrategy
        from strategies.base_strategy import MarketData
        from market_intelligence.market_context import MarketContextBuilder, MarketRegime, MarketBias, TimeWindow, VolatilityState
        
        strat = OriginalStrategy(BotConfig)
        
        data = MarketData(
            timestamp=datetime.now(),
            spot_price=24000, future_price=24050,
            future_open=24000, future_high=24080, future_low=23980, future_close=24050,
            vwap=24020, atm_strike=24000,
            rsi=55, ema_5=24030, ema_13=24010, ema_21=23990, ema_50=23900,
            adx=28, atr=50,
            candle_body=40, candle_range=100, is_green_candle=True,
            pcr=1.1, ce_oi_change_pct=2.0, pe_oi_change_pct=3.0,
            volume_relative=1.5
        )
        
        context = MarketContextBuilder()\
            .set_regime(MarketRegime.TRENDING_UP, 28, 10)\
            .set_bias(MarketBias.BULLISH, 40)\
            .set_time_window(TimeWindow.MORNING_SESSION, 280, False)\
            .set_volatility(VolatilityState.NORMAL, 50, 50, 50)\
            .build()
        
        signal = strat.check_entry(data, context)
        print(f"   ✅ Strategies working")
    except Exception as e: 
        print(f"   ❌ Strategy error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test risk manager
    print("\n5.Testing Risk Manager...")
    try:
        from execution.risk_manager import RiskManager
        risk = RiskManager(BotConfig)
        print(f"   ✅ Risk Manager working")
    except Exception as e: 
        print(f"   ❌ Risk Manager error: {e}")
        return False
    
    print("\n" + "=" * 40)
    print("✅ ALL TESTS PASSED!")
    print("=" * 40)
    return True


def main():
    """Main entry point."""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Experiment 6 Trading Bot')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation')
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Test mode
    if args.test:
        success = run_test_mode()
        sys.exit(0 if success else 1)
    
    # Print config
    print_config_summary()
    
    # Confirm start
    if not args.no_confirm:
        if not confirm_start():
            print("\n❌ Launch cancelled.")
            sys.exit(0)
    
    print("\n⏳ Initializing systems...")
    time.sleep(1)
    
    # Import and run orchestrator
    try:
        from orchestrator import Orchestrator
        
        orchestrator = Orchestrator()
        orchestrator.run()
        
    except KeyboardInterrupt: 
        print("\n\n👋 Interrupted by user.")
    except Exception as e: 
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n✅ System shutdown complete.")
    print(f"📂 Logs saved to: {os.path.join(current_dir, 'logs')}\n")


if __name__ == "__main__":
    main()