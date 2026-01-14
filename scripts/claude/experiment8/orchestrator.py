"""
ORCHESTRATOR
The Commander that initializes and coordinates all components.

Responsibilities:
1.Initialize all modules (data, intelligence, strategies, execution)
2.Run the main trading loop
3.Coordinate signal aggregation across strategies
4.Handle market hours and shutdown
5.Generate end-of-day reports
"""

import time
import sys
import os
from datetime import datetime, time as dt_time
from typing import Dict, List, Optional
from dataclasses import dataclass

# Add parent to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import BotConfig, get_future_symbol, get_timeframe_display_name

# Data
from data.data_engine import DataEngine

# Market Intelligence
from market_intelligence.market_context import (
    MarketContext, get_current_time_window, TimeWindow
)
from market_intelligence.regime_detector import RegimeDetector
from market_intelligence.bias_calculator import BiasCalculator
from market_intelligence.order_flow_tracker import OrderFlowTracker
from market_intelligence.liquidity_mapper import LiquidityMapper

# Strategies
from strategies.base_strategy import StrategySignal, SignalType
from strategies.trend_strategies import (
    OriginalStrategy, VWAPEMATrendStrategy, MomentumBreakoutStrategy
)
from strategies.range_strategies import VWAPBounceStrategy, RangeMeanReversionStrategy
from strategies.ema_crossover_strategy import EMACrossoverStrategy
from strategies.liquidity_sweep_strategy import LiquiditySweepStrategy, FalseBreakoutStrategy
from strategies.volatility_strategies import VolatilitySpikeStrategy, OpeningRangeBreakoutStrategy
from strategies.order_flow_strategy import OrderFlowStrategy, PCRExtremeStrategy

# Execution
from execution.signal_aggregator import SignalAggregator, AggregatedSignal, TradeDecision
from execution.risk_manager import RiskManager, RiskAction
from execution.strategy_runner import StrategyRunner


# Strategy factory
STRATEGY_CLASSES = {
    "ORIGINAL": OriginalStrategy,
    "VWAP_EMA_TREND": VWAPEMATrendStrategy,
    "VWAP_BOUNCE": VWAPBounceStrategy,
    "MOMENTUM_BREAKOUT":  MomentumBreakoutStrategy,
    "EMA_CROSSOVER": EMACrossoverStrategy,
    "LIQUIDITY_SWEEP":  LiquiditySweepStrategy,
    "VOLATILITY_SPIKE":  VolatilitySpikeStrategy,
    "ORDER_FLOW": OrderFlowStrategy,
    "OPENING_RANGE_BREAKOUT": OpeningRangeBreakoutStrategy,
}


@dataclass
class TimeframeInstance:
    """Holds all components for a single timeframe."""
    timeframe: str
    engine: DataEngine
    regime_detector: RegimeDetector
    bias_calculator: BiasCalculator
    order_flow_tracker:  OrderFlowTracker
    liquidity_mapper: LiquidityMapper
    runners: List[StrategyRunner]


