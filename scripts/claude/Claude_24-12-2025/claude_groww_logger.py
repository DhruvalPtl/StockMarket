import os
from datetime import datetime

class GrowwLogger:
    def __init__(self):
        # 1. Setup File Names
        date_str = datetime.now().strftime('%Y%m%d')
        self.bot_log_file = f"D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_bot_log\\Claude_Bot_Log_{date_str}.csv"
        self.trade_file = f"D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_trade_book\\Claude_Trade_Book_{date_str}.csv"
        
        # 2. Counters for tracking
        self.tick_count = 0
        self.trade_count = 0
        self.last_print_time = None

        self._init_files()

    def _init_files(self):
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.bot_log_file), exist_ok=True)
        os.makedirs(os.path.dirname(self.trade_file), exist_ok=True)
        
        # Init Bot Log (Market Data Snapshot)
        if not os.path.exists(self.bot_log_file):
            cols = [
                "Timestamp", "Spot", "RSI", "ATM_Strike", "PCR", 
                "CE_Price", "PE_Price", "CE_OI", "PE_OI", 
                "CE_Delta", "PE_Delta", "Status", "PnL", "Reason"
            ]
            with open(self.bot_log_file, 'w', newline='', encoding='utf-8') as f:
                f.write(",".join(cols) + "\n")

        # Init Trade Book (Buy/Sell Record)
        if not os.path.exists(self.trade_file):
            cols = [
                "Entry_Time", "Exit_Time", "Symbol", "Type", 
                "Entry_Price", "Exit_Price", "Max_Price", 
                "PnL", "Balance", "Exit_Reason"
            ]
            with open(self.trade_file, 'w') as f:
                f.write(",".join(cols) + "\n")
                
        print(f"📝 Logs Ready:")
        print(f"   1. {self.bot_log_file}")
        print(f"   2. {self.trade_file}")

    def log_tick(self, engine, status, pnl, reason):
        """Saves one second of market data to Bot Log"""
        try:
            self.tick_count += 1
            
            row = [
                datetime.now().strftime("%H:%M:%S"),
                engine.spot_ltp, int(engine.rsi), engine.atm_strike, engine.pcr,
                engine.atm_ce['ltp'], engine.atm_pe['ltp'],
                engine.atm_ce['oi'], engine.atm_pe['oi'],
                round(engine.atm_ce['delta'], 4), round(engine.atm_pe['delta'], 4),
                status, round(pnl, 2), reason
            ]
            
            with open(self.bot_log_file, 'a', newline='', encoding='utf-8') as f:
                f.write(",".join(map(str, row)) + "\n")
                f.flush()
            
            # Print periodic update (every 10 ticks = ~50 seconds)
            if self.tick_count % 10 == 0:
                self._print_tick_summary(engine, status, pnl)
                
        except Exception as e:
            print(f"\n❌ Tick Log Error: {e}")

    def log_trade(self, trade, exit_price, pnl, balance, reason):
        """Saves a finished trade to Trade Book"""
        try:
            self.trade_count += 1
            
            row = [
                trade['entry_time'].strftime("%H:%M:%S"),
                datetime.now().strftime("%H:%M:%S"),
                trade['symbol'], trade['type'],
                trade['entry_price'], exit_price, trade['peak'],
                round(pnl, 2), round(balance, 2), reason
            ]
            
            with open(self.trade_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
                f.flush()
            
            # Always print trade results
            self._print_trade_summary(trade, exit_price, pnl, balance, reason)
            
        except Exception as e:
            print(f"\n❌ Trade Log Error: {e}")

    def _print_tick_summary(self, engine, status, pnl):
        """Print periodic market status"""
        now = datetime.now()
        
        # Only print if at least 30 seconds passed since last print
        if self.last_print_time and (now - self.last_print_time).seconds < 30:
            return
        
        self.last_print_time = now
        
        print(f"\n")
        print(f"{'='*60}")
        print(f"⏰ {now.strftime('%H:%M:%S')} | Update #{self.tick_count}")
        print(f"{'='*60}")
        print(f"📊 Nifty Spot: {engine.spot_ltp:.2f} | ATM: {engine.atm_strike}")
        print(f"📈 RSI: {int(engine.rsi)} | PCR: {engine.pcr}")
        print(f"💰 Current PnL: ₹{pnl:.2f}")
        print(f"🎯 Status: {status}")
        
        if engine.atm_ce['ltp'] > 0 and engine.atm_pe['ltp'] > 0:
            print(f"📞 CE: ₹{engine.atm_ce['ltp']:.2f} (Δ={engine.atm_ce['delta']:.3f})")
            print(f"📞 PE: ₹{engine.atm_pe['ltp']:.2f} (Δ={engine.atm_pe['delta']:.3f})")
        
        print(f"{'='*60}\n")

    def _print_trade_summary(self, trade, exit_price, pnl, balance, reason):
        """Print detailed trade results"""
        profit_emoji = "✅" if pnl > 0 else "❌"
        
        print(f"\n")
        print(f"{'='*60}")
        print(f"{profit_emoji} TRADE #{self.trade_count} CLOSED - {reason}")
        print(f"{'='*60}")
        print(f"Symbol: {trade['symbol']} ({trade['type']})")
        print(f"Entry:  ₹{trade['entry_price']:.2f} @ {trade['entry_time'].strftime('%H:%M:%S')}")
        print(f"Exit:   ₹{exit_price:.2f} @ {datetime.now().strftime('%H:%M:%S')}")
        print(f"Peak:   ₹{trade['peak']:.2f}")
        print(f"")
        print(f"PnL:    ₹{pnl:,.2f} ({(pnl/trade['entry_price']*100):.2f}%)")
        print(f"Balance: ₹{balance:,.2f}")
        print(f"{'='*60}\n")

    def print_session_start(self):
        """Print when trading session starts"""
        print(f"\n")
        print(f"{'='*60}")
        print(f"🚀 TRADING SESSION STARTED")
        print(f"{'='*60}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Logs: Recording to CSV files")
        print(f"{'='*60}\n")

    def print_session_end(self, initial_capital, final_capital, trades):
        """Print end of session summary"""
        total_pnl = final_capital - initial_capital
        win_count = sum(1 for t in trades if t.get('pnl', 0) > 0)
        loss_count = len(trades) - win_count
        win_rate = (win_count / len(trades) * 100) if trades else 0
        
        print(f"\n")
        print(f"{'='*60}")
        print(f"🏁 TRADING SESSION ENDED")
        print(f"{'='*60}")
        print(f"Starting Capital: ₹{initial_capital:,.2f}")
        print(f"Ending Capital:   ₹{final_capital:,.2f}")
        print(f"Total PnL:        ₹{total_pnl:,.2f} ({(total_pnl/initial_capital)*100:.2f}%)")
        print(f"")
        print(f"Total Trades:     {len(trades)}")
        print(f"Winning Trades:   {win_count}")
        print(f"Losing Trades:    {loss_count}")
        print(f"Win Rate:         {win_rate:.1f}%")
        print(f"")
        print(f"Total Ticks:      {self.tick_count}")
        print(f"{'='*60}\n")