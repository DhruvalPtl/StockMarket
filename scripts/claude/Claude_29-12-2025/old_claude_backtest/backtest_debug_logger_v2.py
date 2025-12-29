"""
BACKTEST DEBUG LOGGER V2
========================
Enhanced logging for backtesting with real option data
Saves every decision point to CSV for analysis

Author: Claude
Date: 2025-12-27
"""

import pandas as pd
import os
from datetime import datetime
from typing import Dict, Any, Optional


class BacktestDebugLoggerV2:
    """Enhanced debug logger for backtesting with real option data"""
    
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            output_dir = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\debug_logs"
        
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = f"{output_dir}\\backtest_debug_v2_{timestamp}.csv"
        
        # All columns
        self.columns = [
            # Time
            "datetime", "date", "time",
            
            # Price Data (Spot & Futures)
            "spot_close", "fut_close", "vwap",
            
            # Indicators
            "rsi", "ema5", "ema13",
            
            # Real PCR (from option chain)
            "ce_oi_total", "pe_oi_total", "pcr",
            
            # Conditions
            "rsi_ready", "in_market", "in_cooldown",
            
            # Signal Analysis
            "spot_vs_vwap",
            "ema_crossover",
            "rsi_zone",
            "pcr_signal",
            
            # Signal Counts
            "bullish_signals", "bearish_signals",
            
            # Market Bias
            "market_bias",
            
            # Strike Selection
            "atm_strike",
            "tried_strikes",
            "selected_strike",
            "strike_type",  # ATM/OTM/ITM
            "option_type",  # CE/PE
            "option_price",
            "option_cost",
            "option_oi",
            "option_volume",
            "expiry",
            
            # Entry Decision
            "entry_signal",
            "entry_blocked_reason",
            "entry_executed",
            
            # Position (if active)
            "has_position",
            "position_type",
            "position_strike",
            "position_entry_price",
            "position_current_price",
            "position_pnl_points",
            "position_pnl_rupees",
            "position_pnl_pct",
            "position_peak",
            "trailing_active",
            
            # Exit
            "exit_signal",
            "exit_reason",
            "exit_price",
            
            # Capital
            "capital",
            "daily_pnl",
            
            # Action Taken
            "action",
            
            # API Stats
            "api_calls_total",
            "cache_hits_total",
        ]
        
        self._init_csv()
        print(f"📝 Debug Logger V2 initialized:  {self.log_file}")
    
    def _init_csv(self):
        """Create CSV with headers"""
        with open(self.log_file, 'w') as f:
            f.write(",".join(self. columns) + "\n")
    
    def log(self, data: Dict[str, Any]):
        """Log a row of data"""
        row = []
        for col in self.columns:
            value = data. get(col, "")
            
            if value is None:
                value = ""
            elif isinstance(value, float):
                if abs(value) < 0.0001:
                    value = 0
                else:
                    value = round(value, 4)
            elif isinstance(value, bool):
                value = str(value).upper()
            elif isinstance(value, list):
                value = "|".join(str(v) for v in value)
            
            # Escape commas in strings
            value_str = str(value)
            if "," in value_str:
                value_str = f'"{value_str}"'
            
            row.append(value_str)
        
        with open(self.log_file, 'a') as f:
            f.write(",". join(row) + "\n")
    
    def get_dataframe(self) -> pd.DataFrame:
        """Get all logged data as DataFrame"""
        return pd.read_csv(self.log_file)
    
    def print_summary(self):
        """Print comprehensive summary"""
        df = self.get_dataframe()
        
        print(f"\n{'='*60}")
        print(f"📊 DEBUG LOG SUMMARY V2")
        print(f"{'='*60}")
        print(f"📁 Log File: {self. log_file}")
        print(f"📝 Total Rows: {len(df):,}")
        
        if len(df) == 0:
            print("   No data logged")
            return
        
        print(f"\n📈 MARKET BIAS DISTRIBUTION")
        print("-" * 40)
        bias_counts = df['market_bias'].value_counts()
        for bias, count in bias_counts.items():
            pct = count / len(df) * 100
            print(f"   {bias}: {count:,} ({pct:.1f}%)")
        
        print(f"\n🎯 ENTRY SIGNALS")
        print("-" * 40)
        signals = df[df['entry_signal']. notna() & (df['entry_signal'] != '')]
        if len(signals) > 0:
            signal_counts = signals['entry_signal'].value_counts()
            for signal, count in signal_counts.items():
                print(f"   {signal}: {count: ,}")
        else:
            print("   No entry signals")
        
        print(f"\n✅ ENTRIES EXECUTED")
        print("-" * 40)
        entries = df[df['entry_executed'] == 'TRUE']
        if len(entries) > 0:
            print(f"   Total Entries: {len(entries)}")
            strike_types = entries['strike_type'].value_counts()
            for st, count in strike_types.items():
                print(f"   {st} Strikes: {count}")
        else: 
            print("   No entries executed")
        
        print(f"\n🚫 ENTRY BLOCKED REASONS")
        print("-" * 40)
        blocked = df[df['entry_blocked_reason'].notna() & (df['entry_blocked_reason'] != '')]
        if len(blocked) > 0:
            reason_counts = blocked['entry_blocked_reason'].value_counts().head(10)
            for reason, count in reason_counts.items():
                print(f"   {reason}: {count: ,}")
        else:
            print("   No blocked entries")
        
        print(f"\n🚪 EXIT REASONS")
        print("-" * 40)
        exits = df[df['exit_reason'].notna() & (df['exit_reason'] != '')]
        if len(exits) > 0:
            exit_counts = exits['exit_reason'].value_counts()
            for reason, count in exit_counts.items():
                print(f"   {reason}: {count}")
        else: 
            print("   No exits")
        
        print(f"\n🔄 ACTIONS TAKEN")
        print("-" * 40)
        action_counts = df['action'].value_counts().head(15)
        for action, count in action_counts.items():
            print(f"   {action}: {count: ,}")
        
        print(f"\n📡 API USAGE")
        print("-" * 40)
        if 'api_calls_total' in df. columns:
            last_row = df.iloc[-1]
            print(f"   Total API Calls: {last_row. get('api_calls_total', 'N/A')}")
            print(f"   Cache Hits: {last_row.get('cache_hits_total', 'N/A')}")
        
        print(f"{'='*60}")