class Orchestrator: 
    """
    Main Trading System Controller.
    
    Architecture:
    - One DataEngine per timeframe
    - One set of Intelligence modules per timeframe
    - Multiple StrategyRunners per timeframe
    - Shared RiskManager and SignalAggregator
    """
    
    def __init__(self):
        print("\n" + "=" * 60)
        print("🚀 EXPERIMENT 8 - FLATTRADE API TRADING SYSTEM")
        print("=" * 60)
        
        self.config = BotConfig
        
        # Validate configuration
        self.config.validate()
        self.config.print_config()
        
        # Setup logging
        self._setup_logging()
        self._setup_csv_logging()
        
        # Generate future symbol
        self.fut_symbol = get_future_symbol(self.config.FUTURE_EXPIRY)
        print(f"🎯 Target Future:  {self.fut_symbol}")
        self._log_and_print(f"Target Future: {self.fut_symbol}")
        
        # Shared components
        self.risk_manager = RiskManager(self.config)
        self.signal_aggregator = SignalAggregator(self.config)
        
        # Timeframe instances
        self.timeframes:  Dict[str, TimeframeInstance] = {}
        
        # All runners (flat list for easy iteration)
        self.all_runners: List[StrategyRunner] = []
        
        # Initialize everything
        self._initialize_timeframes()
        
        # State
        self.is_running = False
        self.iteration = 0
        self.start_time:  Optional[datetime] = None
        self.reset_count = 0
        
        print(f"\n🤖 SYSTEM READY: {len(self.all_runners)} strategy instances")
        print("=" * 60 + "\n")
        self._log_and_print(f"System initialized with {len(self.all_runners)} strategies")
    
    def _setup_logging(self):
        """Setup logging system for live trading."""
        import logging
        
        # Create logs directory if doesn't exist
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f'Live_System_Log_{timestamp}.txt')
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger('Experiment8')
        self.logger.info("=" * 60)
        self.logger.info("EXPERIMENT 8 - SYSTEM LOG INITIALIZED")
        self.logger.info("=" * 60)
        print(f"📝 Logging to: {log_file}")
    
    def _setup_csv_logging(self):
        """Setup CSV logging for trade book and market snapshots."""
        import csv
        
        # Create logs directory (not the log directory with subfolders)
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Trade book CSV
        self.trade_book_path = os.path.join(log_dir, f'Live_Trade_Book_{timestamp}.csv')
        with open(self.trade_book_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Entry_Time', 'Exit_Time', 'Strategy', 'Timeframe', 'Direction',
                'Strike', 'Entry_Price', 'Exit_Price', 'Lots', 'PnL',
                'Exit_Reason', 'Duration_Min', 'Regime', 'Bias', 'Confluence'
            ])
        
        # Market tracker CSV
        self.tracker_path = os.path.join(log_dir, f'Live_Super_Tracker_{timestamp}.csv')
        with open(self.tracker_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Timestamp', 'Spot_LTP', 'Fut_LTP', 'Premium', 'VWAP', 'RSI',
                'ADX', 'ATR', 'PCR', 'Regime', 'Bias', 'Active_Positions', 'Daily_PnL'
            ])
        
        self._log_and_print(f"CSV logging: {self.trade_book_path}", 'INFO')
        self._log_and_print(f"Market tracker: {self.tracker_path}", 'INFO')
    
    def _log_and_print(self, message: str, level: str = 'INFO'):
        """Logs and prints a message."""
        if hasattr(self, 'logger'):
            if level == 'INFO':
                self.logger.info(message)
            elif level == 'WARNING':
                self.logger.warning(message)
            elif level == 'ERROR':
                self.logger.error(message)
        else:
            print(message)
    
    def _check_daily_loss_reset(self) -> bool:
        """Check if max daily loss hit and should reset."""
        if self.risk_manager.daily_stats.net_pnl < -self.risk_manager.max_daily_loss:
            return True
        return False
    
    def _reset_for_new_session(self):
        """Reset system after max daily loss for fresh start."""
        self.reset_count += 1
        
        stats = self.risk_manager.daily_stats
        win_rate = (stats.trades_won / stats.trades_taken * 100) if stats.trades_taken > 0 else 0
        
        # Log the reset
        reset_msg = f"\n{'='*60}\n"
        reset_msg += f"🔄 AUTO-RESET #{self.reset_count} - MAX DAILY LOSS HIT\n"
        reset_msg += f"Previous Loss: ₹{abs(stats.net_pnl):.2f}\n"
        reset_msg += f"Trades Taken: {stats.trades_taken}\n"
        reset_msg += f"Win Rate: {win_rate:.1f}%\n"
        reset_msg += f"Starting Fresh Session with Capital: ₹{self.config.Risk.CAPITAL_PER_STRATEGY:.2f}\n"
        reset_msg += f"{'='*60}\n"
        
        self._log_and_print(reset_msg, 'WARNING')
        
        # Force exit all positions
        self._force_exit_all(f"AUTO_RESET_{self.reset_count}")
        
        # Reset risk manager
        self.risk_manager.reset_daily_stats()
        self.risk_manager.is_halted = False
        self.risk_manager.halt_reason = None
        
        # Reset signal aggregator
        self.signal_aggregator.reset_stats()
        
        # Reset all runners
        for runner in self.all_runners:
            if hasattr(runner, 'reset_stats'):
                runner.reset_stats()
        
        # Wait before resuming
        self._log_and_print("⏳ Waiting 5 seconds before resuming...")
        time.sleep(5)
        self._log_and_print("✅ Fresh session started - ready to trade!")
    
    def _initialize_timeframes(self):
        """Initializes all timeframe instances."""
        print("\n📊 Initializing Timeframes...")
        
        for tf in self.config.TIMEFRAMES:
            display_name = get_timeframe_display_name(tf)
            print(f"\n   [{display_name}] Setting up...")
            
            # 1.Data Engine
            engine = DataEngine(
                user_token=self.config.USER_TOKEN,
                user_id=self.config.USER_ID,
                option_expiry=self.config.OPTION_EXPIRY,
                future_expiry=self.config.FUTURE_EXPIRY,
                fut_symbol=self.fut_symbol,
                timeframe=tf
            )
            
            # 2.Intelligence Modules (one per timeframe)
            regime_detector = RegimeDetector(self.config)
            bias_calculator = BiasCalculator(self.config)
            order_flow_tracker = OrderFlowTracker(self.config)
            liquidity_mapper = LiquidityMapper(self.config)
            
            # 3.Strategy Runners
            runners = []
            for strat_code in self.config.STRATEGIES_TO_RUN: 
                if strat_code not in STRATEGY_CLASSES:
                    print(f"      ⚠️ Unknown strategy: {strat_code}")
                    continue
                
                # Create strategy instance
                strategy_class = STRATEGY_CLASSES[strat_code]
                strategy = strategy_class(self.config, tf)
                
                # Create runner
                runner = StrategyRunner(
                    strategy=strategy,
                    engine=engine,
                    regime_detector=regime_detector,
                    bias_calculator=bias_calculator,
                    order_flow_tracker=order_flow_tracker,
                    liquidity_mapper=liquidity_mapper,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                
                runners.append(runner)
                self.all_runners.append(runner)
                print(f"      ✓ {strat_code}")
            
            # Store timeframe instance
            self.timeframes[tf] = TimeframeInstance(
                timeframe=tf,
                engine=engine,
                regime_detector=regime_detector,
                bias_calculator=bias_calculator,
                order_flow_tracker=order_flow_tracker,
                liquidity_mapper=liquidity_mapper,
                runners=runners
            )
            
            print(f"   [{display_name}] ✅ {len(runners)} strategies ready")
    
    def run(self):
        """Main trading loop."""
        print("\n🟢 STARTING TRADING LOOP")
        print("Press Ctrl+C to stop safely.\n")
        
        self.is_running = True
        self.start_time = datetime.now()
        
        try: 
            while self.is_running:
                self.iteration += 1
                now = datetime.now()
                
                # 1.Check market hours
                if self._is_market_closed(now):
                    print("\n🛑 Market Closed. Stopping...")
                    break
                
                # 2.Check force exit time
                if self._is_force_exit_time(now):
                    print("\n🏁 Force exit time reached.")
                    self._force_exit_all("EOD_FORCE_EXIT")
                    break
                
                # 3.Check for max daily loss and auto-reset
                if self._check_daily_loss_reset():
                    self._log_and_print("🔄 MAX DAILY LOSS HIT - AUTO RESET TRIGGERED")
                    self._reset_for_new_session()
                    continue
                
                # 4.Update all data engines
                self._update_all_engines()
                
                # 5.Process strategies if market open
                if self._is_market_open(now):
                    # Check no-entry time
                    no_new_entries = self._is_no_entry_time(now)
                    
                    # Process each timeframe
                    for tf, instance in self.timeframes.items():
                        self._process_timeframe(instance, no_new_entries)
                
                # 6.Print and log real-time market status (every iteration)
                self._print_live_status()
                
                # 7.Periodic detailed status (every 30 seconds)
                if self.iteration % 30 == 0:
                    self._print_status()
                
                # 8.Loop delay
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n⚠️ USER INTERRUPT")
        except Exception as e: 
            print(f"\n❌ CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._shutdown()
    
    def _update_all_engines(self):
        """Updates data for all timeframes."""
        for tf, instance in self.timeframes.items():
            try:
                instance.engine.update()
            except Exception as e:
                if self.iteration % 10 == 0:
                    print(f"⚠️ [{tf}] Engine update error: {e}")
    
    def _process_timeframe(self, instance: TimeframeInstance, no_new_entries: bool):
        """Processes all strategies for a timeframe."""
        # Skip if engine not ready
        if not instance.engine.is_ready():
            return
        
        # Collect signals from all runners
        signals:  List[StrategySignal] = []
        
        for runner in instance.runners:
            # Skip entry check if in position or no new entries allowed
            if runner.has_position():
                # Just manage existing position
                runner.process_tick()
                continue
            
            if no_new_entries: 
                continue
            
            # Get signal from strategy
            signal = runner.process_tick()
            if signal:
                signals.append(signal)
        
        # If we have signals, aggregate and potentially execute
        if signals:
            self._handle_signals(signals, instance)
    
    def _handle_signals(self, signals: List[StrategySignal], instance: TimeframeInstance):
        """Handles aggregated signals for execution."""
        # Log signal generation
        signal_info = f"Signals received: {len(signals)} from {instance.timeframe}"
        self._log_and_print(signal_info, 'INFO')
        
        # Build context from first runner (they share the same engine)
        runner = instance.runners[0]
        market_data = runner._build_market_data()
        context = runner._build_market_context()
        
        # Aggregate signals
        agg_signal = self.signal_aggregator.aggregate(signals, context)
        
        # Log aggregation result
        agg_info = f"Aggregated: {agg_signal.decision.value} | Confluence: {agg_signal.confluence_score}"
        self._log_and_print(agg_info, 'INFO')
        
        # Check if should execute
        if agg_signal.decision != TradeDecision.EXECUTE:
            skip_msg = f"Trade skipped: {agg_signal.skip_reason}"
            self._log_and_print(skip_msg, 'INFO')
            return
        
        # Find the runner that generated the best signal
        best_runner = None
        for r in instance.runners:
            if r.strategy.STRATEGY_NAME == agg_signal.best_signal.strategy_name:
                best_runner = r
                break
        
        if not best_runner: 
            # Fall back to first matching direction
            for r in instance.runners:
                if not r.has_position():
                    best_runner = r
                    break
        
        if not best_runner: 
            return
        
        # Determine strike
        option_type = 'CE' if agg_signal.direction == SignalType.BUY_CE else 'PE'
        strike_data = instance.engine.get_affordable_strike(
            option_type, 
            self.config.Risk.CAPITAL_PER_STRATEGY * self.config.Risk.MAX_CAPITAL_USAGE_PCT
        )
        
        if not strike_data:
            self._log_and_print("No affordable strike found", 'WARNING')
            return
        
        # Risk check
        risk_decision = self.risk_manager.check_trade(
            agg_signal, 
            strike_data.strike,
            instance.engine.atr
        )
        
        if risk_decision.action == RiskAction.BLOCK:
            block_msg = f"🚫 Trade blocked: {risk_decision.reason}"
            print(block_msg)
            self._log_and_print(block_msg, 'WARNING')
            return
        
        # Print aggregator decision
        self.signal_aggregator.print_decision(agg_signal)
        
        # Get entry price based on option type
        entry_price = strike_data.ce_ltp if option_type == 'CE' else strike_data.pe_ltp
        
        # Log entry attempt
        entry_msg = (
            f"🟢 ENTERING POSITION: {option_type} {strike_data.strike} "
            f"@ ₹{entry_price:.2f} | Strategy: {agg_signal.best_signal.strategy_name}"
        )
        print(entry_msg)
        self._log_and_print(entry_msg, 'INFO')
        
        # Execute through the best runner
        best_runner.enter_position(
            agg_signal.best_signal,
            risk_decision.adjusted_size_multiplier
        )
    
    def _force_exit_all(self, reason: str):
        """Forces exit of all positions."""
        print(f"\n⚠️ Force exiting all positions:  {reason}")
        self._log_and_print(f"Force exiting all positions: {reason}", 'WARNING')
        for runner in self.all_runners: 
            if runner.has_position():
                runner.force_exit(reason)
    
    def _print_live_status(self):
        """Prints and logs real-time market status every second."""
        # Get market data from first engine
        first_tf = list(self.timeframes.keys())[0]
        engine = self.timeframes[first_tf].engine
        
        # Get regime and bias from first timeframe
        instance = self.timeframes[first_tf]
        
        # Build status line
        now = datetime.now()
        status_line = (
            f"[{now.strftime('%H:%M:%S')}] "
            f"Spot: {engine.spot_ltp:.2f} | "
            f"Fut: {engine.fut_ltp:.2f} | "
            f"VWAP: {engine.vwap:.2f} | "
            f"RSI: {engine.rsi:.1f} | "
            f"ADX: {engine.adx:.1f} | "
            f"ATR: {engine.atr:.1f} | "
            f"PCR: {engine.pcr:.2f} | "
            f"Pos: {len([r for r in self.all_runners if r.has_position()])}/{self.config.Risk.MAX_CONCURRENT_POSITIONS} | "
            f"P&L: ₹{self.risk_manager.daily_stats.net_pnl:+,.0f}"
        )
        
        # Print to console
        print(status_line)
        
        # Log to file
        self._log_and_print(status_line, 'INFO')
        
        # Log to CSV (every 60 seconds to avoid huge files)
        if self.iteration % 60 == 0:
            import csv
            try:
                with open(self.tracker_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        now.strftime('%Y-%m-%d %H:%M:%S'),
                        f"{engine.spot_ltp:.2f}",
                        f"{engine.fut_ltp:.2f}",
                        f"{engine.fut_ltp - engine.spot_ltp:.2f}",
                        f"{engine.vwap:.2f}",
                        f"{engine.rsi:.1f}",
                        f"{engine.adx:.1f}",
                        f"{engine.atr:.1f}",
                        f"{engine.pcr:.2f}",
                        "UNKNOWN",  # Regime
                        "UNKNOWN",  # Bias
                        len([r for r in self.all_runners if r.has_position()]),
                        f"{self.risk_manager.daily_stats.net_pnl:.2f}"
                    ])
            except Exception as e:
                self._log_and_print(f"CSV write error: {e}", 'ERROR')
    
    def _print_status(self):
        """Prints periodic status update."""
        # Market context from first engine
        first_tf = list(self.timeframes.keys())[0]
        engine = self.timeframes[first_tf].engine
        
        # Position summary
        active_positions = [r for r in self.all_runners if r.has_position()]
        
        status_block = f"\n{'─'*60}\n"
        status_block += f"📊 STATUS @ {datetime.now().strftime('%H:%M:%S')}\n"
        status_block += f"{'─'*60}\n"
        status_block += f"Spot: {engine.spot_ltp:.2f} | Future: {engine.fut_ltp:.2f} | "
        status_block += f"RSI: {engine.rsi:.1f} | ADX: {engine.adx:.1f}\n"
        status_block += f"VWAP: {engine.vwap:.2f} | PCR: {engine.pcr:.2f} | "
        status_block += f"ATM: {engine.atm_strike}\n"
        
        if active_positions:
            status_block += f"\n🔥 Active Positions: {len(active_positions)}\n"
            for r in active_positions: 
                pos = r.active_position
                status_block += f"   • {r.strategy_name} ({r.timeframe}): "
                status_block += f"{pos['type']} {pos['strike']} @ ₹{pos['entry_price']:.2f}\n"
        else:
            status_block += f"\n💤 No Active Positions (Scanning...)\n"
        
        # Risk summary
        risk_summary = self.risk_manager.get_risk_summary()
        status_block += f"\n📈 Daily:  Trades={risk_summary['trades_today']} | "
        status_block += f"PnL=₹{risk_summary['net_pnl']:+,.2f} | "
        status_block += f"Win%={risk_summary['win_rate']:.0f}%\n"
        status_block += f"{'─'*60}\n"
        
        # Print to console
        print(status_block)
        
        # Log to file
        self._log_and_print(status_block.strip(), 'INFO')
    
    def _shutdown(self):
        """Safe shutdown sequence."""
        print("\n" + "=" * 60)
        print("🔻 SHUTDOWN SEQUENCE")
        print("=" * 60)
        
        # 1.Close all positions
        self._force_exit_all("SHUTDOWN")
        
        # 2.Print final report
        self._print_final_report()
        
        self.is_running = False
        print("\n✅ Shutdown complete. Goodbye!")
    
    def _print_final_report(self):
        """Prints end-of-day performance report."""
        print("\n" + "=" * 60)
        print("📊 FINAL PERFORMANCE REPORT")
        print("=" * 60)
        
        # Collect all strategy summaries
        summaries = []
        for runner in self.all_runners: 
            summary = runner.get_summary()
            if summary['trades']> 0 or summary['signals']> 0:
                summaries.append(summary)
        
        # Sort by PnL
        summaries.sort(key=lambda x: x['daily_pnl'], reverse=True)
        
        # Print header
        print(f"\n{'Strategy':<25} {'TF':<6} {'Trades':>6} {'Win%':>6} {'PnL':>12}")
        print("-" * 60)
        
        total_pnl = 0
        total_trades = 0
        total_wins = 0
        
        for s in summaries: 
            print(f"{s['strategy']:<25} {s['timeframe']:<6} "
                  f"{s['trades']:>6} {s['win_rate']:>5.0f}% "
                  f"₹{s['daily_pnl']:>+10,.2f}")
            total_pnl += s['daily_pnl']
            total_trades += s['trades']
            total_wins += s['wins']
        
        print("-" * 60)
        overall_win_rate = (total_wins / total_trades * 100) if total_trades> 0 else 0
        print(f"{'TOTAL':<25} {'':<6} {total_trades:>6} "
              f"{overall_win_rate:>5.0f}% ₹{total_pnl:>+10,.2f}")
        
        # Risk Manager Stats
        print("\n" + "-" * 60)
        self.risk_manager.print_status()
        
        # Signal Aggregator Stats
        agg_stats = self.signal_aggregator.get_stats()
        print(f"Signal Aggregator:  {agg_stats['executed']} executed, "
              f"{agg_stats['skipped']} skipped "
              f"({agg_stats['execution_rate']:.1f}% execution rate)")
        
        print("=" * 60)
    
    # ==================== TIME HELPERS ====================
    
    def _is_market_open(self, now: datetime) -> bool:
        """Checks if within market hours."""
        market_open = now.replace(
            hour=self.config.TimeWindows.MARKET_OPEN[0],
            minute=self.config.TimeWindows.MARKET_OPEN[1],
            second=0
        )
        market_close = now.replace(
            hour=self.config.TimeWindows.MARKET_CLOSE[0],
            minute=self.config.TimeWindows.MARKET_CLOSE[1],
            second=0
        )
        return market_open <= now <= market_close
    
    def _is_market_closed(self, now: datetime) -> bool:
        """Checks if market has closed for the day."""
        market_close = now.replace(
            hour=self.config.TimeWindows.MARKET_CLOSE[0],
            minute=self.config.TimeWindows.MARKET_CLOSE[1],
            second=0
        )
        return now> market_close
    
    def _is_no_entry_time(self, now: datetime) -> bool:
        """Checks if too late for new entries."""
        no_entry = now.replace(
            hour=self.config.TimeWindows.NO_NEW_ENTRY[0],
            minute=self.config.TimeWindows.NO_NEW_ENTRY[1],
            second=0
        )
        return now>= no_entry
    
    def _is_force_exit_time(self, now: datetime) -> bool:
        """Checks if force exit time reached."""
        force_exit = now.replace(
            hour=self.config.TimeWindows.FORCE_EXIT[0],
            minute=self.config.TimeWindows.FORCE_EXIT[1],
            second=0
        )
        return now>= force_exit


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__": 
    print("\n🔬 Testing Orchestrator Import...\n")
    print("✅ Orchestrator class loaded successfully!")
    print("   - Timeframe initialization")
    print("   - Strategy factory")
    print("   - Signal aggregation")
    print("   - Risk management integration")
    print("   - Main loop structure")