"""
ENHANCED GROWW LOGGER - Multi-Strategy Support
✅ Separate trade books per strategy
✅ Aggregated performance reporting
✅ Strategy comparison metrics
"""

import os
from datetime import datetime

class GrowwLogger:
    def __init__(self, strategy_name="ORIGINAL"):
        date_str = datetime.now().strftime('%Y%m%d')
        base_path = "D:\\StockMarket\\StockMarket\\scripts\\claude\\expriment3"
        
        # Strategy-specific files
        safe_name = strategy_name.replace(" ", "_").replace("-", "_")
        self.bot_log_file = f"{base_path}\\claude_bot_log\\Claude_Bot_Log_{safe_name}_{date_str}.csv"
        self.trade_file = f"{base_path}\\claude_trade_book\\Claude_Trade_Book_{safe_name}_{date_str}.csv"
        
        self.strategy_name = strategy_name
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
                "Timestamp", "Strategy", "Spot", "RSI", "RSI_Ready", "VWAP", "ATM_Strike", "PCR",
                "CE_Price", "PE_Price", "CE_OI", "PE_OI",
                "CE_Delta", "PE_Delta", "Status", "PnL", "Reason"
            ]
            with open(self.bot_log_file, 'w', newline='', encoding='utf-8') as f:
                f.write(",".join(cols) + "\n")
        
        # Trade Book
        if not os.path.exists(self.trade_file):
            cols = [
                "Entry_Time", "Exit_Time", "Strategy", "Symbol", "Type", "Strike",
                "Entry_Price", "Exit_Price", "Max_Price",
                "PnL", "PnL_Pct", "Balance", "Exit_Reason"
            ]
            with open(self.trade_file, 'w') as f:
                f.write(",".join(cols) + "\n")
        
        print(f"📝 [{self.strategy_name}] Logs Ready:")
        print(f"   Bot Log: {self.bot_log_file}")
        print(f"   Trades:  {self.trade_file}")
    
    def log_tick(self, engine, status, pnl, reason):
        """Log market state"""
        try:
            self.tick_count += 1
            
            row = [
                datetime.now().strftime("%H:%M:%S"),
                self.strategy_name,
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
        
        except Exception as e:
            print(f"\n❌ [{self.strategy_name}] Tick Log Error: {e}")
    
    def log_trade(self, trade, exit_price, pnl, balance, reason):
        """Log completed trade"""
        try:
            self.trade_count += 1
            
            pnl_pct = (pnl / (trade['entry_price'] * 75)) * 100  # 75 = lot size
            
            row = [
                trade['entry_time'].strftime("%H:%M:%S"),
                datetime.now().strftime("%H:%M:%S"),
                self.strategy_name,
                trade['symbol'],
                trade['type'],
                trade['strike'],
                trade['entry_price'],
                exit_price,
                trade['peak'],
                round(pnl, 2),
                round(pnl_pct, 2),
                round(balance, 2),
                reason
            ]
            
            with open(self.trade_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
                f.flush()
            
            self._print_trade_summary(trade, exit_price, pnl, pnl_pct, balance, reason)
        
        except Exception as e:
            print(f"\n❌ [{self.strategy_name}] Trade Log Error: {e}")
    
    def _print_trade_summary(self, trade, exit_price, pnl, pnl_pct, balance, reason):
        """Print detailed trade results"""
        profit_emoji = "✅" if pnl > 0 else "❌"
        
        print(f"\n")
        print(f"{'='*60}")
        print(f"{profit_emoji} [{self.strategy_name}] TRADE #{self.trade_count} - {reason}")
        print(f"{'='*60}")
        print(f"Symbol: {trade['symbol']} ({trade['type']} @ Strike {trade['strike']})")
        print(f"Entry:  Rs.{trade['entry_price']:.2f} @ {trade['entry_time'].strftime('%H:%M:%S')}")
        print(f"Exit:   Rs.{exit_price:.2f} @ {datetime.now().strftime('%H:%M:%S')}")
        print(f"Peak:   Rs.{trade['peak']:.2f}")
        print(f"")
        print(f"PnL:    Rs.{pnl:,.2f} ({pnl_pct:+.2f}%)")
        print(f"Balance: Rs.{balance:,.2f}")
        
        hold_time = (datetime.now() - trade['entry_time']).seconds // 60
        print(f"Hold Time: {hold_time} minutes")
        print(f"{'='*60}\n")
    
    def print_session_end(self, initial_capital, final_capital, trades):
        """Session end with statistics"""
        total_pnl = final_capital - initial_capital
        win_count = sum(1 for t in trades if t.get('pnl', 0) > 0)
        loss_count = len(trades) - win_count
        win_rate = (win_count / len(trades) * 100) if trades else 0
        
        if trades:
            best_trade = max(trades, key=lambda x: x.get('pnl', 0))
            worst_trade = min(trades, key=lambda x: x.get('pnl', 0))
            avg_win = sum(t['pnl'] for t in trades if t['pnl'] > 0) / win_count if win_count > 0 else 0
            avg_loss = sum(t['pnl'] for t in trades if t['pnl'] < 0) / loss_count if loss_count > 0 else 0
        
        print(f"\n")
        print(f"{'='*60}")
        print(f"🏁 [{self.strategy_name}] SESSION ENDED")
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
                print(f"Profit Factor:    {profit_factor:.2f}")
            else:
                print(f"Profit Factor:    ∞ (No losses!)")
        
        print(f"")
        print(f"Total Ticks:      {self.tick_count}")
        print(f"{'='*60}\n")


class MultiStrategyLogger:
    """Aggregated logger for all strategies"""
    
    def __init__(self):
        date_str = datetime.now().strftime('%Y%m%d')
        base_path = "D:\\StockMarket\\StockMarket\\scripts\\claude\\expriment3"
        
        self.summary_file = f"{base_path}\\claude_summary\\Strategy_Comparison_{date_str}.csv"
        os.makedirs(os.path.dirname(self.summary_file), exist_ok=True)
        
        # Initialize summary CSV
        if not os.path.exists(self.summary_file):
            cols = [
                "Strategy", "Initial_Capital", "Final_Capital", "Total_PnL", "PnL_Pct",
                "Total_Trades", "Wins", "Losses", "Win_Rate", "Best_Trade", "Worst_Trade",
                "Avg_Win", "Avg_Loss", "Profit_Factor"
            ]
            with open(self.summary_file, 'w') as f:
                f.write(",".join(cols) + "\n")
        
        print(f"\n📊 Multi-Strategy Summary: {self.summary_file}\n")
    
    def log_strategy_summary(self, strategy_name, initial_capital, final_capital, trades):
        """Log summary for one strategy"""
        try:
            total_pnl = final_capital - initial_capital
            pnl_pct = (total_pnl / initial_capital) * 100
            
            win_count = sum(1 for t in trades if t.get('pnl', 0) > 0)
            loss_count = len(trades) - win_count
            win_rate = (win_count / len(trades) * 100) if trades else 0
            
            if trades:
                best_trade = max(trades, key=lambda x: x.get('pnl', 0))['pnl']
                worst_trade = min(trades, key=lambda x: x.get('pnl', 0))['pnl']
                avg_win = sum(t['pnl'] for t in trades if t['pnl'] > 0) / win_count if win_count > 0 else 0
                avg_loss = sum(t['pnl'] for t in trades if t['pnl'] < 0) / loss_count if loss_count > 0 else 0
                
                if avg_loss != 0 and loss_count > 0:
                    profit_factor = abs((avg_win * win_count) / (abs(avg_loss) * loss_count))
                else:
                    profit_factor = 999.99  # Infinity placeholder
            else:
                best_trade = 0
                worst_trade = 0
                avg_win = 0
                avg_loss = 0
                profit_factor = 0
            
            row = [
                strategy_name, initial_capital, round(final_capital, 2),
                round(total_pnl, 2), round(pnl_pct, 2),
                len(trades), win_count, loss_count, round(win_rate, 2),
                round(best_trade, 2), round(worst_trade, 2),
                round(avg_win, 2), round(avg_loss, 2), round(profit_factor, 2)
            ]
            
            with open(self.summary_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
                f.flush()
        
        except Exception as e:
            print(f"\n❌ Summary Log Error: {e}")
    
    def print_final_comparison(self, results):
        """Print final comparison table"""
        print(f"\n\n")
        print(f"{'='*80}")
        print(f"🏆 FINAL STRATEGY COMPARISON")
        print(f"{'='*80}")
        print(f"{'Strategy':<20} {'PnL':>12} {'PnL%':>8} {'Trades':>8} {'Win%':>8} {'P.Factor':>10}")
        print(f"{'-'*80}")
        
        for result in sorted(results, key=lambda x: x['pnl'], reverse=True):
            print(f"{result['name']:<20} "
                  f"Rs.{result['pnl']:>10,.2f} "
                  f"{result['pnl_pct']:>7.2f}% "
                  f"{result['trades']:>8} "
                  f"{result['win_rate']:>7.1f}% "
                  f"{result['profit_factor']:>10.2f}")
        
        print(f"{'='*80}\n")
 