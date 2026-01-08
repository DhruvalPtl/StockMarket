"""
TIMEFRAME MANAGER MODULE
Orchestrates multiple GrowwDataEngine instances (one per timeframe).
Responsible for synchronized updates and health monitoring.
"""

import time
import sys
from typing import Dict

# Import the Engine we just verified
from enhanced_data_pipeline import GrowwDataEngine
from config import BotConfig, get_timeframe_display_name, get_future_symbol

class TimeframeManager:
    """
    Manages a collection of Data Engines.
    Ensures all timeframes are updated and accessible.
    """
    
    def __init__(self):
        self.engines: Dict[str, GrowwDataEngine] = {}
        
        print("\n" + "="*60)
        print("🔧 INITIALIZING TIMEFRAME MANAGER")
        print("="*60)
        
        # 1. Validate Config first
        BotConfig.validate()
        
        # 2. Generate Future Symbol ONCE (Shared across all)
        # Note: We use the future expiry from config
        self.fut_symbol = get_future_symbol(BotConfig.FUTURE_EXPIRY)
        print(f"🎯 Target Future: {self.fut_symbol}")
        
        # 3. Initialize an Engine for each timeframe
        for tf in BotConfig.TIMEFRAMES:
            display_name = get_timeframe_display_name(tf)
            print(f"   ... Booting {display_name} Engine")
            
            try:
                engine = GrowwDataEngine(
                    api_key=BotConfig.API_KEY,
                    api_secret=BotConfig.API_SECRET,
                    expiry_date=BotConfig.OPTION_EXPIRY,
                    fut_symbol=self.fut_symbol,
                    timeframe=tf
                )
                self.engines[tf] = engine
                print(f"   ✅ {display_name} Ready")
                
            except Exception as e:
                print(f"   ❌ FAILED to initialize {display_name}: {e}")
                sys.exit(1) # Critical failure if an engine can't start
                
        print("="*60 + "\n")

    def update_all(self):
        """
        Triggers an update on ALL engines.
        This runs sequentially but fast, relying on individual engine rate limits.
        """
        for tf, engine in self.engines.items():
            try:
                engine.update()
            except Exception as e:
                print(f"⚠️ Error updating {tf}: {e}")

    def get_engine(self, timeframe: str) -> GrowwDataEngine:
        """Retrieves the specific engine for a strategy."""
        if timeframe not in self.engines:
            raise ValueError(f"Requested timeframe '{timeframe}' not initialized!")
        return self.engines[timeframe]

    def register_active_strike_globally(self, strike: int):
        """
        CRITICAL: If Strategy A (1min) buys a strike, 
        Strategies on 5min might also need to know about it.
        This registers the strike across ALL engines to ensure data consistency.
        """
        for engine in self.engines.values():
            engine.register_active_strike(strike)

    def unregister_active_strike_globally(self, strike: int):
        """Stop monitoring a strike across all engines."""
        for engine in self.engines.values():
            engine.unregister_active_strike(strike)

    def print_status_summary(self):
        """
        Prints a 'Cockpit View' dashboard row.
        Shows Spot, RSI, and VWAP for all timeframes side-by-side.
        """
        # Header
        statuses = []
        
        for tf in BotConfig.TIMEFRAMES:
            engine = self.engines[tf]
            name = get_timeframe_display_name(tf)
            
            # Formatted status string
            # Ex: "1min: RSI 55.2 | VWAP 24100"
            if engine.spot_ltp > 0:
                status = f"[{name}] RSI:{int(engine.rsi)} V:{int(engine.vwap)}"
            else:
                status = f"[{name}] ⏳ INIT"
            
            statuses.append(status)
            
        # Print all on one line for cleaner logs
        print("\r" + " | ".join(statuses), end="", flush=True)

# ==================================================================
# SELF-TEST BLOCK
# ==================================================================
if __name__ == "__main__":
    print("\n🔬 RUNNING MANAGER DIAGNOSTIC...\n")
    
    try:
        # Initialize
        mgr = TimeframeManager()
        
        print("⏳ Running update loop for 10 seconds...")
        for i in range(5):
            mgr.update_all()
            mgr.print_status_summary()
            time.sleep(2)
        
        print("\n\n✅ Manager Test Complete.")
        
    except Exception as e:
        print(f"\n❌ MANAGER FAILED: {e}")