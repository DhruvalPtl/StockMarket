"""
Nifty Options Backtesting Framework
Based on OI, PCR, and Technical Indicators Strategy
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class NiftyOptionsBacktester:
    def __init__(self, initial_capital=10000):
        """
        Initialize backtester with capital and parameters
        
        Parameters:
        -----------
        initial_capital : float
            Starting capital in INR (default: 10,000)
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self. position = None
        self.trades = []
        self.equity_curve = []
        
        # Strategy Parameters (based on your research document)
        self.RSI_OVERBOUGHT = 60
        self.RSI_OVERSOLD = 40
        self.PCR_BULLISH_MIN = 1.10
        self.PCR_BEARISH_MAX = 0.90
        
        # Risk Management
        self.max_loss_per_trade = 0.05  # 5% of capital per trade
        self.daily_loss_limit = 0.10    # 10% daily loss limit
        self.target_profit_percent = 0.15  # 15 point target
        self.stop_loss_percent = 0.10      # 10 point stop
        
    def load_historical_data(self, file_path):
        """
        Load historical data from CSV or create from Groww API
        
        Expected columns:
        - Timestamp, Spot, RSI, ATM_Strike, PCR, CE_Price, PE_Price, 
          CE_OI, PE_OI, CE_Delta, PE_Delta
        """
        try:
            df = pd.read_csv(file_path)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            df = df.sort_values('Timestamp').reset_index(drop=True)
            
            # Calculate additional indicators
            df = self._calculate_indicators(df)
            
            return df
        except Exception as e:
            print(f"Error loading data: {e}")
            return None
    
    def _calculate_indicators(self, df):
        """
        Calculate technical indicators and OI signals
        """
        # OI Change (proxy for Short Covering / Long Unwinding)
        df['CE_OI_Change'] = df['CE_OI'].pct_change()
        df['PE_OI_Change'] = df['PE_OI'].pct_change()
        
        # PCR Change
        df['PCR_Change'] = df['PCR'].diff()
        
        # Price momentum
        df['Price_Change'] = df['Spot'].diff()
        df['Price_Change_Pct'] = df['Spot'].pct_change() * 100
        
        # Volume-like indicator using OI
        df['Total_OI'] = df['CE_OI'] + df['PE_OI']
        df['OI_Imbalance'] = (df['PE_OI'] - df['CE_OI']) / df['Total_OI']
        
        return df
    
    def identify_short_covering(self, row, prev_row):
        """
        Identify Short Covering signal (BULLISH)
        
        Conditions:
        1. Price moving UP
        2. Call OI decreasing (CE_OI_Change < 0)
        3. RSI crossing above 60
        4. PCR rising
        """
        if prev_row is None:
            return False
            
        return (
            row['Price_Change'] > 0 and
            row['CE_OI_Change'] < -0.01 and  # Call OI dropping
            row['RSI'] > self.RSI_OVERBOUGHT and
            prev_row['RSI'] <= self.RSI_OVERBOUGHT and
            row['PCR_Change'] > 0
        )
    
    def identify_long_unwinding(self, row, prev_row):
        """
        Identify Long Unwinding signal (BEARISH)
        
        Conditions:
        1. Price moving DOWN
        2. Put OI decreasing (PE_OI_Change < 0)
        3. RSI crossing below 40
        4. PCR falling
        """
        if prev_row is None:
            return False
            
        return (
            row['Price_Change'] < 0 and
            row['PE_OI_Change'] < -0.01 and  # Put OI dropping
            row['RSI'] < self.RSI_OVERSOLD and
            prev_row['RSI'] >= self.RSI_OVERSOLD and
            row['PCR_Change'] < 0
        )
    
    def calculate_position_size(self, premium_price):
        """
        Calculate position size based on capital
        
        For ₹10,000 capital, we can afford ~1 lot of ATM options
        Lot size = 25-50 for Nifty (using 50 for calculation)
        """
        lot_size = 50  # Standard Nifty lot size
        max_investment = self.capital * 0.70  # Use 70% of capital max
        
        # Calculate how many lots we can afford
        cost_per_lot = premium_price * lot_size
        
        if cost_per_lot > max_investment:
            return 0  # Can't afford even 1 lot
        
        # For small capital, stick to 1 lot
        return 1
    
    def enter_position(self, row, signal_type, entry_time):
        """
        Enter a trading position
        
        Parameters: 
        -----------
        row : pandas.Series
            Current market data
        signal_type : str
            'CALL' or 'PUT'
        entry_time : datetime
            Entry timestamp
        """
        premium_price = row['CE_Price'] if signal_type == 'CALL' else row['PE_Price']
        lot_size = 50
        
        position_size = self.calculate_position_size(premium_price)
        
        if position_size == 0:
            return False
        
        # Calculate targets and stops
        entry_value = premium_price
        target = entry_value * (1 + self.target_profit_percent)
        stop_loss = entry_value * (1 - self.stop_loss_percent)
        
        self.position = {
            'type': signal_type,
            'entry_time': entry_time,
            'entry_price': entry_value,
            'quantity': lot_size * position_size,
            'lot_size': lot_size,
            'target': target,
            'stop_loss': stop_loss,
            'spot_entry':  row['Spot']
        }
        
        return True
    
    def exit_position(self, row, exit_time, exit_reason):
        """
        Exit current position and record trade
        """
        if self.position is None:
            return
        
        exit_price = row['CE_Price'] if self.position['type'] == 'CALL' else row['PE_Price']
        
        pnl = (exit_price - self.position['entry_price']) * self.position['quantity']
        pnl_percent = (pnl / (self.position['entry_price'] * self.position['quantity'])) * 100
        
        trade_record = {
            'entry_time': self.position['entry_time'],
            'exit_time': exit_time,
            'type': self.position['type'],
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'quantity': self.position['quantity'],
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'exit_reason': exit_reason,
            'duration': (exit_time - self. position['entry_time']).total_seconds() / 60  # minutes
        }
        
        self.trades.append(trade_record)
        self.capital += pnl
        self.position = None
    
    def check_exit_conditions(self, row, current_time):
        """
        Check if any exit condition is met
        """
        if self.position is None:
            return False, None
        
        current_price = row['CE_Price'] if self.position['type'] == 'CALL' else row['PE_Price']
        
        # Target hit
        if current_price >= self.position['target']:
            return True, 'TARGET'
        
        # Stop loss hit
        if current_price <= self.position['stop_loss']: 
            return True, 'STOP_LOSS'
        
        # Time-based exit (end of day or max holding period)
        if current_time. hour >= 15 and current_time.minute >= 15:
            return True, 'EOD'
        
        # Duration-based exit (max 30 minutes for scalping)
        duration = (current_time - self.position['entry_time']).total_seconds() / 60
        if duration > 30:
            return True, 'TIME_EXIT'
        
        return False, None
    
    def run_backtest(self, data):
        """
        Main backtesting loop
        
        Parameters:
        -----------
        data : pandas.DataFrame
            Historical market data
        
        Returns:
        --------
        dict :  Backtest results and statistics
        """
        print("Starting backtest...")
        print(f"Initial Capital: ₹{self.initial_capital:,.2f}")
        print(f"Data points: {len(data)}")
        print("-" * 50)
        
        for i in range(1, len(data)):
            current_row = data.iloc[i]
            prev_row = data.iloc[i-1]
            current_time = current_row['Timestamp']
            
            # Track equity curve
            self.equity_curve.append({
                'timestamp': current_time,
                'capital': self.capital
            })
            
            # Check daily loss limit
            if self._check_daily_loss_limit(current_time):
                if self.position:
                    self.exit_position(current_row, current_time, 'DAILY_LIMIT')
                continue
            
            # If in position, check exit conditions
            if self.position:
                should_exit, exit_reason = self.check_exit_conditions(current_row, current_time)
                if should_exit:
                    self.exit_position(current_row, current_time, exit_reason)
                continue
            
            # Look for entry signals
            # Short Covering Signal (Buy CALL)
            if self.identify_short_covering(current_row, prev_row):
                self.enter_position(current_row, 'CALL', current_time)
                continue
            
            # Long Unwinding Signal (Buy PUT)
            if self.identify_long_unwinding(current_row, prev_row):
                self.enter_position(current_row, 'PUT', current_time)
                continue
        
        # Close any open position at end
        if self.position:
            self.exit_position(data. iloc[-1], data.iloc[-1]['Timestamp'], 'BACKTEST_END')
        
        return self.generate_results()
    
    def _check_daily_loss_limit(self, current_time):
        """
        Check if daily loss limit has been hit
        """
        # Get trades for current day
        current_date = current_time.date()
        daily_trades = [t for t in self.trades 
                       if t['exit_time'].date() == current_date]
        
        if not daily_trades:
            return False
        
        daily_pnl = sum(t['pnl'] for t in daily_trades)
        daily_loss_pct = abs(daily_pnl / self.initial_capital)
        
        return daily_pnl < 0 and daily_loss_pct >= self.daily_loss_limit
    
    def generate_results(self):
        """
        Generate comprehensive backtest results
        """
        if not self.trades:
            return {
                'error': 'No trades executed',
                'initial_capital': self.initial_capital,
                'final_capital': self.capital
            }
        
        trades_df = pd.DataFrame(self.trades)
        
        # Calculate metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
        total_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
        
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean()) if losing_trades > 0 else 0
        
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Calculate returns
        net_pnl = self.capital - self.initial_capital
        roi = (net_pnl / self.initial_capital) * 100
        
        # Maximum drawdown
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['peak'] = equity_df['capital']. cummax()
        equity_df['drawdown'] = (equity_df['capital'] - equity_df['peak']) / equity_df['peak'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
        results = {
            'summary': {
                'initial_capital': self.initial_capital,
                'final_capital':  self.capital,
                'net_pnl': net_pnl,
                'roi_percent': roi,
                'max_drawdown_percent': max_drawdown
            },
            'trade_statistics': {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate_percent': win_rate,
                'avg_win':  avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'avg_trade_duration_min': trades_df['duration'].mean()
            },
            'breakdown': {
                'call_trades': len(trades_df[trades_df['type'] == 'CALL']),
                'put_trades': len(trades_df[trades_df['type'] == 'PUT']),
                'target_exits': len(trades_df[trades_df['exit_reason'] == 'TARGET']),
                'stop_loss_exits': len(trades_df[trades_df['exit_reason'] == 'STOP_LOSS']),
                'time_exits': len(trades_df[trades_df['exit_reason'] == 'TIME_EXIT']),
                'eod_exits': len(trades_df[trades_df['exit_reason'] == 'EOD'])
            },
            'trades_df': trades_df,
            'equity_curve': equity_df
        }
        
        return results
    
    def print_results(self, results):
        """
        Print formatted backtest results
        """
        if 'error' in results:
            print(f"ERROR: {results['error']}")
            return
        
        print("\n" + "="*60)
        print("BACKTEST RESULTS")
        print("="*60)
        
        print("\n📊 SUMMARY")
        print("-" * 60)
        for key, value in results['summary']. items():
            if 'percent' in key:
                print(f"{key. replace('_', ' ').title()}: {value:.2f}%")
            else:
                print(f"{key.replace('_', ' ').title()}: ₹{value:,.2f}")
        
        print("\n📈 TRADE STATISTICS")
        print("-" * 60)
        for key, value in results['trade_statistics'].items():
            if 'percent' in key or 'rate' in key:
                print(f"{key.replace('_', ' ').title()}: {value:.2f}%")
            elif 'factor' in key:
                print(f"{key.replace('_', ' ').title()}: {value:.2f}")
            elif 'duration' in key:
                print(f"{key.replace('_', ' ').title()}: {value:.2f} minutes")
            elif 'avg' in key:
                print(f"{key.replace('_', ' ').title()}: ₹{value:. 2f}")
            else:
                print(f"{key.replace('_', ' ').title()}: {value}")
        
        print("\n🔍 BREAKDOWN")
        print("-" * 60)
        for key, value in results['breakdown']. items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        
        print("\n" + "="*60)
    
    def plot_results(self, results):
        """
        Plot equity curve and trade distribution
        """
        try:
            import matplotlib.pyplot as plt
            
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            
            # Equity Curve
            equity_df = results['equity_curve']
            axes[0, 0].plot(equity_df. index, equity_df['capital'])
            axes[0, 0].set_title('Equity Curve')
            axes[0, 0].set_xlabel('Trade Number')
            axes[0, 0].set_ylabel('Capital (₹)')
            axes[0, 0].grid(True)
            
            # Drawdown
            axes[0, 1].fill_between(equity_df.index, equity_df['drawdown'], 0, alpha=0.3, color='red')
            axes[0, 1].set_title('Drawdown %')
            axes[0, 1].set_xlabel('Trade Number')
            axes[0, 1].set_ylabel('Drawdown %')
            axes[0, 1].grid(True)
            
            # PnL Distribution
            trades_df = results['trades_df']
            axes[1, 0].hist(trades_df['pnl'], bins=30, edgecolor='black')
            axes[1, 0].set_title('PnL Distribution')
            axes[1, 0].set_xlabel('PnL (₹)')
            axes[1, 0].set_ylabel('Frequency')
            axes[1, 0].grid(True)
            
            # Win/Loss Pie Chart
            win_loss_data = [
                results['trade_statistics']['winning_trades'],
                results['trade_statistics']['losing_trades']
            ]
            axes[1, 1].pie(win_loss_data, labels=['Wins', 'Losses'], autopct='%1.1f%%', startangle=90)
            axes[1, 1].set_title(f"Win Rate: {results['trade_statistics']['win_rate_percent']:.1f}%")
            
            plt.tight_layout()
            plt.savefig('backtest_results.png', dpi=300, bbox_inches='tight')
            print("\n📊 Charts saved as 'backtest_results.png'")
            plt.show()
            
        except ImportError:
            print("\n⚠️ matplotlib not installed. Install with: pip install matplotlib")


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    
    # Initialize backtester
    backtester = NiftyOptionsBacktester(initial_capital=10000)
    
    # Load your conversation log data
    print("Loading data from conversations. csv...")
    data = backtester.load_historical_data('Claude_Bot_Log_20251224. csv')
    
    if data is not None:
        # Run backtest
        results = backtester.run_backtest(data)
        
        # Print results
        backtester.print_results(results)
        
        # Plot results
        backtester.plot_results(results)
        
        # Save detailed trade log
        if 'trades_df' in results: 
            results['trades_df'].to_csv('backtest_trades.csv', index=False)
            print("\n💾 Detailed trades saved to 'backtest_trades.csv'")
    else:
        print("Failed to load data!")