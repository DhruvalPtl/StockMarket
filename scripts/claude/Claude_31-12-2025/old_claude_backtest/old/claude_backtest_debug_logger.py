"""
BACKTEST DEBUG LOGGER
Saves every decision point to CSV for analysis
"""

import pandas as pd
import os
from datetime import datetime


class BacktestDebugLogger:
    """Logs every bot decision to CSV for debugging"""
    
    def __init__(self, output_dir:  str = None):
        if output_dir is None:
            output_dir = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\debug_logs"
        
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = f"{output_dir}\\backtest_debug_{timestamp}.csv"
        
        # All columns we want to track
        self.columns = [
            # Time
            "datetime", "date", "time",
            
            # Price Data
            "spot_close", "fut_close", "vwap",
            
            # Indicators
            "rsi", "ema5", "ema13", "pcr",
            
            # Conditions
            "rsi_ready", "in_market", "in_cooldown",
            
            # Signal Analysis
            "spot_vs_vwap",  # "ABOVE" or "BELOW"
            "ema_crossover",  # "BULLISH", "BEARISH", "NEUTRAL"
            "rsi_zone",  # "BULLISH", "BEARISH", "NEUTRAL"
            "pcr_signal",  # "BULLISH", "BEARISH", "NEUTRAL"
            
            # Signal Counts
            "bullish_signals", "bearish_signals",
            
            # Decisions
            "market_bias",  # "BULLISH", "BEARISH", "NEUTRAL"
            "entry_signal",  # "BUY_CE", "BUY_PE", None
            "entry_blocked_reason",  # Why entry was blocked
            
            # Position
            "has_position", "position_type", "position_strike",
            "position_entry_price", "position_current_price",
            "position_pnl", "position_pnl_pct",
            
            # Exit
            "exit_signal", "exit_reason",
            
            # Capital
            "capital", "daily_pnl",
            
            # Trade Action
            "action",  # "ENTRY_CE", "ENTRY_PE", "EXIT_TARGET", "EXIT_SL", "SKIP", etc.
        ]
        
        # Initialize CSV
        self.rows = []
        self._init_csv()
        
        print(f"📝 Debug logger initialized:  {self.log_file}")
    
    def _init_csv(self):
        """Create CSV with headers"""
        with open(self.log_file, 'w') as f:
            f.write(",".join(self. columns) + "\n")
    
    def log(self, data: dict):
        """Log a row of data"""
        row = []
        for col in self.columns:
            value = data.get(col, "")
            # Handle None values
            if value is None: 
                value = ""
            # Handle floats
            elif isinstance(value, float):
                value = round(value, 4)
            row.append(str(value))
        
        self.rows.append(row)
        
        # Write to file every row (for real-time debugging)
        with open(self.log_file, 'a') as f:
            f.write(",".join(row) + "\n")
    
    def get_dataframe(self) -> pd.DataFrame:
        """Get all logged data as DataFrame"""
        return pd.read_csv(self.log_file)
    
    def print_summary(self):
        """Print summary of logged data"""
        df = self.get_dataframe()
        
        print(f"\n📊 DEBUG LOG SUMMARY")
        print(f"=" * 50)
        print(f"Total rows logged: {len(df)}")
        print(f"Log file: {self. log_file}")
        
        if len(df) > 0:
            print(f"\n📈 Market Bias Distribution:")
            print(df['market_bias'].value_counts().to_string())
            
            print(f"\n🎯 Entry Signals:")
            print(df['entry_signal'].value_counts().to_string())
            
            print(f"\n🚫 Entry Blocked Reasons:")
            blocked = df[df['entry_blocked_reason'] != ""]
            if len(blocked) > 0:
                print(blocked['entry_blocked_reason']. value_counts().to_string())
            else:
                print("   No blocked entries")
            
            print(f"\n🔄 Actions Taken:")
            print(df['action']. value_counts().to_string())
        
        print(f"=" * 50)