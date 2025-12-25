import os
from datetime import datetime

class GrowwLogger:
    def __init__(self):
        # 1. Setup File Names
        date_str = datetime.now().strftime('%Y%m%d')
        self.bot_log_file = f"Bot_Log_{date_str}_OFFLINE.csv"     
        self.trade_file   = f"Trade_Book_{date_str}_OFFLINE.csv"   

        self._init_files()

    def _init_files(self):
        # Init Bot Log (Heartbeat)
        if not os.path.exists(self.bot_log_file):
            cols = [
                "Timestamp", "Spot", "Velocity", "Wall_High", "Wall_Low", 
                "CE_Price", "PE_Price", "CE_Delta", "PE_Delta", 
                "Status", "Reason"
            ]
            with open(self.bot_log_file, 'w') as f:
                f.write(",".join(cols) + "\n")

        # Init Trade Book (Money)
        if not os.path.exists(self.trade_file):
            cols = [
                "Entry_Time", "Exit_Time", "Symbol", "Type", 
                "Entry_Price", "Exit_Price", "Max_Price", 
                "PnL", "Balance", "Exit_Reason"
            ]
            with open(self.trade_file, 'w') as f:
                f.write(",".join(cols) + "\n")
                
        print(f"📝 Offline Logs Ready:\n   1. {self.bot_log_file}\n   2. {self.trade_file}")

    def log_tick(self, engine, velocity, wall_high, wall_low, status, reason):
        """Saves one second of simulation data"""
        try:
            row = [
                datetime.now().strftime("%H:%M:%S"),
                engine.spot_ltp, round(velocity, 2), wall_high, wall_low,
                engine.atm_ce['ltp'], engine.atm_pe['ltp'],
                engine.atm_ce['delta'], engine.atm_pe['delta'],
                status, reason
            ]
            with open(self.bot_log_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
        except: pass

    def log_trade(self, trade, exit_price, pnl, balance, reason):
        """Saves a finished trade"""
        try:
            row = [
                trade['entry_time'].strftime("%H:%M:%S"),
                datetime.now().strftime("%H:%M:%S"),
                trade['symbol'], trade['type'],
                trade['entry_price'], exit_price, trade['peak'],
                round(pnl, 2), round(balance, 2), reason
            ]
            with open(self.trade_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
        except: pass