"""
TIMEFRAME MANAGER - Manages multiple GrowwDataEngine instances
One engine per timeframe, all sharing the same API connection
"""

from enhanced_data_pipeline import GrowwDataEngine
from config import BotConfig, get_timeframe_display_name
import time


class TimeframeManager:
    """
    Manages multiple data engines, one per timeframe
    Handles API rate limiting across all engines
    """
    
    def __init__(self, api_key, api_secret, expiry_date, fut_symbol, timeframes):
        """
        Initialize data engines for all timeframes
        
        Args:
            api_key: Groww API key
            api_secret: Groww API secret
            expiry_date: Option expiry (YYYY-MM-DD)
            fut_symbol: Futures symbol
            timeframes: List of timeframes ['1minute', '2minute', ...]
        """
        print("\n" + "="*80)
        print("🔧 INITIALIZING TIMEFRAME MANAGER")
        print("="*80)
        
        self.timeframes = timeframes
        self.engines = {}
        
        # Create one engine per timeframe
        for tf in timeframes:
            tf_display = get_timeframe_display_name(tf)
            print(f"\n📊 Setting up {tf_display} engine...")
            
            # Create engine with timeframe-specific logging
            engine = GrowwDataEngine(
                api_key=api_key,
                api_secret=api_secret,
                expiry_date=expiry_date,
                fut_symbol=fut_symbol,
                timeframe=tf  # Pass timeframe to engine
            )
            
            # Disable debug by default
            engine.disable_debug()
            
            self.engines[tf] = engine
            print(f"   ✅ {tf_display} engine ready")
        
        print("\n" + "="*80)
        print(f"✅ ALL {len(self.engines)} ENGINES INITIALIZED")
        print("="*80 + "\n")
        
        # Track last update times for rate limiting
        self.last_update = {tf: 0 for tf in timeframes}
        self.update_interval = 5  # Update every 5 seconds
    
    def update_all(self):
        """
        Update all timeframe engines
        Handles rate limiting to avoid API throttling
        """
        current_time = time.time()
        
        for tf in self.timeframes:
            # Check if enough time has passed since last update
            if current_time - self.last_update[tf] >= self.update_interval:
                try:
                    self.engines[tf].update()
                    self.last_update[tf] = current_time
                except Exception as e:
                    tf_display = get_timeframe_display_name(tf)
                    print(f"\n⚠️ Error updating {tf_display} engine: {e}")
    
    def get_engine(self, timeframe):
        """Get engine for specific timeframe"""
        return self.engines.get(timeframe)
    
    def get_all_engines(self):
        """Get all engines"""
        return self.engines
    
    def get_health_status(self):
        """Get health status of all engines"""
        status = {}
        for tf, engine in self.engines.items():
            tf_display = get_timeframe_display_name(tf)
            status[tf_display] = engine.get_health_status()
        return status
    
    def enable_debug_all(self):
        """Enable debug mode on all engines"""
        for engine in self.engines.values():
            engine.enable_debug()
    
    def disable_debug_all(self):
        """Disable debug mode on all engines"""
        for engine in self.engines.values():
            engine.disable_debug()
    
    def print_status_summary(self):
        """Print status summary of all engines"""
        print("\n" + "="*80)
        print("📊 TIMEFRAME ENGINES STATUS")
        print("="*80)
        
        for tf in self.timeframes:
            engine = self.engines[tf]
            tf_display = get_timeframe_display_name(tf)
            
            status_items = []
            
            # Spot
            if engine.spot_ltp > 0:
                status_items.append(f"Spot: {engine.spot_ltp:.2f}")
            
            # VWAP
            if engine.vwap > 0:
                vwap_diff = engine.fut_ltp - engine.vwap
                status_items.append(f"VWAP: {engine.vwap:.2f} ({vwap_diff:+.1f})")
            
            # RSI
            if engine.rsi_warmup_complete:
                status_items.append(f"RSI: {engine.rsi:.1f}")
            else:
                status_items.append(f"RSI: WARMUP ({engine.candles_processed}/{engine.rsi_periods_needed})")
            
            # ATM
            if engine.atm_strike > 0:
                status_items.append(f"ATM: {engine.atm_strike}")
            
            # Data quality
            health = engine.get_health_status()
            quality_emoji = "✅" if health['data_quality'] == 'GOOD' else "⚠️"
            
            print(f"{quality_emoji} {tf_display:<6} | {' | '.join(status_items)}")
        
        print("="*80 + "\n")
