"""
BACKTESTER - Main backtest engine
With detailed logging
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple

from config import Config
from indicators import Indicators
from strategies import get_strategy
from position_manager import PositionManager
from option_fetcher import OptionFetcher
from logger import Logger


class Backtester:
    """Main backtest engine"""
    
    def __init__(self, config: Config, timeframe: str, strategy_code: str):
        self.config = config
        self.timeframe = timeframe
        self.strategy_code = strategy_code
        
        # Initialize components
        self.indicators = Indicators(config)
        self.strategy = get_strategy(strategy_code, config)
        self.option_fetcher = OptionFetcher(config.cache_dir)
        self.position_manager = PositionManager(config, self.option_fetcher)
        self.logger = Logger(config.debug_dir, timeframe, strategy_code)
        
        # Capital tracking
        self.capital = config.capital
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.current_date = None
        
        # Results
        self.trades:  List[Dict] = []
        self.equity_curve: List[Dict] = []
    
    def run(self) -> Dict:
        """Run the backtest"""
        print(f"\n{'='*60}")
        print(f"🚀 STARTING BACKTEST")
        print(f"{'='*60}")
        print(f"   Strategy:   {self.strategy.name}")
        print(f"   Timeframe: {self.timeframe}")
        print(f"   Capital:   ₹{self.config.capital:,.0f}")
        print(f"{'='*60}\n")
        
        # Load and prepare data
        df = self._load_data()
        df = self._prepare_data(df)
        
        # Run backtest
        self._process_data(df)
        
        # Print failure analysis
        self._print_failure_analysis()
        
        # Save logs
        self.logger.save()
        
        # Return results
        return self._get_results()
    
    def _load_data(self) -> pd.DataFrame:
        """Load raw data from CSV"""
        print(f"📂 Loading data from:  {self.config.data_file}")
        df = pd.read_csv(self.config.data_file)
        df['datetime'] = pd.to_datetime(df['datetime'])
        print(f"   Loaded {len(df)} rows")
        return df
    
    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Resample and calculate indicators"""
        print(f"📊 Preparing {self.timeframe} data...")
        
        # Resample to timeframe
        df = self.indicators.resample_to_timeframe(df, self.timeframe)
        print(f"   Resampled to {len(df)} candles")
        
        # Calculate indicators
        df = self.indicators.calculate_all(df)
        print(f"   Indicators calculated")
        
        return df
    
    def _process_data(self, df:  pd.DataFrame):
        """Process each candle"""
        total_rows = len(df)
        prev_row = None
        
        for idx, row in df.iterrows():
            # Progress
            if idx % 500 == 0:
                print(f"   Processing candle {idx}/{total_rows}...")
            
            # Process single candle
            self._process_candle(row, prev_row)
            prev_row = row
        
        print(f"   ✅ Processed all {total_rows} candles")
    
    def _process_candle(self, row: pd.Series, prev_row: pd.Series):
        """Process a single candle"""
        current_time = row['datetime']
        current_date = current_time.date()
        
        # Reset daily stats if new day
        if self.current_date != current_date:
            self._reset_daily_stats(current_date)
        
        # Initialize log data
        log_data = self._get_base_log_data(row)
        
        # Check if market hours
        if not self._is_market_hours(current_time):
            log_data['action'] = 'SKIP_NOT_MARKET_HOURS'
            self.logger.log(log_data)
            return
        
        # Check if indicators ready
        if not row['indicators_ready']:
            log_data['action'] = 'SKIP_INDICATORS_WARMUP'
            self.logger.log(log_data)
            return
        
        # Check daily limits
        if self.daily_pnl <= -self.config.max_daily_loss:
            log_data['action'] = 'SKIP_DAILY_LOSS_LIMIT'
            log_data['action_details'] = f"Daily loss ₹{abs(self.daily_pnl):.0f} >= ₹{self.config.max_daily_loss:.0f}"
            self.logger.log(log_data)
            return
        
        if self.daily_pnl >= self.config.daily_target:
            log_data['action'] = 'SKIP_DAILY_TARGET_REACHED'
            log_data['action_details'] = f"Daily profit ₹{self.daily_pnl:.0f} >= ₹{self.config.daily_target:.0f}"
            self.logger.log(log_data)
            return
        
        # If in position, manage it
        if self.position_manager.has_position():
            self._manage_position(row, log_data)
        else:
            self._check_entry(row, prev_row, log_data)
        
        # Add cache stats
        cache_stats = self.option_fetcher.get_stats()
        log_data['cache_hits'] = cache_stats['cache_hits']
        log_data['cache_misses'] = cache_stats['cache_misses']
        
        self.logger.log(log_data)
    
    def _check_entry(self, row: pd.Series, prev_row:  pd.Series, log_data: Dict):
        """Check for entry signal"""
        current_time = row['datetime']
        
        # Check cooldown
        in_cooldown, cooldown_reason = self.position_manager.is_in_cooldown(current_time)
        log_data['in_cooldown'] = 'TRUE' if in_cooldown else 'FALSE'
        
        if in_cooldown:
            log_data['action'] = 'SKIP_COOLDOWN'
            log_data['action_details'] = cooldown_reason
            return
        
        # Check if too late for new entries
        end_time = datetime.strptime(self.config.market_end, "%H:%M").time()
        if current_time.time() >= end_time:
            log_data['action'] = 'SKIP_MARKET_CLOSING'
            return
        
        # Get strategy signal
        signal = self.strategy.check_entry(row, prev_row)
        log_data['signal'] = signal or ""
        
        # Add strategy reason details
        entry_reason = self.strategy.get_entry_reason(row)
        for key, value in entry_reason.items():
            if key not in log_data:
                log_data[key] = value
        
        # Add RSI zone
        rsi = row['rsi']
        if rsi > 70:
            log_data['rsi_zone'] = 'OVERBOUGHT'
        elif rsi < 30:
            log_data['rsi_zone'] = 'OVERSOLD'
        else:
            log_data['rsi_zone'] = 'NEUTRAL'
        
        if signal is None:
            log_data['action'] = 'SKIP_NO_SIGNAL'
            log_data['entry_conditions_met'] = 'FALSE'
            return
        
        log_data['entry_conditions_met'] = 'TRUE'
        
        # Try to enter position
        success, details = self.position_manager.enter_position(signal, row)
        
        # Add strike search details to log
        strike_search = self.position_manager.get_last_strike_search()
        log_data.update(strike_search)
        
        if success:
            log_data['action'] = f'ENTRY_{signal}'
            log_data['position_type'] = details['option_type']
            log_data['position_strike'] = details['strike']
            log_data['entry_price'] = details['entry_price']
            log_data['position_expiry'] = details['expiry']
            log_data['action_details'] = f"{details['strike_type']} @ ₹{details['entry_price']:.2f}"
            self.daily_trades += 1
            
            # Print entry
            print(f"   🟢 ENTRY:  {details['option_type']}@{details['strike']} | "
                  f"₹{details['entry_price']:.2f} | {details['strike_type']}")
        else:
            log_data['action'] = 'SKIP_ENTRY_FAILED'
            log_data['action_details'] = details.get('reason', 'UNKNOWN')
    
    def _manage_position(self, row: pd.Series, log_data: Dict):
        """Manage existing position"""
        # Get position status
        status = self.position_manager.get_position_status(row)
        
        log_data.update({
            'has_position': 'TRUE',
            'position_type': status['option_type'],
            'position_strike':  status['strike'],
            'entry_price': status['entry_price'],
            'current_price': status['current_price'],
            'pnl_points': status['pnl_points'],
            'pnl_rupees': status['pnl_rupees'],
            'pnl_pct': round(status['pnl_points'] / status['entry_price'] * 100, 2) if status['entry_price'] > 0 else 0,
            'peak_price': status['peak_price'],
            'drop_from_peak':  status['drop_from_peak'],
            'trailing_active':  'TRUE' if status['trailing_active'] else 'FALSE',
            'hold_minutes': status['hold_minutes']
        })
        
        # Check exit conditions
        should_exit, exit_reason, exit_details = self.position_manager.check_exit(row)
        
        if should_exit: 
            # Execute exit
            exit_price = exit_details['current_price']
            trade = self.position_manager.exit_position(exit_reason, exit_price, row['datetime'])
            
            # Update capital
            self.capital += trade['pnl_rupees']
            self.daily_pnl += trade['pnl_rupees']
            
            # Save trade
            trade['capital_after'] = self.capital
            self.trades.append(trade)
            
            # Update equity curve
            self.equity_curve.append({
                'datetime': row['datetime'],
                'capital': self.capital
            })
            
            # Log
            log_data['action'] = f'EXIT_{exit_reason}'
            log_data['exit_reason'] = exit_reason
            log_data['exit_price'] = exit_price
            log_data['capital'] = self.capital
            log_data['action_details'] = f"PnL: ₹{trade['pnl_rupees']:.0f} ({trade['pnl_points']:.1f} pts)"
            
            # Print trade
            emoji = "✅" if trade['is_winner'] else "❌"
            print(f"   {emoji} EXIT: {trade['option_type']}@{trade['strike']} | "
                  f"₹{trade['pnl_rupees']:+.0f} | {exit_reason}")
        else:
            log_data['action'] = 'HOLDING'
            log_data['action_details'] = f"PnL: ₹{status['pnl_rupees']:.0f} | Peak: ₹{status['peak_price']:.2f}"
    
    def _get_base_log_data(self, row: pd.Series) -> Dict:
        """Get base log data for a candle"""
        return {
            # Time
            'datetime':  row['datetime'],
            'date': row['datetime'].date(),
            'time': row['datetime'].time(),
            # Timeframe & Strategy
            'timeframe': self.timeframe,
            'strategy': self.strategy_code,
            # Price Data
            'spot_open': round(row['open'], 2),
            'spot_high': round(row['high'], 2),
            'spot_low': round(row['low'], 2),
            'spot_close': round(row['close'], 2),
            'fut_open': round(row['fut_open'], 2),
            'fut_high': round(row['fut_high'], 2),
            'fut_low': round(row['fut_low'], 2),
            'fut_close': round(row['fut_close'], 2),
            'vwap': round(row['vwap'], 2),
            # Indicators
            'ema_fast':  round(row['ema_fast'], 2),
            'ema_slow':  round(row['ema_slow'], 2),
            'rsi': round(row['rsi'], 2),
            # Signals
            'fut_vs_vwap': 'ABOVE' if row['fut_above_vwap'] else 'BELOW',
            'ema_crossover': 'BULLISH' if row['ema_bullish'] else ('BEARISH' if row['ema_bearish'] else 'NEUTRAL'),
            'spot_vs_ema': 'ABOVE' if row['spot_above_ema_fast'] else 'BELOW',
            'candle_color':  'GREEN' if row['candle_green'] else 'RED',
            'candle_body':  round(row['candle_body'], 2),
            # Capital
            'capital': round(self.capital, 2),
            'daily_pnl': round(self.daily_pnl, 2),
            'daily_trades': self.daily_trades,
            'consecutive_losses': self.position_manager.consecutive_losses,
            # Position (default)
            'has_position': 'FALSE',
            'in_cooldown': 'FALSE'
        }
    
    def _is_market_hours(self, dt: datetime) -> bool:
        """Check if within market hours"""
        start = datetime.strptime(self.config.market_start, "%H:%M").time()
        end = datetime.strptime(self.config.force_exit_time, "%H:%M").time()
        return start <= dt.time() <= end
    
    def _reset_daily_stats(self, new_date):
        """Reset daily statistics"""
        if self.current_date is not None:
            print(f"📅 {self.current_date} | Daily PnL: ₹{self.daily_pnl:+,.0f} | "
                  f"Trades: {self.daily_trades} | Capital: ₹{self.capital:,.0f}")
        
        self.current_date = new_date
        self.daily_pnl = 0.0
        self.daily_trades = 0
    
    def _print_failure_analysis(self):
        """Print analysis of why entries failed"""
        analysis = self.logger.get_failure_analysis()
        
        if not analysis.get('total_signals'):
            return
        
        print(f"\n{'='*60}")
        print("🔍 ENTRY FAILURE ANALYSIS")
        print(f"{'='*60}")
        print(f"   Total Signals:       {analysis['total_signals']}")
        print(f"   Successful Entries:  {analysis['successful_entries']}")
        print(f"   Failed Entries:     {analysis['failed_entries']}")
        
        if analysis['failure_reasons']:
            print(f"\n   Failure Reasons:")
            for reason, count in sorted(analysis['failure_reasons'].items(), key=lambda x:  -x[1]):
                print(f"      {reason}: {count}")
        
        print(f"\n   Strike Status Breakdown:")
        for strike, statuses in analysis['strike_status_counts'].items():
            if statuses:
                print(f"      {strike}:")
                for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
                    print(f"         {status}:  {count}")
        
        print(f"{'='*60}")
    
    def _get_results(self) -> Dict:
        """Calculate and return backtest results"""
        if not self.trades:
            return {"error": "No trades executed"}
        
        # Basic stats
        total_trades = len(self.trades)
        winners = [t for t in self.trades if t['is_winner']]
        losers = [t for t in self.trades if not t['is_winner']]
        
        win_rate = len(winners) / total_trades * 100 if total_trades > 0 else 0
        
        gross_profit = sum(t['pnl_rupees'] for t in winners)
        gross_loss = abs(sum(t['pnl_rupees'] for t in losers))
        net_pnl = gross_profit - gross_loss
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        avg_win = gross_profit / len(winners) if winners else 0
        avg_loss = gross_loss / len(losers) if losers else 0
        
        # Max drawdown
        peak_capital = self.config.capital
        max_dd = 0
        for eq in self.equity_curve:
            if eq['capital'] > peak_capital:
                peak_capital = eq['capital']
            dd = (peak_capital - eq['capital']) / peak_capital * 100
            if dd > max_dd:
                max_dd = dd
        
        return {
            'initial_capital': self.config.capital,
            'final_capital': self.capital,
            'net_pnl': net_pnl,
            'return_pct': (self.capital - self.config.capital) / self.config.capital * 100,
            'total_trades': total_trades,
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': win_rate,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss':  avg_loss,
            'max_drawdown': max_dd,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }