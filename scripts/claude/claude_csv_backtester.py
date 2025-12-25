"""
CSV-BASED BACKTESTER
Test your strategy on recorded historical data
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

class CSVBacktester:
    def __init__(self, csv_file, initial_capital=10000):
        print("\n" + "="*70)
        print("📊 CSV-BASED BACKTESTER")
        print("="*70)
        
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.lot_size = 75
        
        # Load data
        print(f"📂 Loading: {csv_file}")
        self.data = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(self.data)} rows")
        
        # Convert timestamp
        if 'Timestamp' in self.data.columns:
            self.data['Timestamp'] = pd.to_datetime(self.data['Timestamp'])
        
        # Trading tracking
        self.trades = []
        self.active_position = None
        self.daily_pnl = 0
        self.max_loss_limit = initial_capital * 0.10
        
        # Statistics
        self.total_ticks_processed = 0
        
        print(f"💰 Initial Capital: Rs.{initial_capital:,.2f}")
        print(f"🛡️  Max Daily Loss: Rs.{self.max_loss_limit:,.2f}")
        print("="*70 + "\n")
    
    def run(self, strategy_func):
        """
        Run backtest with custom strategy function
        
        Args:
            strategy_func: Function that takes (row, engine_state) and returns 'BUY_CE', 'BUY_PE', or None
        """
        print("🚀 Starting Backtest...\n")
        
        for idx, row in self.data.iterrows():
            self.total_ticks_processed += 1
            
            # Check risk limits
            if abs(self.daily_pnl) >= self.max_loss_limit:
                print(f"\n🛑 Daily loss limit hit at tick {idx}")
                break
            
            # Build engine state from row
            engine_state = self._build_engine_state(row)
            
            # If no position, check for entry
            if not self.active_position:
                signal = strategy_func(row, engine_state)
                
                if signal in ['BUY_CE', 'BUY_PE']:
                    self._enter_position(row, signal, engine_state)
            
            # If position active, manage it
            else:
                self._manage_position(row, engine_state)
            
            # Print progress every 100 ticks
            if self.total_ticks_processed % 100 == 0:
                self._print_progress(row)
        
        # Close any open position at end
        if self.active_position:
            last_row = self.data.iloc[-1]
            engine_state = self._build_engine_state(last_row)
            self._exit_position(last_row, engine_state, "END_OF_DATA")
        
        # Print results
        self._print_results()
    
    def _build_engine_state(self, row):
        """Build engine-like state from CSV row"""
        return {
            'timestamp': row.get('Timestamp', ''),
            'spot': row.get('Spot_LTP', row.get('Spot', 0)),
            'rsi': row.get('RSI', 0),
            'vwap': row.get('VWAP', 0),
            'ema5': row.get('EMA5', row.get('EMA_5', 0)),
            'ema13': row.get('EMA13', row.get('EMA_13', 0)),
            'pcr': row.get('PCR', row.get('PCR_Ratio', 0)),
            'atm_strike': row.get('ATM_Strike', 0),
            'ce_price': row.get('CE_LTP', row.get('CE_Price', row.get('ATM_CE_Price', 0))),
            'pe_price': row.get('PE_LTP', row.get('PE_Price', row.get('ATM_PE_Price', 0))),
            'ce_oi': row.get('CE_OI', row.get('ATM_CE_OI', 0)),
            'pe_oi': row.get('PE_OI', row.get('ATM_PE_OI', 0)),
            'ce_delta': row.get('CE_Delta', row.get('ATM_CE_Delta', 0)),
            'pe_delta': row.get('PE_Delta', row.get('ATM_PE_Delta', 0))
        }
    
    def _enter_position(self, row, signal, engine_state):
        """Enter a position"""
        if signal == 'BUY_CE':
            entry_price = engine_state['ce_price']
            option_type = 'CE'
        else:  # BUY_PE
            entry_price = engine_state['pe_price']
            option_type = 'PE'
        
        if entry_price == 0:
            return
        
        # Check affordability
        total_cost = entry_price * self.lot_size
        if total_cost > self.capital * 0.7:
            return
        
        self.active_position = {
            'type': option_type,
            'entry_price': entry_price,
            'entry_time': engine_state['timestamp'],
            'entry_tick': self.total_ticks_processed,
            'peak': entry_price,
            'target': entry_price + 10,  # 10 point target
            'stop_loss': entry_price - 5  # 5 point stop
        }
        
        print(f"🟢 ENTRY: {option_type} @ Rs.{entry_price:.2f} | Tick {self.total_ticks_processed}")
    
    def _manage_position(self, row, engine_state):
        """Manage active position"""
        # Get current price
        if self.active_position['type'] == 'CE':
            current_price = engine_state['ce_price']
        else:
            current_price = engine_state['pe_price']
        
        if current_price == 0:
            return
        
        # Update peak
        if current_price > self.active_position['peak']:
            self.active_position['peak'] = current_price
        
        # Check exit conditions
        exit_reason = None
        
        # 1. Target hit
        if current_price >= self.active_position['target']:
            exit_reason = "TARGET"
        
        # 2. Stop loss
        elif current_price <= self.active_position['stop_loss']:
            exit_reason = "STOP_LOSS"
        
        # 3. Trailing stop
        elif self.active_position['peak'] > self.active_position['target']:
            trailing_stop = self.active_position['peak'] * 0.9
            if current_price <= trailing_stop:
                exit_reason = "TRAILING_STOP"
        
        # 4. Time-based (30 ticks = ~30 seconds in real trading)
        ticks_held = self.total_ticks_processed - self.active_position['entry_tick']
        if ticks_held > 1800:  # 30 minutes
            exit_reason = "TIME_EXIT"
        
        if exit_reason:
            self._exit_position(row, engine_state, exit_reason)
    
    def _exit_position(self, row, engine_state, reason):
        """Exit position"""
        if self.active_position['type'] == 'CE':
            exit_price = engine_state['ce_price']
        else:
            exit_price = engine_state['pe_price']
        
        if exit_price == 0:
            return
        
        # Calculate PnL
        pnl = (exit_price - self.active_position['entry_price']) * self.lot_size
        
        # Update capital
        self.capital += pnl
        self.daily_pnl += pnl
        
        # Record trade
        trade_record = {
            'entry_time': self.active_position['entry_time'],
            'exit_time': engine_state['timestamp'],
            'type': self.active_position['type'],
            'entry_price': self.active_position['entry_price'],
            'exit_price': exit_price,
            'peak': self.active_position['peak'],
            'pnl': pnl,
            'exit_reason': reason,
            'ticks_held': self.total_ticks_processed - self.active_position['entry_tick']
        }
        self.trades.append(trade_record)
        
        print(f"🔴 EXIT: {reason} @ Rs.{exit_price:.2f} | PnL: Rs.{pnl:,.2f} | Balance: Rs.{self.capital:,.2f}")
        
        self.active_position = None
    
    def _print_progress(self, row):
        """Print progress update"""
        if self.active_position:
            print(f"⏳ Tick {self.total_ticks_processed} | In Position | Balance: Rs.{self.capital:,.2f}")
        else:
            print(f"⏳ Tick {self.total_ticks_processed} | Scanning | Balance: Rs.{self.capital:,.2f}")
    
    def _print_results(self):
        """Print backtest results"""
        print("\n" + "="*70)
        print("📊 BACKTEST RESULTS")
        print("="*70)
        
        # Overall stats
        total_pnl = self.capital - self.initial_capital
        total_return_pct = (total_pnl / self.initial_capital) * 100
        
        print(f"Initial Capital: Rs.{self.initial_capital:,.2f}")
        print(f"Final Capital:   Rs.{self.capital:,.2f}")
        print(f"Total PnL:       Rs.{total_pnl:,.2f} ({total_return_pct:.2f}%)")
        print(f"")
        
        if len(self.trades) == 0:
            print("No trades executed.")
            print("="*70 + "\n")
            return
        
        # Trade statistics
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] <= 0]
        
        print(f"Total Trades:    {len(self.trades)}")
        print(f"Winning Trades:  {len(winning_trades)}")
        print(f"Losing Trades:   {len(losing_trades)}")
        print(f"Win Rate:        {len(winning_trades)/len(self.trades)*100:.1f}%")
        print(f"")
        
        # PnL stats
        if winning_trades:
            avg_win = np.mean([t['pnl'] for t in winning_trades])
            max_win = max([t['pnl'] for t in winning_trades])
            print(f"Average Win:     Rs.{avg_win:,.2f}")
            print(f"Max Win:         Rs.{max_win:,.2f}")
        
        if losing_trades:
            avg_loss = np.mean([t['pnl'] for t in losing_trades])
            max_loss = min([t['pnl'] for t in losing_trades])
            print(f"Average Loss:    Rs.{avg_loss:,.2f}")
            print(f"Max Loss:        Rs.{max_loss:,.2f}")
        
        # Exit reasons breakdown
        print(f"\nExit Reasons:")
        exit_counts = {}
        for t in self.trades:
            reason = t['exit_reason']
            exit_counts[reason] = exit_counts.get(reason, 0) + 1
        
        for reason, count in exit_counts.items():
            print(f"  {reason}: {count}")
        
        print("="*70 + "\n")
        
        # Save detailed results
        self._save_results()
    
    def _save_results(self):
        """Save detailed trade results to CSV"""
        if len(self.trades) == 0:
            return
        
        df = pd.DataFrame(self.trades)
        filename = f"Backtest_Results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False)
        print(f"📝 Detailed results saved to: {filename}")


# ============================================================
# EXAMPLE STRATEGY FUNCTIONS
# ============================================================

def simple_rsi_strategy(row, engine_state):
    """
    Simple RSI strategy:
    - Buy PE when RSI < 35 and price below VWAP
    - Buy CE when RSI > 65 and price above VWAP
    """
    rsi = engine_state['rsi']
    spot = engine_state['spot']
    vwap = engine_state['vwap']
    
    if rsi < 35 and spot < vwap:
        return 'BUY_PE'
    elif rsi > 65 and spot > vwap:
        return 'BUY_CE'
    
    return None


def momentum_burst_strategy(row, engine_state):
    """
    Momentum burst strategy (like your bot):
    - Bearish: RSI < 40, Spot < VWAP, PCR < 0.95
    - Bullish: RSI > 55, Spot > VWAP, PCR > 1.05
    """
    rsi = engine_state['rsi']
    spot = engine_state['spot']
    vwap = engine_state['vwap']
    pcr = engine_state['pcr']
    
    # Bearish setup
    if rsi < 40 and spot < vwap and 0.85 < pcr < 0.95:
        return 'BUY_PE'
    
    # Bullish setup
    if rsi > 55 and spot > vwap and pcr > 1.05:
        return 'BUY_CE'
    
    return None


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    # Configuration
    CSV_FILE = "Master_Data_2025-12-24.csv"  # Your recorded data
    INITIAL_CAPITAL = 10000
    
    # Create backtester
    backtester = CSVBacktester(CSV_FILE, INITIAL_CAPITAL)
    
    # Run with your chosen strategy
    print("🎯 Using: Momentum Burst Strategy")
    backtester.run(momentum_burst_strategy)
    
    # Or try the simple RSI strategy
    # backtester.run(simple_rsi_strategy)