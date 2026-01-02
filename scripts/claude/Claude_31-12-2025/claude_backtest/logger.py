"""
LOGGER - Log every movement with real values
With detailed strike search columns
"""

import os
import csv
from datetime import datetime
from typing import Dict, List


class Logger:
    """Logs every bot movement to CSV"""
    
    def __init__(self, debug_dir: str, timeframe: str, strategy: str):
        self.debug_dir = debug_dir
        os.makedirs(debug_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join(
            debug_dir,
            f"debug_{strategy}_{timeframe}_{timestamp}.csv"
        )
        
        self.rows: List[Dict] = []
        
        # Define all columns - EXPANDED
        self.columns = [
            # ========== TIME ==========
            "datetime", "date", "time",
            
            # ========== CONFIG ==========
            "timeframe", "strategy",
            
            # ========== PRICE DATA ==========
            "spot_open", "spot_high", "spot_low", "spot_close",
            "fut_open", "fut_high", "fut_low", "fut_close",
            "vwap",
            
            # ========== INDICATORS ==========
            "ema_fast", "ema_slow", "rsi",
            
            # ========== SIGNALS ==========
            "fut_vs_vwap",           # ABOVE or BELOW
            "prev_fut_vs_vwap",
            "vwap_cross",
            "min_body_required",
            "ema_crossover",         # BULLISH, BEARISH, NEUTRAL
            "spot_vs_ema",           # ABOVE or BELOW
            "candle_color",          # GREEN or RED
            "candle_body",           # Size in points
            "rsi_zone",              # OVERBOUGHT, OVERSOLD, NEUTRAL
            
            # ========== ENTRY DECISION ==========
            "signal",                # BUY_CE, BUY_PE, or empty
            "entry_conditions_met",  # TRUE or FALSE
            
            # ========== STRIKE SEARCH DETAILS ==========
            "search_atm_strike",     # ATM strike calculated
            "search_option_type",    # CE or PE
            "search_spot_price",     # Spot price used
            "search_capital",        # Current capital
            "search_max_cost",       # Max affordable cost (capital * 0.95)
            "search_min_price",      # Min option price allowed
            "search_max_price",      # Max option price allowed
            "expiry_used",           # Expiry date used
            "strikes_tried",         # All strikes tried
            
            # Strike 1 (ATM)
            "strike_1_price",        # Option price
            "strike_1_cost",         # Cost (price * lot)
            "strike_1_status",       # SELECTED, TOO_CHEAP, TOO_EXPENSIVE, UNAFFORDABLE, NO_DATA
            
            # Strike 2 (OTM1)
            "strike_2_price",
            "strike_2_cost",
            "strike_2_status",
            
            # Strike 3 (OTM2)
            "strike_3_price",
            "strike_3_cost",
            "strike_3_status",
            
            # Strike 4 (ITM)
            "strike_4_price",
            "strike_4_cost",
            "strike_4_status",
            
            "failure_reason",        # Why no strike was selected
            
            # ========== PENDING ENTRY INFO ==========
            "pending_strike",
            "pending_strike_type",
            "expected_entry_price",
            
            # ========== POSITION INFO ==========
            "has_position",          # TRUE or FALSE
            "position_type",         # CE or PE
            "position_strike",       # Strike price
            "position_expiry",       # Expiry date
            "signal_time",
            "entry_delay",
            "entry_slippage",
            "entry_price",           # Entry option price
            "current_price",         # Current option price
            "pnl_points",            # P&L in points
            "pnl_rupees",            # P&L in rupees
            "pnl_pct",               # P&L percentage
            "peak_price",            # Highest price seen
            "drop_from_peak",        # Current drop from peak
            "trailing_active",       # TRUE or FALSE
            "hold_minutes",          # How long held
            
            # ========== EXIT INFO ==========
            "exit_signal",           # Exit condition triggered
            "exit_trigger_reason",   # The reason an exit was signaled (will execute next candle)
            "exit_reason",           # STOP_LOSS, TARGET, TRAILING_STOP, TIME_EXIT, EOD_EXIT
            "exit_price",            # Exit price
            "exit_slippage",
            "pnl_gross",
            "transaction_cost",
            "pnl_net",
            
            # ========== ACTION ==========
            "action",                # What happened this row
            "action_details",        # Additional details
            
            # ========== CAPITAL & RISK ==========
            "capital",               # Current capital
            "daily_pnl",             # Today's P&L
            "daily_trades",          # Today's trade count
            "consecutive_losses",    # Consecutive losses
            "in_cooldown",           # TRUE or FALSE
            
            # ========== CACHE STATS ==========
            "cache_hits",
            "cache_misses"
        ]
    
    def log(self, data: Dict):
        """Add a log entry"""
        # Ensure all columns exist
        row = {col: "" for col in self.columns}
        row.update(data)
        self.rows.append(row)
    
    def save(self):
        """Save all logs to CSV"""
        if not self.rows:
            print("⚠️ No logs to save")
            return
        
        with open(self.filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.columns)
            writer.writeheader()
            writer.writerows(self.rows)
        
        print(f"📝 Debug log saved:  {self.filename}")
        print(f"   Total rows: {len(self.rows)}")
    
    def get_summary(self) -> Dict:
        """Get summary of logged actions"""
        if not self.rows:
            return {}
        
        actions = {}
        for row in self.rows:
            action = row.get('action', 'UNKNOWN')
            actions[action] = actions.get(action, 0) + 1
        
        return actions
    
    def get_failure_analysis(self) -> Dict:
        """Analyze why entries failed"""
        if not self.rows:
            return {}
        
        analysis = {
            "total_signals": 0,
            "successful_entries": 0,
            "failed_entries": 0,
            "failure_reasons": {},
            "strike_status_counts": {
                "strike_1":  {},
                "strike_2": {},
                "strike_3":  {},
                "strike_4": {}
            }
        }
        
        for row in self.rows:
            if row.get('entry_conditions_met') == 'TRUE':
                analysis["total_signals"] += 1
                
                if 'ENTRY' in row.get('action', ''):
                    analysis["successful_entries"] += 1
                else:
                    analysis["failed_entries"] += 1
                    reason = row.get('failure_reason', 'UNKNOWN')
                    analysis["failure_reasons"][reason] = analysis["failure_reasons"].get(reason, 0) + 1
                
                # Count strike statuses
                for i in range(1, 5):
                    status = row.get(f'strike_{i}_status', '')
                    if status:
                        key = f"strike_{i}"
                        analysis["strike_status_counts"][key][status] = \
                            analysis["strike_status_counts"][key].get(status, 0) + 1
        
        return analysis