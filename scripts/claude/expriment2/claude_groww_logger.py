"""
MODULAR GROWW LOGGER v2.0
✅ Supports Multiple Strategies
✅ Creates Separate Folders per Strategy
✅ distinct Trade Books for Strategy A, B, C, and Live
"""

import os
from datetime import datetime

class GrowwLogger:
    def __init__(self, strategy_name="Default"):
        self.strategy_name = strategy_name
        self.date_str = datetime.now().strftime('%Y%m%d')
        
        # Base Path
        base_path = "D:\\StockMarket\\StockMarket\\scripts\\claude\\expriment2"
        
        # Create Strategy-Specific Folder
        # e.g., .../claude_trade_book/Strategy_A_Trend/
        self.log_dir = f"{base_path}\\claude_trade_book\\{self.strategy_name}"
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Define Files
        self.trade_file = f"{self.log_dir}\\TradeBook_{self.strategy_name}_{self.date_str}.csv"
        
        # Tracking
        self.trade_count = 0
        self._init_files()
    
    def _init_files(self):
        """Initialize CSV with Headers if it doesn't exist"""
        if not os.path.exists(self.trade_file):
            cols = [
                "Entry_Time", "Exit_Time", "Signal", "Strike", 
                "Entry_Price", "Exit_Price", "PnL", "Reason", 
                "Spot_at_Entry", "VWAP_at_Entry", "RSI_at_Entry"
            ]
            with open(self.trade_file, 'w') as f:
                f.write(",".join(cols) + "\n")
        
        # We don't print "Logs Ready" here to avoid spamming console 4 times
    
    def log_trade(self, trade_dict):
        """Log a completed trade to the specific strategy file"""
        try:
            self.trade_count += 1
            
            row = [
                trade_dict['start_time'].strftime("%H:%M:%S"),
                datetime.now().strftime("%H:%M:%S"),
                trade_dict['type'],
                trade_dict['strike'],
                trade_dict['entry_price'],
                trade_dict['exit_price'],
                round(trade_dict['pnl'], 2),
                trade_dict['reason'],
                trade_dict['debug_spot'],
                round(trade_dict['debug_vwap'], 2),
                round(trade_dict['debug_rsi'], 2)
            ]
            
            with open(self.trade_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
        
        except Exception as e:
            print(f"❌ Log Error ({self.strategy_name}): {e}")