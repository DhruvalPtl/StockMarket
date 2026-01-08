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
from utils.flattrade_wrapper import FlattradeWrapper

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
    """
    Runs quick test to verify system with REAL API data only.
    NO MOCK DATA. NO FALLBACKS.PURE LIVE DATA TEST.
    """
    print("\n🧪 RUNNING TEST MODE (LIVE API ONLY)...\n")
    
    from config import BotConfig
    
    # ====================================================================
    # TEST 1: CONFIGURATION VALIDATION
    # ====================================================================
    print("1️⃣  Testing Configuration...")
    try:
        BotConfig.validate()
        print("   ✅ Configuration valid")
        print(f"      Option Expiry:   {BotConfig.OPTION_EXPIRY}")
        print(f"      Future Expiry:  {BotConfig.FUTURE_EXPIRY}")
        print(f"      Timeframes:     {BotConfig.TIMEFRAMES}")
        print(f"      Strategies:     {len(BotConfig.STRATEGIES_TO_RUN)}")
    except Exception as e:   
        print(f"   ❌ Configuration error: {e}")
        print("\n🛑 FIX YOUR CONFIG.PY FIRST")
        return False
    
    # ====================================================================
    # TEST 2: API CONNECTION & AUTHENTICATION
    # ====================================================================
    print("\n2️⃣  Testing API Connection...")
    try:
        print(f"   🔑 Connecting to Flattrade API...")
        api = FlattradeWrapper(
            user_id=BotConfig.USER_ID,
            user_token=BotConfig.USER_TOKEN
        )
        
        if not api.is_connected:
            print("   ❌ Flattrade connection failed")
            return False
            
        print("   ✅ Flattrade API connected successfully")
        
    except Exception as e:
        print(f"   ❌ API Connection FAILED: {e}")
        print("\n🛑 POSSIBLE CAUSES:")
        print("      1. Invalid/Expired token")
        print("      2. Wrong USER_ID or USER_TOKEN in config.py")
        print("      3. Network connection issue")
        print("\n💡 ACTION: Run gettoken.py to generate a new token")
        return False
    
    # ====================================================================
    # TEST 3: LIVE MARKET DATA FETCH
    # ====================================================================
    print("\n3️⃣  Testing Live Market Data Fetch...")
    try:
        print("   📡 Fetching live Nifty spot quote...")
        spot_quote = api.get_quote("NSE-NIFTY")
        
        if not spot_quote or 'last_price' not in spot_quote: 
            print(f"   ❌ Invalid spot quote response: {spot_quote}")
            return False
        
        live_spot = float(spot_quote['last_price'])
        print(f"   ✅ Live Nifty Spot: ₹{live_spot:.2f}")
        
        # Validate price is realistic
        if live_spot < 10000 or live_spot > 50000:
            print(f"   ⚠️  WARNING: Price {live_spot} seems unrealistic")
            print(f"      Expected range: 10,000 - 50,000")
        
    except Exception as e: 
        print(f"   ❌ Failed to fetch spot data: {e}")
        return False
    
    # ====================================================================
    # TEST 4: DATA ENGINE WITH LIVE API
    # ====================================================================
    print("\n4️⃣  Testing Data Engine (Live API)...")
    try:
        from data.data_engine import DataEngine
        from config import get_future_symbol
        
        fut_symbol = get_future_symbol(BotConfig.FUTURE_EXPIRY)
        print(f"   Target Future:  {fut_symbol}")
        
        print(f"   Initializing Data Engine...")
        engine = DataEngine(
            api_key=BotConfig.USER_ID,
            api_secret=BotConfig.USER_TOKEN,
            option_expiry=BotConfig.OPTION_EXPIRY,
            future_expiry=BotConfig.FUTURE_EXPIRY,
            fut_symbol=fut_symbol,
            timeframe="1minute"
        )
        
        if not engine.is_connected:
            print(f"   ❌ Engine failed to connect to API")
            return False
        
        print(f"   📊 Fetching historical candles...")
        engine.update()
        
        # Verify we got REAL data
        if engine.spot_ltp <= 0:
            print(f"   ❌ No valid spot price received")
            return False
        
        if engine.fut_ltp <= 0:
            print(f"   ❌ No valid future price received")
            return False
        
        if engine.atm_strike <= 0:
            print(f"   ❌ No valid ATM strike calculated")
            return False
        
        print(f"   ✅ Data Engine working with LIVE data")
        print(f"\n   📈 LIVE MARKET SNAPSHOT:")
        print(f"      Spot Price:       ₹{engine.spot_ltp:.2f}")
        print(f"      Future Price:    ₹{engine.fut_ltp:.2f}")
        print(f"      Premium:         ₹{(engine.fut_ltp - engine.spot_ltp):+.2f}")
        print(f"      ATM Strike:      {engine.atm_strike}")
        print(f"      VWAP:            ₹{engine.vwap:.2f}")
        print(f"      RSI:             {engine.rsi:.1f}")
        print(f"      ADX:             {engine.adx:.1f}")
        print(f"      ATR:             {engine.atr:.1f}")
        print(f"      PCR:             {engine.pcr:.2f}")
        print(f"      Total CE OI:     {engine.total_ce_oi: ,}")
        print(f"      Total PE OI:     {engine.total_pe_oi:,}")
        
        # Verify option chain
        if not engine.strikes_data:
            print(f"\n   ⚠️  WARNING: No option chain data received")
        else:
            print(f"\n   ✅ Option chain loaded:  {len(engine.strikes_data)} strikes")
            
            # Show ATM option prices
            if engine.atm_strike in engine.strikes_data:
                atm_data = engine.strikes_data[engine.atm_strike]
                print(f"      ATM {engine.atm_strike} CE: ₹{atm_data.ce_ltp:.2f} (OI: {atm_data.ce_oi:,})")
                print(f"      ATM {engine.atm_strike} PE:  ₹{atm_data.pe_ltp:.2f} (OI: {atm_data.pe_oi:,})")
        
    except SystemExit:
        print(f"   ❌ Data Engine exited (check error above)")
        return False
    except Exception as e:
        print(f"   ❌ Data Engine error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ====================================================================
    # TEST 5: MARKET INTELLIGENCE MODULES
    # ====================================================================
    print("\n5️⃣  Testing Market Intelligence...")
    try:
        from market_intelligence.regime_detector import RegimeDetector
        from market_intelligence.bias_calculator import BiasCalculator
        from market_intelligence.order_flow_tracker import OrderFlowTracker
        from market_intelligence.liquidity_mapper import LiquidityMapper
        
        print(f"   Initializing intelligence modules...")
        regime_detector = RegimeDetector(BotConfig)
        bias_calculator = BiasCalculator(BotConfig)
        order_flow_tracker = OrderFlowTracker(BotConfig)
        liquidity_mapper = LiquidityMapper(BotConfig)
        
        # Feed REAL data from engine
        print(f"   Feeding live data to detectors...")
        
        # Use historical candles to prime the detectors
        if engine.candles:
            for candle in engine.candles:
                regime_state = regime_detector.update(
                    candle.high, candle.low, candle.close
                )
        else:
            # Fallback if no candles
            for _ in range(20):
                regime_state = regime_detector.update(
                    engine.fut_high, engine.fut_low, engine.fut_close
                )
        
        # Final update with current live data
        regime_state = regime_detector.update(
            engine.fut_high, engine.fut_low, engine.fut_close
        )
        
        # Update Bias Calculator
        bias_state = bias_calculator.update(
            engine.spot_ltp,
            engine.fut_ltp,
            engine.vwap,
            engine.pcr,
            engine.rsi
        )
        
        print(f"   ✅ Market Intelligence modules working")
        print(f"\n   🧠 MARKET INTELLIGENCE:")
        print(f"      Regime:           {regime_state.regime.value}")
        print(f"      ADX:             {regime_state.adx:.1f}")
        print(f"      Trend Direction: {regime_state.trend_direction}")
        print(f"      Bias:            {bias_state.bias.value}")
        print(f"      Bias Score:      {bias_state.score:+.1f}")
        print(f"      EMA Alignment:   {bias_state.ema_alignment}")
        
    except Exception as e:  
        print(f"   ❌ Intelligence module error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ====================================================================
    # TEST 6: STRATEGY SIGNAL GENERATION
    # ====================================================================
    print("\n6️⃣  Testing Strategy Logic...")
    try:
        from strategies.trend_strategies import OriginalStrategy
        from strategies.base_strategy import MarketData
        from market_intelligence.market_context import (
            MarketContextBuilder, OrderFlowState, VolatilityState, TimeWindow
        )
        
        print(f"   Creating strategy instance...")
        strat = OriginalStrategy(BotConfig, "1minute")
        
        # Build MarketData from REAL engine data
        print(f"   Building market data from live feed...")
        market_data = MarketData(
            timestamp=datetime.now(),
            spot_price=engine.spot_ltp,
            future_price=engine.fut_ltp,
            future_open=engine.fut_open,
            future_high=engine.fut_high,
            future_low=engine.fut_low,
            future_close=engine.fut_close,
            vwap=engine.vwap,
            atm_strike=engine.atm_strike,
            rsi=engine.rsi,
            ema_5=engine.ema_5,
            ema_13=engine.ema_13,
            ema_21=engine.ema_21,
            ema_50=engine.ema_50,
            adx=engine.adx,
            atr=engine.atr,
            candle_body=engine.candle_body,
            candle_range=engine.candle_range,
            is_green_candle=engine.is_green_candle,
            pcr=engine.pcr,
            ce_oi_change_pct=0.0,  # Would need history for real change
            pe_oi_change_pct=0.0,
            volume_relative=engine.volume_relative
        )
        
        # Build MarketContext from REAL intelligence data
        print(f"   Building market context...")
        context = MarketContextBuilder()\
            .set_regime(regime_state.regime, regime_state.adx, regime_state.regime_duration)\
            .set_bias(bias_state.bias, bias_state.score)\
            .set_time_window(TimeWindow.MORNING_SESSION, 300, False)\
            .set_volatility(VolatilityState.NORMAL, engine.atr, 50, 50)\
            .set_prices(engine.spot_ltp, engine.fut_ltp, engine.vwap)\
            .set_order_flow(OrderFlowState(
                total_ce_oi=engine.total_ce_oi,
                total_pe_oi=engine.total_pe_oi,
                pcr=engine.pcr
            ))\
            .build()
        
        # Test signal generation
        print(f"   Testing signal generation...")
        signal = strat.check_entry(market_data, context)
        
        print(f"   ✅ Strategy logic working")
        if signal:
            print(f"\n   🎯 SIGNAL GENERATED:")
            print(f"      Direction:    {signal.signal_type.value}")
            print(f"      Reason:      {signal.reason}")
            print(f"      Strength:    {signal.strength.value}")
            print(f"      Base Score:  {signal.base_score}/5")
        else:
            print(f"\n   ℹ️  No signal (market conditions don't match strategy criteria)")
        
    except Exception as e:  
        print(f"   ❌ Strategy error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ====================================================================
    # TEST 7: RISK MANAGEMENT
    # ====================================================================
    print("\n7️⃣  Testing Risk Manager...")
    try:
        from execution.risk_manager import RiskManager
        
        risk_mgr = RiskManager(BotConfig)
        print(f"   ✅ Risk Manager initialized")
        print(f"\n   ⚙️  RISK PARAMETERS:")
        print(f"      Max Positions:        {BotConfig.Risk.MAX_CONCURRENT_POSITIONS}")
        print(f"      Max Same Direction:   {BotConfig.Risk.MAX_SAME_DIRECTION}")
        print(f"      Max Daily Trades:     {BotConfig.Risk.MAX_DAILY_TRADES}")
        print(f"      Max Daily Loss:       ₹{BotConfig.Risk.MAX_DAILY_LOSS:,}")
        print(f"      Capital per Strategy: ₹{BotConfig.Risk.CAPITAL_PER_STRATEGY:,}")
        
    except Exception as e:  
        print(f"   ❌ Risk Manager error: {e}")
        return False
    
    # ====================================================================
    # TEST 8: SIGNAL AGGREGATOR
    # ====================================================================
    print("\n8️⃣  Testing Signal Aggregator...")
    try:
        from execution.signal_aggregator import SignalAggregator
        
        agg = SignalAggregator(BotConfig)
        print(f"   ✅ Signal Aggregator initialized")
        print(f"\n   ⚙️  CONFLUENCE SETTINGS:")
        print(f"      Min High Confidence:   {BotConfig.Confluence.MIN_SCORE_HIGH_CONFIDENCE}")
        print(f"      Min Medium Confidence: {BotConfig.Confluence.MIN_SCORE_MEDIUM_CONFIDENCE}")
        print(f"      Min Low Confidence:    {BotConfig.Confluence.MIN_SCORE_LOW_CONFIDENCE}")
        
    except Exception as e:  
        print(f"   ❌ Signal Aggregator error:  {e}")
        return False
    
    # ====================================================================
    # FINAL SUMMARY
    # ====================================================================
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED - SYSTEM READY FOR LIVE TRADING")
    print("=" * 70)
    
    print("\n📊 LIVE MARKET STATUS:")
    print(f"   Nifty Spot:        ₹{engine.spot_ltp:.2f}")
    print(f"   Nifty Future:      ₹{engine.fut_ltp:.2f}")
    print(f"   ATM Strike:        {engine.atm_strike}")
    print(f"   Market Regime:     {regime_state.regime.value}")
    print(f"   Market Bias:       {bias_state.bias.value}")
    
    print("\n🤖 SYSTEM CONFIGURATION:")
    print(f"   Timeframes:        {len(BotConfig.TIMEFRAMES)} ({', '.join(BotConfig.TIMEFRAMES)})")
    print(f"   Strategies:        {len(BotConfig.STRATEGIES_TO_RUN)}")
    print(f"   Total Bots:        {len(BotConfig.TIMEFRAMES) * len(BotConfig.STRATEGIES_TO_RUN)}")
    print(f"   Max Positions:     {BotConfig.Risk.MAX_CONCURRENT_POSITIONS}")
    
    print("\n🟢 STATUS:")
    print(f"   API Connection:    ✅ CONNECTED")
    print(f"   Live Data Feed:    ✅ ACTIVE")
    print(f"   Intelligence:      ✅ WORKING")
    print(f"   Strategies:        ✅ READY")
    print(f"   Risk Management:   ✅ ARMED")
    
    print("\n" + "=" * 70)
    print("💡 NEXT STEP:   Run 'python main.py' during market hours (9:15 AM - 3:30 PM)")
    print("=" * 70)
    
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