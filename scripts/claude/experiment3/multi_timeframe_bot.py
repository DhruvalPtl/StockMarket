"""
MULTI-TIMEFRAME BOT ORCHESTRATOR
Runs multiple bot instances (one per timeframe) simultaneously
Each bot instance runs all 4 strategies independently
"""

import time
from datetime import datetime
from config import BotConfig, get_timeframe_display_name
from timeframe_manager import TimeframeManager
from enhanced_logger import GrowwLogger, MultiStrategyLogger
from strategies import StrategyA, StrategyB, StrategyC
from multi_strategy_bot import OriginalStrategy, StrategyRunner, OriginalStrategyRunner, StrategyConfig


class TimeframeBotInstance:
    """
    Single bot instance for one timeframe
    Runs all strategies for that specific timeframe
    """
    
    def __init__(self, timeframe, engine, config, capital):
        """
        Initialize bot instance for specific timeframe
        
        Args:
            timeframe: Timeframe string (e.g., "1minute")
            engine: GrowwDataEngine for this timeframe
            config: StrategyConfig object
            capital: Capital per strategy
        """
        self.timeframe = timeframe
        self.timeframe_display = get_timeframe_display_name(timeframe)
        self.engine = engine
        self.config = config
        self.capital = capital
        
        # Initialize all strategies for this timeframe
        self.strategies = []
        
        # 1. Original Strategy
        original_strat = OriginalStrategy(config)
        original_runner = OriginalStrategyRunner(
            f"ORIGINAL_{self.timeframe_display}",
            original_strat,
            engine,
            config,
            capital
        )
        self.strategies.append(original_runner)
        
        # 2. Strategy A
        strategy_a = StrategyA(config)
        runner_a = StrategyRunner(
            f"STRATEGY_A_{self.timeframe_display}",
            strategy_a,
            engine,
            config,
            capital
        )
        self.strategies.append(runner_a)
        
        # 3. Strategy B
        strategy_b = StrategyB(config)
        runner_b = StrategyRunner(
            f"STRATEGY_B_{self.timeframe_display}",
            strategy_b,
            engine,
            config,
            capital
        )
        self.strategies.append(runner_b)
        
        # 4. Strategy C
        strategy_c = StrategyC(config)
        runner_c = StrategyRunner(
            f"STRATEGY_C_{self.timeframe_display}",
            strategy_c,
            engine,
            config,
            capital
        )
        self.strategies.append(runner_c)
        
        print(f"✅ {self.timeframe_display} bot initialized with {len(self.strategies)} strategies")
    
    def process_tick(self, now, no_new_entry_time, force_exit_time):
        """
        Process one market tick for this timeframe
        
        Args:
            now: Current datetime
            no_new_entry_time: Time to stop new entries
            force_exit_time: Time to force exit all positions
        """
        # Force exit all positions at 15:25
        if now >= force_exit_time:
            for strategy in self.strategies:
                if strategy.active_position:
                    current_price = strategy.get_current_option_price()
                    pnl = (current_price - strategy.active_position['entry_price']) * strategy.lot_size
                    strategy.exit_position(current_price, pnl, "EOD_EXIT")
            return
        
        # Process each strategy independently
        for strategy in self.strategies:
            # No position - look for entry
            if not strategy.active_position:
                # No new entries after 15:20
                if now >= no_new_entry_time:
                    continue
                
                signal = strategy.check_entry()
                
                if signal:
                    strategy.place_order(signal)
                else:
                    # Log scanning
                    strategy.logger.log_tick(
                        self.engine,
                        "SCANNING",
                        strategy.daily_pnl,
                        "Waiting for entry"
                    )
            
            # Position active - manage it
            else:
                strategy.manage_position()
                
                if strategy.active_position:
                    unrealized_pnl = strategy.get_unrealized_pnl()
                    current_price = strategy.get_current_option_price()
                    
                    strategy.logger.log_tick(
                        self.engine,
                        f"IN_POSITION_{strategy.active_position['type']}",
                        unrealized_pnl,
                        f"Monitoring @ Rs.{current_price:.2f}"
                    )
    
    def get_summary(self):
        """Get summary of all strategies in this timeframe"""
        summary = {
            'timeframe': self.timeframe_display,
            'strategies': []
        }
        
        for strategy in self.strategies:
            pnl = strategy.capital - strategy.initial_capital
            summary['strategies'].append({
                'name': strategy.strategy_name,
                'active': strategy.active_position is not None,
                'pnl': pnl,
                'trades': len(strategy.trades_today)
            })
        
        return summary
    
    def close_all_positions(self, reason="MANUAL_EXIT"):
        """Close all open positions"""
        for strategy in self.strategies:
            if strategy.active_position:
                current_price = strategy.get_current_option_price()
                pnl = (current_price - strategy.active_position['entry_price']) * strategy.lot_size
                strategy.exit_position(current_price, pnl, reason)


