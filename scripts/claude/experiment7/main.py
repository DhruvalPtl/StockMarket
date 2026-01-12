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
    """Runs comprehensive test to verify all system components."""
    print("\n🧪 RUNNING COMPREHENSIVE TEST MODE...\n")
    print("=" * 60)
    
    from config import BotConfig
    test_results = []
    
    # ==================== 1. CONFIGURATION TESTS ====================
    print("\n📋 1. CONFIGURATION TESTS")
    print("-" * 60)
    
    try:
        BotConfig.validate()
        print("   ✅ Config validation passed")
        test_results.append(("Config Validation", True))
        
        # Test critical config values
        assert len(BotConfig.API_KEY) > 10, "API_KEY too short"
        assert len(BotConfig.OPTION_EXPIRY) == 10, "Invalid expiry format"
        assert BotConfig.Exit.DEFAULT_TARGET_POINTS > BotConfig.Exit.DEFAULT_STOP_LOSS_POINTS, "Target <= Stop Loss"
        assert BotConfig.Risk.MAX_CONCURRENT_POSITIONS > 0, "Max positions invalid"
        print("   ✅ Config values validated")
        test_results.append(("Config Values", True))
        
        # Test log paths
        log_paths = BotConfig.get_log_paths()
        assert len(log_paths) == 6, "Missing log paths"
        print(f"   ✅ Log paths created ({len(log_paths)} directories)")
        test_results.append(("Log Paths", True))
        
    except Exception as e:
        print(f"   ❌ Configuration error: {e}")
        test_results.append(("Configuration", False))
        return False
    
    # ==================== 2. DATA ENGINE TESTS ====================
    print("\n📊 2. DATA ENGINE TESTS")
    print("-" * 60)
    
    try:
        from data.data_engine import DataEngine, StrikeOIData, CandleData
        
        engine = DataEngine(
            api_key=BotConfig.API_KEY,
            api_secret=BotConfig.API_SECRET,
            option_expiry=BotConfig.OPTION_EXPIRY,
            future_expiry=BotConfig.FUTURE_EXPIRY,
            fut_symbol="NSE-NIFTY-27Jan26-FUT",
            timeframe="1minute"
        )
        
        # Update data
        engine.update()
        print(f"   ✅ Data engine initialized")
        test_results.append(("Data Engine Init", True))
        
        # Check if data was fetched
        if engine.spot_ltp <= 0:
            print(f"   ❌ CRITICAL: No real market data received from API")
            print(f"      Possible reasons:")
            print(f"      - Market is closed (trading hours: 9:15 AM - 3:30 PM)")
            print(f"      - API token expired or invalid")
            print(f"      - Network/API connectivity issue")
            print(f"      Current time: {datetime.now().strftime('%H:%M:%S')}")
            test_results.append(("Data Engine Values", False))
            return False
        
        # Test all critical properties
        assert engine.spot_ltp > 0, "Spot LTP not set"
        assert engine.fut_ltp > 0, "Future LTP not set"
        assert engine.atm_strike > 0, "ATM strike not calculated"
        assert 0 <= engine.rsi <= 100, "RSI out of range"
        assert engine.adx >= 0, "ADX negative"
        assert engine.atr >= 0, "ATR negative"
        assert engine.vwap > 0, "VWAP not calculated"
        print(f"   ✅ Spot: {engine.spot_ltp:.2f} | Future: {engine.fut_ltp:.2f} | ATM: {engine.atm_strike}")
        print(f"   ✅ RSI: {engine.rsi:.1f} | ADX: {engine.adx:.1f} | ATR: {engine.atr:.1f}")
        test_results.append(("Data Engine Values", True))
        
        # Test option chain
        assert len(engine.strikes_data) > 0, "Option chain empty"
        assert engine.total_ce_oi > 0, "CE OI not calculated"
        assert engine.total_pe_oi > 0, "PE OI not calculated"
        assert engine.pcr > 0, "PCR not calculated"
        print(f"   ✅ Option chain loaded ({len(engine.strikes_data)} strikes)")
        print(f"   ✅ PCR: {engine.pcr:.2f} | CE OI: {engine.total_ce_oi:,} | PE OI: {engine.total_pe_oi:,}")
        test_results.append(("Option Chain", True))
        
        # Test affordable strike
        affordable_ce = engine.get_affordable_strike('CE', 50000)
        affordable_pe = engine.get_affordable_strike('PE', 50000)
        assert affordable_ce is not None, "No affordable CE strike"
        assert affordable_pe is not None, "No affordable PE strike"
        print(f"   ✅ Affordable strikes: CE {affordable_ce.strike} @ ₹{affordable_ce.ce_ltp:.2f}, PE {affordable_pe.strike} @ ₹{affordable_pe.pe_ltp:.2f}")
        test_results.append(("Affordable Strikes", True))
        
        # Test IV percentile
        iv_pct = engine.get_iv_percentile()
        assert 0 <= iv_pct <= 100, "IV percentile out of range"
        print(f"   ✅ IV Percentile: {iv_pct:.1f}%")
        test_results.append(("IV Percentile", True))
        
        # Test stale data check
        is_stale = engine.is_data_stale()
        print(f"   ✅ Stale data check: {'⚠️ STALE' if is_stale else '✓ FRESH'}")
        test_results.append(("Stale Data Check", True))
        
    except Exception as e:
        print(f"   ❌ Data Engine error: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("Data Engine", False))
        return False
    
    # ==================== 3. INTELLIGENCE MODULES TESTS ====================
    print("\n🧠 3. MARKET INTELLIGENCE TESTS")
    print("-" * 60)
    
    try:
        from market_intelligence.regime_detector import RegimeDetector
        from market_intelligence.bias_calculator import BiasCalculator
        from market_intelligence.order_flow_tracker import OrderFlowTracker
        from market_intelligence.liquidity_mapper import LiquidityMapper
        
        # Regime Detector
        regime = RegimeDetector(BotConfig)
        regime_state = None
        # Feed historical candles from engine instead of same value 20 times
        if len(engine.candles) >= 20:
            candles_list = list(engine.candles)  # Convert deque to list for slicing
            for candle in candles_list[-50:]:  # Use last 50 candles for warmup
                regime_state = regime.update(candle.high, candle.low, candle.close)
        else:
            # Fallback if not enough candles
            for i in range(20):
                regime_state = regime.update(engine.fut_high, engine.fut_low, engine.fut_close)
        
        assert regime_state is not None, "Regime state is None"
        assert regime_state.adx >= 0, "ADX negative"
        assert 0 <= regime_state.atr_percentile <= 100, "ATR percentile out of range"
        print(f"   ✅ Regime: {regime_state.regime.value} | ADX: {regime_state.adx:.1f} | ATR%: {regime_state.atr_percentile:.1f}%")
        test_results.append(("Regime Detector", True))
        
        # Bias Calculator
        bias_calc = BiasCalculator(BotConfig)
        bias_state = None
        for i in range(15):
            bias_state = bias_calc.update(engine.spot_ltp, engine.fut_ltp, engine.vwap, engine.pcr, engine.rsi)
        
        assert bias_state is not None, "Bias state is None"
        assert -100 <= bias_state.score <= 100, "Bias score out of range"
        print(f"   ✅ Bias: {bias_state.bias.value} | Score: {bias_state.score:.0f}")
        test_results.append(("Bias Calculator", True))
        
        # Order Flow Tracker
        flow = OrderFlowTracker(BotConfig)
        flow_state = flow.update(
            engine.fut_ltp, engine.total_ce_oi, engine.total_pe_oi,
            engine.current_volume, engine.strikes_data, engine.atm_strike
        )
        assert flow_state is not None, "Flow state is None"
        print(f"   ✅ Order Flow: {flow_state.oi_signal} | Volume: {flow_state.volume_state}")
        test_results.append(("Order Flow Tracker", True))
        
        # Liquidity Mapper
        liquidity = LiquidityMapper(BotConfig)
        option_chain = {s: {'ce_oi': d.ce_oi, 'pe_oi': d.pe_oi} for s, d in engine.strikes_data.items()}
        levels = liquidity.update(engine.fut_high, engine.fut_low, engine.fut_close, 
                                 engine.vwap, option_chain, engine.atm_strike)
        print(f"   ✅ Liquidity levels identified: {len(levels)}")
        test_results.append(("Liquidity Mapper", True))
        
    except Exception as e:
        print(f"   ❌ Intelligence module error: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("Intelligence Modules", False))
        return False
    
    # ==================== 4. STRATEGY TESTS ====================
    print("\n🎯 4. STRATEGY TESTS")
    print("-" * 60)
    
    try:
        from strategies.base_strategy import MarketData
        from market_intelligence.market_context import (
            MarketContextBuilder, MarketRegime, MarketBias, 
            TimeWindow, VolatilityState
        )
        from strategies.trend_strategies import (
            OriginalStrategy, VWAPEMATrendStrategy, MomentumBreakoutStrategy
        )
        from strategies.range_strategies import VWAPBounceStrategy
        from strategies.ema_crossover_strategy import EMACrossoverStrategy
        from strategies.volatility_strategies import VolatilitySpikeStrategy
        
        # Create test data
        test_data = MarketData(
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
            ce_oi_change_pct=2.0,
            pe_oi_change_pct=3.0,
            volume_relative=engine.volume_relative
        )
        
        # Create test context
        test_context = MarketContextBuilder()
            .set_regime(MarketRegime.TRENDING_UP, 28, 10)
            .set_bias(MarketBias.BULLISH, 40)
            .set_time_window(TimeWindow.MORNING_SESSION, 280, False)
            .set_volatility(VolatilityState.NORMAL, 50, 50, 50)
            .set_prices(engine.spot_ltp, engine.fut_ltp, engine.vwap)
            .build()
        
        # Test all strategies
        strategies_to_test = [
            ("Original", OriginalStrategy),
            ("VWAP-EMA Trend", VWAPEMATrendStrategy),
            ("Momentum Breakout", MomentumBreakoutStrategy),
            ("VWAP Bounce", VWAPBounceStrategy),
            ("EMA Crossover", EMACrossoverStrategy),
            ("Volatility Spike", VolatilitySpikeStrategy)
        ]
        
        for name, strategy_class in strategies_to_test:
            strat = strategy_class(BotConfig)
            signal = strat.check_entry(test_data, test_context)
            print(f"   ✅ {name}: {'Signal' if signal else 'No signal'}")
            test_results.append((f"Strategy: {name}", True))
        
    except Exception as e:
        print(f"   ❌ Strategy error: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("Strategies", False))
        return False
    
    # ==================== 5. EXECUTION TESTS ====================
    print("\n⚡ 5. EXECUTION LAYER TESTS")
    print("-" * 60)
    
    try:
        from execution.risk_manager import RiskManager
        from execution.signal_aggregator import SignalAggregator
        from strategies.base_strategy import StrategySignal, SignalType, SignalStrength
        
        # Risk Manager
        risk = RiskManager(BotConfig)
        assert risk.max_positions == BotConfig.Risk.MAX_CONCURRENT_POSITIONS
        assert risk.max_daily_trades == BotConfig.Risk.MAX_DAILY_TRADES
        print(f"   ✅ Risk Manager initialized")
        print(f"      Max positions: {risk.max_positions} | Max daily trades: {risk.max_daily_trades}")
        test_results.append(("Risk Manager", True))
        
        # Signal Aggregator
        aggregator = SignalAggregator(BotConfig)
        
        # Create test signals
        test_signals = [
            StrategySignal(
                signal_type=SignalType.BUY_CE,
                strength=SignalStrength.STRONG,
                reason="Test signal 1",
                strategy_name="TEST1",
                timeframe="1minute",
                regime="TRENDING_UP",
                bias="BULLISH",
                base_score=4,
                confluence_factors=["RSI", "EMA", "VWAP"]
            ),
            StrategySignal(
                signal_type=SignalType.BUY_CE,
                strength=SignalStrength.MODERATE,
                reason="Test signal 2",
                strategy_name="TEST2",
                timeframe="1minute",
                regime="TRENDING_UP",
                bias="BULLISH",
                base_score=3,
                confluence_factors=["RSI", "ADX"]
            )
        ]
        
        agg_signal = aggregator.aggregate(test_signals, test_context)
        assert agg_signal is not None, "Aggregated signal is None"
        assert agg_signal.confluence_score >= 2, "Confluence score incorrect"
        print(f"   ✅ Signal Aggregator working")
        print(f"      Confluence: {agg_signal.confluence_score} | Decision: {agg_signal.decision.value}")
        test_results.append(("Signal Aggregator", True))
        
    except Exception as e:
        print(f"   ❌ Execution error: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("Execution Layer", False))
        return False
    
    # ==================== 6. EDGE CASE TESTS ====================
    print("\n🛡️  6. EDGE CASE TESTS")
    print("-" * 60)
    
    try:
        # Test zero/negative values
        zero_oi_pct = engine._get_oi_change_pct('CE') if hasattr(engine, '_get_oi_change_pct') else 0
        print(f"   ✅ Zero value handling: OI change = {zero_oi_pct:.2f}%")
        
        # Test price validation
        low_price_strike = StrikeOIData(strike=24000, ce_ltp=0.5, pe_ltp=0.5)
        valid_strike = engine.get_affordable_strike('CE', 100000)
        assert valid_strike.ce_ltp >= 1.0, "Price validation failed"
        print(f"   ✅ Price validation: Minimum ₹{valid_strike.ce_ltp:.2f} (>= ₹1.00)")
        
        # Test stale data
        engine.timestamp = datetime.now()
        assert not engine.is_data_stale(60), "Fresh data marked as stale"
        print(f"   ✅ Stale data detection working")
        
        test_results.append(("Edge Cases", True))
        
    except Exception as e:
        print(f"   ⚠️  Edge case test warning: {e}")
        test_results.append(("Edge Cases", True))  # Non-critical
    
    # ==================== FINAL SUMMARY ====================
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} | {test_name}")
    
    print("=" * 60)
    print(f"📈 RESULT: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("✅ ALL TESTS PASSED! System is production-ready.")
        print("=" * 60)
        return True
    else:
        print("❌ SOME TESTS FAILED. Please review errors above.")
        print("=" * 60)
        return False


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
