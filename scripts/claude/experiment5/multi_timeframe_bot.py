"""
ORCHESTRATOR MODULE
The Commander that initializes the army of bots and runs the main loop.
Manages high-level flow: Market Hours -> Data Update -> Strategy Execution.
"""

import time
import sys
from datetime import datetime
from typing import List

from config import BotConfig
from timeframe_manager import TimeframeManager
from strategies import get_strategy
from multi_strategy_bot import StrategyRunner
from enhanced_logger import MultiStrategyLogger

class MultiTimeframeOrchestrator:
    """
    Main Bot Controller.
    1. Initializes TimeframeManager (Data).
    2. Spawns StrategyRunners for every Timeframe x Strategy combination.
    3. Runs the main event loop.
    """
    
    def __init__(self):
        print("\n" + "="*60)
        print("🚀 STARTING MULTI-TIMEFRAME ORCHESTRATOR")
        print("="*60)
        
        # 1. Initialize Data Layer
        self.tf_manager = TimeframeManager()
        
        # 2. Initialize Logging Layer
        self.summary_logger = MultiStrategyLogger()
        
        # 3. Initialize Strategies
        self.runners: List[StrategyRunner] = []
        self._initialize_runners()
        
        print(f"\n🤖 BOT READY: Managing {len(self.runners)} active strategy instances.")
        print("="*60 + "\n")

    def _initialize_runners(self):
        """Creates a StrategyRunner for every TF x Strategy combo."""
        
        for tf in BotConfig.TIMEFRAMES:
            # Get the shared data engine for this timeframe
            engine = self.tf_manager.get_engine(tf)
            
            for strat_code in BotConfig.STRATEGIES_TO_RUN:
                # 1. Create Strategy Logic Object (e.g., StrategyA)
                # Factory pattern from File 2
                logic = get_strategy(strat_code, BotConfig)
                
                # 2. Create Runner (The Brain)
                # Unique name: "STRATEGY_A (1min)"
                runner_name = f"{strat_code}"
                
                runner = StrategyRunner(
                    strategy_name=runner_name,
                    timeframe=tf,
                    strategy_logic=logic,
                    engine=engine,
                    capital=BotConfig.CAPITAL_PER_STRATEGY
                )
                
                self.runners.append(runner)
                print(f"   + Initialized: {runner_name} [{tf}]")

    def run(self):
        """The Main Infinite Loop."""
        print("\n🟢 BOT IS LIVE (Paper Trading Mode)")
        print("Press Ctrl+C to stop safely.\n")
        
        try:
            iteration = 0
            while True:
                iteration += 1
                now = datetime.now()
                
                # 1. Check Market Hours (Exit loop if day ends)
                if self._is_market_closed(now):
                    print("\n🛑 Market Closed. Stopping Bot.")
                    break
                
                # 2. Update Data (All Timeframes)
                # This uses the optimized non-blocking update from File 4
                self.tf_manager.update_all()
                
                # 3. Process Strategies
                # Only process if market is open or we are force-testing
                if self._is_market_open(now):
                    
                    # Check Force Exit Time
                    if self._is_force_exit_time(now):
                        self._close_all_positions("EOD_FORCE_EXIT")
                        print("🏁 End of Day: All positions closed.")
                        break

                    # Standard Processing
                    for runner in self.runners:
                        # Skip if no new entries allowed and not in position
                        if self._is_no_entry_time(now) and not runner.active_position:
                            continue
                            
                        runner.process_tick()
                
                # 4. Feedback
                if iteration % 30 == 0:  # Every ~30 seconds
                    self._print_heartbeat()
                
                # 5. Speed Control (Low Latency)
                # Fast sleep to keep loop responsive (Fix for Lag Issue #5)
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n⚠️ USER INTERRUPT DETECTED")
        except Exception as e:
            print(f"\n❌ CRITICAL LOOP ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._shutdown()

    def _shutdown(self):
        """Safe shutdown sequence."""
        print("\n" + "="*60)
        print("🔻 SHUTDOWN SEQUENCE INITIATED")
        print("="*60)
        
        # 1. Close any open positions
        self._close_all_positions("SHUTDOWN")
        
        # 2. Generate Final Report
        results = []
        for runner in self.runners:
            stats = runner.get_summary()
            results.append(stats)
            self.summary_logger.log_strategy_result(stats)
            
        # 3. Print Leaderboard
        self.summary_logger.print_final_comparison(results)
        print("\n✅ Bye!")
        sys.exit(0)

    def _close_all_positions(self, reason):
        """Panic button to exit everything."""
        for runner in self.runners:
            if runner.active_position:
                print(f"⚠️ Force Exiting {runner.strategy_name} ({runner.timeframe})...")
                runner.force_exit(reason)

    def _print_heartbeat(self):
        """Prints a dashboard summary every 30s."""
        self.tf_manager.print_status_summary()
        print("") # Newline
        
        # Count active trades
        active = [r for r in self.runners if r.active_position]
        if active:
            print(f"🔥 Active Positions: {len(active)}")
            for r in active:
                p = r.active_position
                print(f"   - {r.strategy_name} ({r.timeframe}): {p['type']} {p['strike']}")
        else:
            print("💤 No Active Positions (Scanning...)")

    # --- Time Helpers ---
    
    def _is_market_open(self, now):
        """Is current time within trading hours?"""
        start = now.replace(hour=BotConfig.MARKET_OPEN_HOUR, minute=BotConfig.MARKET_OPEN_MINUTE, second=0)
        end = now.replace(hour=BotConfig.MARKET_CLOSE_HOUR, minute=BotConfig.MARKET_CLOSE_MINUTE, second=0)
        return start <= now <= end

    def _is_market_closed(self, now):
        """Has the market closed for the day?"""
        end = now.replace(hour=BotConfig.MARKET_CLOSE_HOUR, minute=BotConfig.MARKET_CLOSE_MINUTE, second=0)
        return now > end

    def _is_no_entry_time(self, now):
        """Is it too late to take new trades?"""
        limit = now.replace(hour=BotConfig.NO_NEW_ENTRY_HOUR, minute=BotConfig.NO_NEW_ENTRY_MINUTE, second=0)
        return now >= limit

    def _is_force_exit_time(self, now):
        """Is it time to square off everything?"""
        limit = now.replace(hour=BotConfig.FORCE_EXIT_HOUR, minute=BotConfig.FORCE_EXIT_MINUTE, second=0)
        return now >= limit

# ==================================================================
# SELF-TEST BLOCK
# ==================================================================
if __name__ == "__main__":
    # In file 7, we can't easily self-test without full config, 
    # but we can check instantiation.
    print("Checking Orchestrator Import...")
    print("✅ Class MultiTimeframeOrchestrator loaded.")