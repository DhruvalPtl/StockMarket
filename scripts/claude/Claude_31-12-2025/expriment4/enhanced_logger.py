"""
LOGGING MODULE
Handles recording of all bot activities, trades, and performance metrics.
Features atomic file writing to prevent data loss during crashes.
"""

import os
import csv
from datetime import datetime
from typing import Dict, List, Any
from config import BotConfig

class GrowwLogger:
    """
    Per-Strategy Logger.
    Each strategy instance gets one of these to record its specific actions.
    """
    
    def __init__(self, strategy_name: str, timeframe: str):
        self.strategy_name = strategy_name
        self.timeframe = timeframe
        self.tick_count = 0
        self.trade_count = 0
        
        # Setup File Paths
        paths = BotConfig.get_log_paths()
        date_str = datetime.now().strftime('%Y%m%d')
        safe_name = f"{strategy_name.replace(' ', '_')}_{timeframe}"
        
        self.bot_log_file = os.path.join(paths['bot_log'], f"Log_{safe_name}_{date_str}.csv")
        self.trade_file = os.path.join(paths['trade_book'], f"Trades_{safe_name}_{date_str}.csv")
        
        self._init_files()

    def _init_files(self):
        """Initializes CSV headers if files don't exist."""
        # 1. Bot Activity Log
        if not os.path.exists(self.bot_log_file):
            cols = [
                "Timestamp", "Strategy", "Timeframe", "Spot", "RSI", "VWAP", 
                "ATM_Strike", "PCR", "Signal", "PnL", "Reason"
            ]
            self._write_csv(self.bot_log_file, cols, mode='w')
            
        # 2. Trade Book
        if not os.path.exists(self.trade_file):
            cols = [
                "Entry_Time", "Exit_Time", "Strategy", "Timeframe", "Symbol", "Type", 
                "Strike", "Entry_Price", "Exit_Price", "Max_Price", 
                "PnL", "PnL_Pct", "Balance", "Exit_Reason"
            ]
            self._write_csv(self.trade_file, cols, mode='w')

    def log_tick(self, engine, signal: str, daily_pnl: float, reason: str):
        """Records the current market state and strategy status."""
        self.tick_count += 1
        
        row = [
            datetime.now().strftime("%H:%M:%S"),
            self.strategy_name,
            self.timeframe,
            engine.spot_ltp,
            int(engine.rsi),
            round(engine.vwap, 2),
            engine.atm_strike,
            engine.pcr,
            signal or "SCANNING",
            round(daily_pnl, 2),
            reason
        ]
        self._write_csv(self.bot_log_file, row)

    def log_trade(self, trade: Dict, exit_price: float, pnl: float, balance: float, reason: str):
        """Records a closed trade."""
        self.trade_count += 1
        
        # Calculate Percentage
        invested = trade['entry_price'] * BotConfig.LOT_SIZE
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
        
        row = [
            trade['entry_time'].strftime("%H:%M:%S"),
            datetime.now().strftime("%H:%M:%S"),
            self.strategy_name,
            self.timeframe,
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
        
        self._write_csv(self.trade_file, row)
        self._print_trade_summary(trade, exit_price, pnl, pnl_pct, balance, reason)

    def _write_csv(self, filepath: str, row: List[Any], mode='a'):
        """
        Atomic Write Helper.
        Opens, writes, flushes, syncs, and closes.
        """
        try:
            with open(filepath, mode, newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
                f.flush()
                os.fsync(f.fileno()) # Force write to disk
        except Exception as e:
            print(f"❌ LOG ERROR ({self.strategy_name}): {e}")

    def _print_trade_summary(self, trade, exit_price, pnl, pnl_pct, balance, reason):
        """Prints a professional 'Deal Ticket' to console."""
        icon = "✅" if pnl > 0 else "🔻"
        
        print(f"\n{'-'*50}")
        print(f"{icon} TRADE CLOSED: {self.strategy_name} ({self.timeframe})")
        print(f"{'-'*50}")
        print(f"Instrument: {trade['symbol']} ({trade['type']})")
        print(f"Strike:     {trade['strike']}")
        print(f"Entry:      Rs.{trade['entry_price']:.2f}  ➔  Exit: Rs.{exit_price:.2f}")
        print(f"Reason:     {reason}")
        print(f"{'-'*50}")
        print(f"PnL:        Rs.{pnl:+.2f} ({pnl_pct:+.2f}%)")
        print(f"New Bal:    Rs.{balance:,.2f}")
        print(f"{'-'*50}\n")
        
    def print_session_end(self, initial_cap, final_cap, trades):
        """Prints end-of-day stats for this strategy."""
        total_pnl = final_cap - initial_cap
        roi = (total_pnl / initial_cap * 100)
        wins = len([t for t in trades if t['pnl'] > 0])
        losses = len([t for t in trades if t['pnl'] <= 0])
        
        print(f"\n📊 RESULTS: {self.strategy_name} ({self.timeframe})")
        print(f"Trades: {len(trades)} | Wins: {wins} | Losses: {losses}")
        print(f"Final PnL: Rs.{total_pnl:,.2f} ({roi:+.2f}%)")


class MultiStrategyLogger:
    """
    Aggregates results from all strategies into a single summary file
    at the end of the session.
    """
    def __init__(self):
        paths = BotConfig.get_log_paths()
        date_str = datetime.now().strftime('%Y%m%d')
        self.summary_file = os.path.join(paths['summary'], f"Summary_{date_str}.csv")
        
        if not os.path.exists(self.summary_file):
            cols = [
                "Strategy", "Timeframe", "Initial_Cap", "Final_Cap", "Total_PnL", 
                "ROI_Pct", "Trades", "Wins", "Losses", "Win_Rate"
            ]
            with open(self.summary_file, 'w', newline='') as f:
                csv.writer(f).writerow(cols)

    def log_strategy_result(self, result: Dict):
        """Appends one strategy's final result to the summary."""
        try:
            row = [
                result['name'],
                result['timeframe'],
                result['initial'],
                round(result['final'], 2),
                round(result['pnl'], 2),
                round(result['pnl_pct'], 2),
                result['trades'],
                result['wins'],
                result['losses'],
                round(result['win_rate'], 1)
            ]
            
            with open(self.summary_file, 'a', newline='') as f:
                csv.writer(f).writerow(row)
                
        except Exception as e:
            print(f"❌ SUMMARY ERROR: {e}")

    def print_final_comparison(self, results: List[Dict]):
        """Prints the master leaderboard."""
        print(f"\n\n{'='*80}")
        print(f"🏆 FINAL LEADERBOARD")
        print(f"{'='*80}")
        print(f"{'Strategy':<20} {'TF':<6} {'PnL':>10} {'ROI%':>8} {'Win%':>6} {'Trades':>6}")
        print(f"{'-'*80}")
        
        # Sort by PnL descending
        sorted_results = sorted(results, key=lambda x: x['pnl'], reverse=True)
        
        for r in sorted_results:
            print(f"{r['name']:<20} {r['timeframe']:<6} "
                  f"{r['pnl']:>10.2f} {r['pnl_pct']:>8.1f}% "
                  f"{r['win_rate']:>6.1f}% {r['trades']:>6}")
        print(f"{'='*80}\n")