class MultiTimeframeOrchestrator:
    """
    Main orchestrator that manages all timeframe bot instances
    """
    
    def __init__(self):
        """Initialize the multi-timeframe orchestrator"""
        print("\n" + "="*80)
        print("🚀 MULTI-TIMEFRAME NIFTY OPTIONS BOT v4.0")
        print("="*80)
        
        # Validate configuration
        BotConfig.validate()
        BotConfig.print_config()
        
        # Initialize timeframe manager
        fut_symbol = f"NSE-NIFTY-{self._format_expiry_symbol(BotConfig.FUTURE_EXPIRY)}-FUT"
        self.tf_manager = TimeframeManager(
            api_key=BotConfig.API_KEY,
            api_secret=BotConfig.API_SECRET,
            expiry_date=BotConfig.OPTION_EXPIRY,
            fut_symbol=fut_symbol,
            timeframes=BotConfig.TIMEFRAMES
        )
        
        # Initialize strategy config
        config = StrategyConfig()
        config.rsi_oversold = BotConfig.RSI_OVERSOLD
        config.rsi_overbought = BotConfig.RSI_OVERBOUGHT
        config.rsi_momentum_low = BotConfig.RSI_MOMENTUM_LOW
        config.rsi_momentum_high = BotConfig.RSI_MOMENTUM_HIGH
        config.rsi_momentum_low_bear = BotConfig.RSI_MOMENTUM_LOW_BEAR
        config.rsi_momentum_high_bear = BotConfig.RSI_MOMENTUM_HIGH_BEAR
        config.min_candle_body = BotConfig.MIN_CANDLE_BODY
        config.target_points = BotConfig.TARGET_POINTS
        config.stop_loss_points = BotConfig.STOP_LOSS_POINTS
        config.trailing_stop_activation = BotConfig.TRAILING_STOP_ACTIVATION
        config.trailing_stop_distance = BotConfig.TRAILING_STOP_DISTANCE
        
        # Initialize bot instances for each timeframe
        self.bot_instances = {}
        print("\n" + "="*80)
        print("🤖 INITIALIZING BOT INSTANCES")
        print("="*80 + "\n")
        
        for timeframe in BotConfig.TIMEFRAMES:
            engine = self.tf_manager.get_engine(timeframe)
            bot = TimeframeBotInstance(
                timeframe=timeframe,
                engine=engine,
                config=config,
                capital=BotConfig.CAPITAL_PER_STRATEGY
            )
            self.bot_instances[timeframe] = bot
        
        # Multi-strategy logger
        self.multi_logger = MultiStrategyLogger()
        
        print("\n" + "="*80)
        print(f"✅ ORCHESTRATOR READY")
        print(f"📊 Running {len(self.bot_instances)} timeframes × 4 strategies = {len(self.bot_instances) * 4} tests")
        print("="*80 + "\n")
    
    def _format_expiry_symbol(self, expiry_date):
        """Convert YYYY-MM-DD to 30Dec25 format"""
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        return dt.strftime("%d%b%y")
    
    def run(self):
        """Main trading loop - runs all timeframes simultaneously"""
        print("🤖 Multi-Timeframe Bot is now LIVE (Paper Trading)\n")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                
                # Market hours check
                now = datetime.now()
                market_start = now.replace(
                    hour=BotConfig.MARKET_OPEN_HOUR,
                    minute=BotConfig.MARKET_OPEN_MINUTE,
                    second=0,
                    microsecond=0
                )
                market_end = now.replace(
                    hour=BotConfig.MARKET_CLOSE_HOUR,
                    minute=BotConfig.MARKET_CLOSE_MINUTE,
                    second=0,
                    microsecond=0
                )
                
                if not (market_start <= now <= market_end):
                    if iteration % 12 == 0:
                        print(f"⏸️ Market closed. Time: {now.strftime('%H:%M:%S')}")
                    time.sleep(5)
                    continue
                
                # No new entries after 15:20
                no_new_entry_time = now.replace(
                    hour=BotConfig.NO_NEW_ENTRY_HOUR,
                    minute=BotConfig.NO_NEW_ENTRY_MINUTE,
                    second=0
                )
                force_exit_time = now.replace(
                    hour=BotConfig.FORCE_EXIT_HOUR,
                    minute=BotConfig.FORCE_EXIT_MINUTE,
                    second=0
                )
                
                # Update all timeframe engines
                self.tf_manager.update_all()
                
                # Process each timeframe bot
                for timeframe, bot in self.bot_instances.items():
                    engine = self.tf_manager.get_engine(timeframe)
                    health = engine.get_health_status()
                    
                    # Skip if data quality is poor (after warmup period)
                    if health['data_quality'] == 'POOR' and iteration > 10:
                        continue
                    
                    # Process this timeframe
                    bot.process_tick(now, no_new_entry_time, force_exit_time)
                
                # Print consolidated status every 30 seconds
                if iteration % 6 == 0:
                    self._print_status()
                
                # Wait
                time.sleep(5)
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Bot stopped by user")
            
            # Close all open positions across all timeframes
            for timeframe, bot in self.bot_instances.items():
                tf_display = get_timeframe_display_name(timeframe)
                print(f"⚠️ Closing {tf_display} positions...")
                bot.close_all_positions("MANUAL_EXIT")
        
        except Exception as e:
            print(f"\n❌ Critical Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self._print_final_results()
    
    def _print_status(self):
        """Print consolidated status of all timeframes and strategies"""
        print(f"\n{'='*120}")
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'-'*120}")
        
        # Print header
        print(f"{'Timeframe':<10} | {'Strategy':<20} | {'Status':<12} | {'PnL':>12} | {'Trades':>8}")
        print(f"{'-'*120}")
        
        for timeframe in BotConfig.TIMEFRAMES:
            bot = self.bot_instances[timeframe]
            tf_display = get_timeframe_display_name(timeframe)
            
            for idx, strategy in enumerate(bot.strategies):
                status = "IN TRADE" if strategy.active_position else "SCANNING"
                pnl = strategy.daily_pnl + (strategy.get_unrealized_pnl() if strategy.active_position else 0)
                
                # Only print timeframe on first strategy row
                tf_col = tf_display if idx == 0 else ""
                
                # Extract just strategy name (remove timeframe suffix)
                strategy_name = strategy.strategy_name.replace(f"_{tf_display}", "")
                
                print(f"{tf_col:<10} | {strategy_name:<20} | {status:<12} | Rs.{pnl:>9,.2f} | {len(strategy.trades_today):>8}")
        
        print(f"{'='*120}\n")
    
    def _print_final_results(self):
        """Print final comparison and save summary"""
        print("\n\n")
        
        results = []
        
        for timeframe in BotConfig.TIMEFRAMES:
            bot = self.bot_instances[timeframe]
            
            for strategy in bot.strategies:
                # Print individual summary
                strategy.logger.print_session_end(
                    strategy.initial_capital,
                    strategy.capital,
                    strategy.trades_today
                )
                
                # Log to multi-strategy summary
                self.multi_logger.log_strategy_summary(
                    strategy.strategy_name,
                    strategy.initial_capital,
                    strategy.capital,
                    strategy.trades_today
                )
                
                # Collect for comparison
                pnl = strategy.capital - strategy.initial_capital
                pnl_pct = (pnl / strategy.initial_capital) * 100
                win_count = sum(1 for t in strategy.trades_today if t.get('pnl', 0) > 0)
                win_rate = (win_count / len(strategy.trades_today) * 100) if strategy.trades_today else 0
                
                avg_win = sum(t['pnl'] for t in strategy.trades_today if t['pnl'] > 0) / win_count if win_count > 0 else 0
                loss_count = len(strategy.trades_today) - win_count
                avg_loss = sum(t['pnl'] for t in strategy.trades_today if t['pnl'] < 0) / loss_count if loss_count > 0 else 0
                
                if avg_loss != 0 and loss_count > 0:
                    profit_factor = abs((avg_win * win_count) / (abs(avg_loss) * loss_count))
                else:
                    profit_factor = 999.99
                
                results.append({
                    'name': strategy.strategy_name,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'trades': len(strategy.trades_today),
                    'win_rate': win_rate,
                    'profit_factor': profit_factor
                })
        
        # Print comparison
        self.multi_logger.print_final_comparison(results)
