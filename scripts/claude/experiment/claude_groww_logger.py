"""
UPDATED GROWW LOGGER
✅ Strike prices in trade book
✅ Better formatting
"""

import os
from datetime import datetime

class GrowwLogger:
    def __init__(self):
        date_str = datetime.now().strftime('%Y%m%d')
        base_path = "D:\\StockMarket\\StockMarket\\scripts\\claude"
        
        self.bot_log_file = f"{base_path}\\expriment\\Claude_Bot_Log_{date_str}.csv"
        self.trade_file = f"{base_path}\\expriment\\Claude_Trade_Book_{date_str}.csv"
        
        self.tick_count = 0
        self.trade_count = 0
        self.last_print_time = None
        
        self._init_files()
    
    def _init_files(self):
        os.makedirs(os.path.dirname(self.bot_log_file), exist_ok=True)
        os.makedirs(os.path.dirname(self.trade_file), exist_ok=True)
        
        # Bot Log
        if not os.path.exists(self.bot_log_file):
            cols = [
                "Timestamp", "Spot", "RSI", "RSI_Ready", "VWAP", "ATM_Strike", "PCR",
                "CE_Price", "PE_Price", "CE_OI", "PE_OI",
                "CE_Delta", "PE_Delta", "Status", "PnL", "Reason"
            ]
            with open(self.bot_log_file, 'w', newline='', encoding='utf-8') as f:
                f.write(",".join(cols) + "\n")
        
        # Trade Book (with strike prices)
        if not os.path.exists(self.trade_file):
            cols = [
                "Entry_Time", "Exit_Time", "Symbol", "Type", "Strike",
                "Entry_Price", "Exit_Price", "Max_Price",
                "PnL", "PnL_Pct", "Balance", "Exit_Reason"
            ]
            with open(self.trade_file, 'w') as f:
                f.write(",".join(cols) + "\n")
        
        print(f"📝 Logs Ready:")
        print(f"   1. {self.bot_log_file}")
        print(f"   2. {self.trade_file}")
    
    def log_tick(self, engine, status, pnl, reason):
        """Log market state"""
        try:
            self.tick_count += 1
            
            row = [
                datetime.now().strftime("%H:%M:%S"),
                engine.spot_ltp, int(engine.rsi), engine.rsi_warmup_complete,
                round(engine.vwap, 2), engine.atm_strike, engine.pcr,
                engine.atm_ce['ltp'], engine.atm_pe['ltp'],
                engine.atm_ce['oi'], engine.atm_pe['oi'],
                round(engine.atm_ce['delta'], 4), round(engine.atm_pe['delta'], 4),
                status, round(pnl, 2), reason
            ]
            
            with open(self.bot_log_file, 'a', newline='', encoding='utf-8') as f:
                f.write(",".join(map(str, row)) + "\n")
                f.flush()
            
            # Periodic console update
            if self.tick_count % 10 == 0:
                self._print_tick_summary(engine, status, pnl)
        
        except Exception as e:
            print(f"\n❌ Tick Log Error: {e}")
    
    def log_trade(self, trade, exit_price, pnl, balance, reason):
        """Log completed trade with strike"""
        try:
            self.trade_count += 1
            
            # Calculate PnL percentage
            pnl_pct = (pnl / (trade['entry_price'] * 75)) * 100  # 75 = lot size
            
            row = [
                trade['entry_time'].strftime("%H:%M:%S"),
                datetime.now().strftime("%H:%M:%S"),
                trade['symbol'],
                trade['type'],
                trade['strike'],  # ADDED: Strike price
                trade['entry_price'],
                exit_price,
                trade['peak'],
                round(pnl, 2),
                round(pnl_pct, 2),  # ADDED: PnL percentage
                round(balance, 2),
                reason
            ]
            
            with open(self.trade_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
                f.flush()
            
            # Print trade summary
            self._print_trade_summary(trade, exit_price, pnl, pnl_pct, balance, reason)
        
        except Exception as e:
            print(f"\n❌ Trade Log Error: {e}")
    
    def _print_tick_summary(self, engine, status, pnl):
        """Print periodic update"""
        now = datetime.now()
        
        if self.last_print_time and (now - self.last_print_time).seconds < 30:
            return
        
        self.last_print_time = now
        
        print(f"\n")
        print(f"{'='*60}")
        print(f"⏰ {now.strftime('%H:%M:%S')} | Update #{self.tick_count}")
        print(f"{'='*60}")
        print(f"📊 Nifty Spot: {engine.spot_ltp:.2f} | ATM: {engine.atm_strike}")
        
        # Show warmup status
        if not engine.rsi_warmup_complete:
            print(f"⏳ RSI Warmup: {engine.candles_processed}/{engine.rsi_periods_needed} candles")
        else:
            print(f"📈 RSI: {int(engine.rsi)} | VWAP: {engine.vwap:.2f} | PCR: {engine.pcr}")
        
        print(f"💰 Current PnL: Rs.{pnl:.2f}")
        print(f"🎯 Status: {status}")
        
        if engine.atm_ce['ltp'] > 0 and engine.atm_pe['ltp'] > 0:
            print(f"📞 CE: Rs.{engine.atm_ce['ltp']:.2f} (Δ={engine.atm_ce['delta']:.3f})")
            print(f"📞 PE: Rs.{engine.atm_pe['ltp']:.2f} (Δ={engine.atm_pe['delta']:.3f})")
        
        print(f"{'='*60}\n")
    
    def _print_trade_summary(self, trade, exit_price, pnl, pnl_pct, balance, reason):
        """Print detailed trade results"""
        profit_emoji = "✅" if pnl > 0 else "❌"
        
        print(f"\n")
        print(f"{'='*60}")
        print(f"{profit_emoji} TRADE #{self.trade_count} CLOSED - {reason}")
        print(f"{'='*60}")
        print(f"Symbol: {trade['symbol']} ({trade['type']} @ Strike {trade['strike']})")
        print(f"Entry:  Rs.{trade['entry_price']:.2f} @ {trade['entry_time'].strftime('%H:%M:%S')}")
        print(f"Exit:   Rs.{exit_price:.2f} @ {datetime.now().strftime('%H:%M:%S')}")
        print(f"Peak:   Rs.{trade['peak']:.2f}")
        print(f"")
        print(f"PnL:    Rs.{pnl:,.2f} ({pnl_pct:+.2f}%)")
        print(f"Balance: Rs.{balance:,.2f}")
        
        # Hold time
        hold_time = (datetime.now() - trade['entry_time']).seconds // 60
        print(f"Hold Time: {hold_time} minutes")
        print(f"{'='*60}\n")
    
    def print_session_start(self):
        """Session start"""
        print(f"\n")
        print(f"{'='*60}")
        print(f"🚀 TRADING SESSION STARTED")
        print(f"{'='*60}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Mode: Paper Trading (No Real Orders)")
        print(f"Logs: Recording to CSV files")
        print(f"{'='*60}\n")
    
    def print_session_end(self, initial_capital, final_capital, trades):
        """Session end with statistics"""
        total_pnl = final_capital - initial_capital
        win_count = sum(1 for t in trades if t.get('pnl', 0) > 0)
        loss_count = len(trades) - win_count
        win_rate = (win_count / len(trades) * 100) if trades else 0
        
        # Calculate best/worst trades
        if trades:
            best_trade = max(trades, key=lambda x: x.get('pnl', 0))
            worst_trade = min(trades, key=lambda x: x.get('pnl', 0))
            avg_win = sum(t['pnl'] for t in trades if t['pnl'] > 0) / win_count if win_count > 0 else 0
            avg_loss = sum(t['pnl'] for t in trades if t['pnl'] < 0) / loss_count if loss_count > 0 else 0
        
        print(f"\n")
        print(f"{'='*60}")
        print(f"🏁 TRADING SESSION ENDED")
        print(f"{'='*60}")
        print(f"Starting Capital: Rs.{initial_capital:,.2f}")
        print(f"Ending Capital:   Rs.{final_capital:,.2f}")
        print(f"Total PnL:        Rs.{total_pnl:,.2f} ({(total_pnl/initial_capital)*100:.2f}%)")
        print(f"")
        print(f"📊 TRADE STATISTICS")
        print(f"{'='*60}")
        print(f"Total Trades:     {len(trades)}")
        print(f"Winning Trades:   {win_count}")
        print(f"Losing Trades:    {loss_count}")
        print(f"Win Rate:         {win_rate:.1f}%")
        
        if trades:
            print(f"")
            print(f"Best Trade:       Rs.{best_trade['pnl']:,.2f}")
            print(f"Worst Trade:      Rs.{worst_trade['pnl']:,.2f}")
            print(f"Avg Win:          Rs.{avg_win:,.2f}")
            print(f"Avg Loss:         Rs.{avg_loss:,.2f}")
            
            if avg_loss != 0 and loss_count > 0:
                profit_factor = abs((avg_win * win_count) / (abs(avg_loss) * loss_count))
                print(f"Profit Factor:     {profit_factor:.2f}")
            else:
                print(f"Profit Factor:    ∞ (No losses! )")
        
        print(f"")
        print(f"Total Ticks:      {self.tick_count}")
        print(f"{'='*60}\n")