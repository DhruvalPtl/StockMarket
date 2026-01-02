"""
CLAUDE NIFTY GROWW BACKTESTER V3
================================
Uses REAL option prices from Groww API
Smart strike selection (ATM → OTM → ITM)
Real PCR from option OI

Author: Claude
Date: 2025-12-27
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import os

from groww_option_fetcher import GrowwOptionFetcher
from backtest_debug_logger_v2 import BacktestDebugLoggerV2


@dataclass
class BacktestConfigV3:
    """Configuration for backtesting"""
    # Capital
    initial_capital: float = 10000.0
    lot_size: int = 75
    
    # Option price limits
    min_option_price: float = 50.0  # Don't buy if price < 50
    max_capital_per_trade: float = 0.95  # Use max 95% of capital
    
    # Entry conditions
    min_signals_required: int = 3
    bullish_rsi_min: float = 55.0
    bullish_rsi_max: float = 75.0
    bearish_rsi_min: float = 25.0
    bearish_rsi_max: float = 45.0
    bullish_pcr_threshold: float = 1.1
    bearish_pcr_threshold:  float = 0.9
    
    # Exit conditions
    target_points:  float = 10.0
    stop_loss_points: float = 5.0
    trailing_trigger_pct: float = 0.05  # 5%
    trailing_stop_pct: float = 0.15  # 15% from peak
    max_hold_minutes: int = 30
    
    # Cooldown
    cooldown_seconds: int = 180  # 3 minutes
    
    # Risk
    daily_loss_limit_pct: float = 0.05  # 5% of capital
    
    # PCR calculation
    pcr_strikes_range: int = 10  # +/- 10 strikes from ATM


@dataclass
class TradeV3:
    """Trade record"""
    entry_time: datetime
    exit_time: datetime
    option_type: str
    strike: int
    strike_type: str  # ATM/OTM/ITM
    expiry: str
    entry_price: float
    exit_price:  float
    entry_spot: float
    exit_spot: float
    pnl_points: float
    pnl:  float
    exit_reason: str
    hold_time_minutes: float
    is_winner: bool


class ClaudeNiftyGrowwBacktesterV3:
    """
    Backtester V3 with real option data from Groww API
    """
    
    def __init__(self, config: BacktestConfigV3, 
                 api_key: str, api_secret: str,
                 debug:  bool = True):
        self.config = config
        self.debug = debug
        
        # Initialize option fetcher
        self.option_fetcher = GrowwOptionFetcher(api_key, api_secret)
        
        # Initialize debug logger
        self.debug_logger = BacktestDebugLoggerV2() if debug else None
        
        # State
        self.capital = config.initial_capital
        self.trades: List[TradeV3] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.daily_stats: List[Dict] = []
        self.active_position: Optional[Dict] = None
        self.last_exit_time: Optional[datetime] = None
        self.daily_pnl = 0.0
        
        # Results
        self.results: Optional[Dict] = None
    
    def prepare_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare indicators - use existing VWAP from CSV"""
        print("📊 Preparing indicators...")
        
        df = df.copy()
        
        # Ensure datetime
        if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
            df['datetime'] = pd.to_datetime(df['datetime'])
        
        # RSI (14 period)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)
        
        # EMAs
        df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
        df['ema13'] = df['close'].ewm(span=13, adjust=False).mean()
        
        # Use VWAP from CSV (already correct)
        if 'vwap' not in df.columns:
            print("⚠️ VWAP not in CSV, using close as fallback")
            df['vwap'] = df['close']
        else:
            print("   ✅ Using VWAP from CSV")
        
        # ATM Strike
        df['atm_strike'] = (df['close'] / 50).round() * 50
        df['atm_strike'] = df['atm_strike'].astype(int)
        
        # RSI warmup flag
        df['rsi_ready'] = df.index >= 15
        
        # Market hours flag
        df['in_market'] = df['datetime'].apply(self._in_market_hours)
        
        print("   ✅ Indicators ready")
        
        return df
    
    def _in_market_hours(self, dt: datetime) -> bool:
        """Check if within trading hours"""
        market_open = dt.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = dt.replace(hour=15, minute=25, second=0, microsecond=0)
        return market_open <= dt <= market_close
    
    def _analyze_market(self, row: pd.Series, pcr:  float) -> Tuple[str, int, int]:
        """
        Analyze market conditions and return bias
        Returns: (bias, bullish_signals, bearish_signals)
        """
        spot = row['fut_close'] if 'fut_close' in row and pd.notna(row['fut_close']) else row['close']
        vwap = row['vwap']
        rsi = row['rsi']
        ema5 = row['ema5']
        ema13 = row['ema13']
        
        bullish_signals = 0
        bearish_signals = 0
        
        # VWAP (2 points)
        if spot > vwap: 
            bullish_signals += 2
        elif spot < vwap: 
            bearish_signals += 2
        
        # EMA Crossover (1 point)
        if ema5 > ema13 and spot > ema5:
            bullish_signals += 1
        elif ema5 < ema13 and spot < ema5:
            bearish_signals += 1
        
        # RSI (1 point)
        if rsi > 60:
            bullish_signals += 1
        elif rsi < 40:
            bearish_signals += 1
        
        # PCR (1 point)
        if pcr > self.config.bullish_pcr_threshold:
            bullish_signals += 1
        elif pcr < self.config.bearish_pcr_threshold: 
            bearish_signals += 1
        
        # Determine bias
        if bullish_signals >= self.config.min_signals_required: 
            bias = "BULLISH"
        elif bearish_signals >= self.config.min_signals_required:
            bias = "BEARISH"
        else: 
            bias = "NEUTRAL"
        
        return bias, bullish_signals, bearish_signals
    
    def _check_entry(self, row: pd.Series, bias: str) -> Optional[str]:
        """Check if entry conditions are met"""
        if bias == "NEUTRAL":
            return None
        
        spot = row['fut_close'] if 'fut_close' in row and pd.notna(row['fut_close']) else row['close']
        vwap = row['vwap']
        rsi = row['rsi']
        
        if bias == "BULLISH":
            if spot <= vwap: 
                return None
            if not (self.config.bullish_rsi_min <= rsi <= self.config.bullish_rsi_max):
                return None
            return "BUY_CE"
        
        elif bias == "BEARISH": 
            if spot >= vwap:
                return None
            if not (self.config.bearish_rsi_min <= rsi <= self.config.bearish_rsi_max):
                return None
            return "BUY_PE"
        
        return None
    
    def _execute_entry(self, row:  pd.Series, signal: str, 
                       debug_data: Dict) -> bool:
        """Execute entry with real option data"""
        spot = row['close']
        option_type = 'CE' if signal == 'BUY_CE' else 'PE'
        dt = row['datetime']
        
        debug_data['atm_strike'] = row['atm_strike']
        
        # Find affordable strike using real prices
        result = self.option_fetcher.find_affordable_strike(
            spot_price=spot,
            option_type=option_type,
            dt=dt,
            capital=self.capital,
            lot_size=self.config.lot_size,
            min_price=self.config.min_option_price
        )
        
        if result is None:
            debug_data['entry_blocked_reason'] = "NO_AFFORDABLE_STRIKE"
            debug_data['entry_executed'] = False
            return False
        
        # Update debug data
        debug_data['selected_strike'] = result['strike']
        debug_data['strike_type'] = result['strike_type']
        debug_data['option_type'] = option_type
        debug_data['option_price'] = result['price']
        debug_data['option_cost'] = result['cost']
        debug_data['option_oi'] = result['oi']
        debug_data['option_volume'] = result['volume']
        debug_data['expiry'] = result['expiry']
        debug_data['entry_executed'] = True
        
        # Create position
        self.active_position = {
            'entry_time': dt,
            'option_type': option_type,
            'strike': result['strike'],
            'strike_type': result['strike_type'],
            'expiry':  result['expiry'],
            'entry_price': result['price'],
            'entry_spot': spot,
            'peak':  result['price'],
            'target': result['price'] + self.config.target_points,
            'stop_loss': result['price'] - self.config.stop_loss_points,
            'trailing_active': False
        }
        
        return True
    
    def _get_current_option_price(self, row: pd.Series) -> Optional[float]:
        """Get current option price from Groww API"""
        if not self.active_position:
            return None
        
        pos = self.active_position
        data = self.option_fetcher.get_option_price_at_time(
            strike=pos['strike'],
            option_type=pos['option_type'],
            dt=row['datetime'],
            expiry=pos['expiry']
        )
        
        if data: 
            return data['close']
        return None
    
    def _manage_position(self, row: pd.Series, 
                         debug_data: Dict) -> Optional[Tuple[float, str]]:
        """Manage active position - check for exit conditions"""
        if not self.active_position:
            return None
        
        pos = self.active_position
        current_price = self._get_current_option_price(row)
        
        if current_price is None:
            # Can't get price, hold position
            return None
        
        # Update debug data
        debug_data['position_current_price'] = current_price
        debug_data['position_pnl_points'] = current_price - pos['entry_price']
        debug_data['position_pnl_rupees'] = (current_price - pos['entry_price']) * self.config.lot_size
        debug_data['position_pnl_pct'] = (current_price - pos['entry_price']) / pos['entry_price'] * 100
        debug_data['position_peak'] = pos['peak']
        debug_data['trailing_active'] = pos['trailing_active']
        
        # Update peak
        if current_price > pos['peak']:
            pos['peak'] = current_price
        
        # Check target
        if current_price >= pos['target']:
            return (current_price, "TARGET")
        
        # Check stop loss
        if current_price <= pos['stop_loss']:
            return (current_price, "STOP_LOSS")
        
        # Check trailing stop
        gain_pct = (pos['peak'] - pos['entry_price']) / pos['entry_price']
        if gain_pct >= self.config.trailing_trigger_pct: 
            pos['trailing_active'] = True
            
            drop_from_peak = (pos['peak'] - current_price) / pos['peak']
            if drop_from_peak >= self.config.trailing_stop_pct:
                return (current_price, "TRAILING_STOP")
        
        # Check time exit
        hold_time = (row['datetime'] - pos['entry_time']).total_seconds() / 60
        if hold_time >= self.config.max_hold_minutes: 
            return (current_price, "TIME_EXIT")
        
        return None
    
    def _execute_exit(self, exit_price: float, reason: str, 
                      exit_time: datetime, exit_spot: float) -> TradeV3:
        """Execute exit and create trade record"""
        pos = self.active_position
        
        pnl_points = exit_price - pos['entry_price']
        pnl = pnl_points * self.config.lot_size
        hold_time = (exit_time - pos['entry_time']).total_seconds() / 60
        
        trade = TradeV3(
            entry_time=pos['entry_time'],
            exit_time=exit_time,
            option_type=pos['option_type'],
            strike=pos['strike'],
            strike_type=pos['strike_type'],
            expiry=pos['expiry'],
            entry_price=pos['entry_price'],
            exit_price=exit_price,
            entry_spot=pos['entry_spot'],
            exit_spot=exit_spot,
            pnl_points=pnl_points,
            pnl=pnl,
            exit_reason=reason,
            hold_time_minutes=hold_time,
            is_winner=pnl > 0
        )
        
        self.trades.append(trade)
        self.capital += pnl
        self.daily_pnl += pnl
        self.equity_curve.append((exit_time, self.capital))
        
        self.last_exit_time = exit_time
        self.active_position = None
        
        return trade
    
    def _save_daily(self, date, start_capital:  float):
        """Save daily stats"""
        self.daily_stats.append({
            'date':  date,
            'start_capital': start_capital,
            'end_capital': self.capital,
            'pnl': self.capital - start_capital,
            'trades': len([t for t in self.trades if t.entry_time.date() == date])
        })
    
    def run(self, df: pd.DataFrame, verbose: bool = True) -> Dict:
        """Run the backtest with real option data"""
        print("\n" + "=" * 60)
        print("🚀 STARTING BACKTEST V3 (Real Option Data)")
        print("=" * 60)
        print(f"Capital: ₹{self.config.initial_capital:,.2f}")
        print(f"Lot Size: {self.config.lot_size}")
        print(f"Period: {df['datetime'].min()} to {df['datetime'].max()}")
        print(f"Debug Mode: {'ON' if self.debug else 'OFF'}")
        print("=" * 60)
        
        # Reset state
        self.capital = self.config.initial_capital
        self.trades = []
        self.equity_curve = [(df['datetime'].iloc[0], self.capital)]
        self.daily_stats = []
        self.active_position = None
        self.last_exit_time = None
        
        current_date = None
        day_start_capital = self.capital
        last_pcr = 1.0  # Cache PCR to avoid too many API calls
        last_pcr_time = None
        
        total_rows = len(df)
        
        for idx, row in df.iterrows():
            # Progress indicator
            if verbose and idx % 1000 == 0:
                print(f"   Processing row {idx}/{total_rows}...")
            
            # Initialize debug data
            debug_data = {
                "datetime": row['datetime'],
                "date": row['datetime'].date(),
                "time": row['datetime'].time(),
                "spot_close": row['close'],
                "fut_close": row.get('fut_close', row['close']),
                "vwap": row['vwap'],
                "rsi":  row['rsi'],
                "ema5": row['ema5'],
                "ema13":  row['ema13'],
                "rsi_ready": row['rsi_ready'],
                "in_market": row['in_market'],
                "capital": self.capital,
                "daily_pnl":  self.daily_pnl,
                "has_position": self.active_position is not None,
                "api_calls_total":  self.option_fetcher.api_calls,
                "cache_hits_total": self.option_fetcher.cache_hits,
            }
            
            # Skip if not in market hours
            if not row['in_market']: 
                debug_data["action"] = "SKIP_NOT_MARKET_HOURS"
                if self.debug:
                    self.debug_logger.log(debug_data)
                continue
            
            # Time checks
            current_time = row['datetime'].time()
            no_entry_time = datetime.strptime("15:20", "%H:%M").time()
            force_exit_time = datetime.strptime("15:25", "%H:%M").time()
            
            # New day
            trade_date = row['datetime'].date()
            if current_date != trade_date: 
                if current_date: 
                    self._save_daily(current_date, day_start_capital)
                current_date = trade_date
                day_start_capital = self.capital
                self.daily_pnl = 0.0
                last_pcr_time = None  # Reset PCR cache for new day
                
                if verbose:
                    print(f"📅 {current_date} | Capital: ₹{self.capital:,.2f}")
            
            debug_data["daily_pnl"] = self.daily_pnl
            
            # Cooldown check
            in_cooldown = False
            if self.last_exit_time:
                elapsed = (row['datetime'] - self.last_exit_time).total_seconds()
                in_cooldown = elapsed < self.config.cooldown_seconds
            debug_data["in_cooldown"] = in_cooldown
            
            # Daily loss limit
            if abs(self.daily_pnl) >= self.config.initial_capital * self.config.daily_loss_limit_pct:
                debug_data["action"] = "SKIP_DAILY_LOSS_LIMIT"
                if self.debug:
                    self.debug_logger.log(debug_data)
                continue
            
            # Force exit at 15:25
            if self.active_position and current_time >= force_exit_time:
                exit_price = self._get_current_option_price(row)
                if exit_price:
                    trade = self._execute_exit(exit_price, "EOD_EXIT", 
                                               row['datetime'], row['close'])
                    debug_data["action"] = "EXIT_EOD"
                    debug_data["exit_reason"] = "EOD_EXIT"
                    debug_data["exit_price"] = exit_price
                    
                    if verbose:
                        emoji = "✅" if trade.is_winner else "❌"
                        print(f"  {emoji} {trade.option_type}@{trade.strike} ({trade.strike_type}) | "
                              f"₹{trade.pnl:+,.2f} | EOD_EXIT")
                
                if self.debug:
                    self.debug_logger.log(debug_data)
                continue
            
            # No new entries after 15:20
            if current_time >= no_entry_time and not self.active_position:
                debug_data["action"] = "SKIP_AFTER_1520"
                if self.debug:
                    self.debug_logger.log(debug_data)
                continue
            
            # Get PCR (cache for 5 minutes to reduce API calls)
            if last_pcr_time is None or (row['datetime'] - last_pcr_time).total_seconds() > 300:
                try:
                    pcr_data = self.option_fetcher.get_option_chain_oi(
                        spot_price=row['close'],
                        dt=row['datetime'],
                        num_strikes=self.config.pcr_strikes_range
                    )
                    last_pcr = pcr_data['pcr']
                    last_pcr_time = row['datetime']
                    debug_data["ce_oi_total"] = pcr_data['ce_oi_total']
                    debug_data["pe_oi_total"] = pcr_data['pe_oi_total']
                except: 
                    pass
            
            debug_data["pcr"] = last_pcr
            
            # Analyze market
            spot = row['fut_close'] if 'fut_close' in row and pd.notna(row['fut_close']) else row['close']
            vwap = row['vwap']
            
            debug_data["spot_vs_vwap"] = "ABOVE" if spot > vwap else "BELOW" if spot < vwap else "EQUAL"
            
            ema5 = row['ema5']
            ema13 = row['ema13']
            if ema5 > ema13 and spot > ema5:
                debug_data["ema_crossover"] = "BULLISH"
            elif ema5 < ema13 and spot < ema5:
                debug_data["ema_crossover"] = "BEARISH"
            else: 
                debug_data["ema_crossover"] = "NEUTRAL"
            
            rsi = row['rsi']
            if rsi > 60:
                debug_data["rsi_zone"] = "BULLISH"
            elif rsi < 40:
                debug_data["rsi_zone"] = "BEARISH"
            else:
                debug_data["rsi_zone"] = "NEUTRAL"
            
            if last_pcr > self.config.bullish_pcr_threshold:
                debug_data["pcr_signal"] = "BULLISH"
            elif last_pcr < self.config.bearish_pcr_threshold:
                debug_data["pcr_signal"] = "BEARISH"
            else:
                debug_data["pcr_signal"] = "NEUTRAL"
            
            bias, bullish_signals, bearish_signals = self._analyze_market(row, last_pcr)
            debug_data["bullish_signals"] = bullish_signals
            debug_data["bearish_signals"] = bearish_signals
            debug_data["market_bias"] = bias
            
            # Position management
            if self.active_position:
                pos = self.active_position
                debug_data["position_type"] = pos['option_type']
                debug_data["position_strike"] = pos['strike']
                debug_data["position_entry_price"] = pos['entry_price']
                
                exit_result = self._manage_position(row, debug_data)
                
                if exit_result:
                    exit_price, reason = exit_result
                    trade = self._execute_exit(exit_price, reason, 
                                               row['datetime'], row['close'])
                    debug_data["action"] = f"EXIT_{reason}"
                    debug_data["exit_reason"] = reason
                    debug_data["exit_price"] = exit_price
                    
                    if verbose:
                        emoji = "✅" if trade.is_winner else "❌"
                        print(f"  {emoji} {trade.option_type}@{trade.strike} ({trade.strike_type}) | "
                              f"₹{trade.pnl:+,.2f} | {reason}")
                else:
                    debug_data["action"] = "HOLD_POSITION"
            
            else:
                # Look for entry
                debug_data["entry_signal"] = ""
                debug_data["entry_blocked_reason"] = ""
                
                if not row['rsi_ready']: 
                    debug_data["entry_blocked_reason"] = "RSI_NOT_READY"
                    debug_data["action"] = "SKIP_RSI_WARMUP"
                
                elif in_cooldown: 
                    debug_data["entry_blocked_reason"] = "IN_COOLDOWN"
                    debug_data["action"] = "SKIP_COOLDOWN"
                
                elif bias == "NEUTRAL": 
                    debug_data["entry_blocked_reason"] = "NEUTRAL_BIAS"
                    debug_data["action"] = "SKIP_NEUTRAL"
                
                else:
                    signal = self._check_entry(row, bias)
                    
                    if signal is None:
                        if bias == "BULLISH":
                            if spot <= vwap: 
                                debug_data["entry_blocked_reason"] = "SPOT_NOT_ABOVE_VWAP"
                            else:
                                debug_data["entry_blocked_reason"] = f"RSI_{rsi:.1f}_NOT_IN_55-75"
                        else:
                            if spot >= vwap:
                                debug_data["entry_blocked_reason"] = "SPOT_NOT_BELOW_VWAP"
                            else: 
                                debug_data["entry_blocked_reason"] = f"RSI_{rsi:.1f}_NOT_IN_25-45"
                        debug_data["action"] = "SKIP_ENTRY_CONDITIONS"
                    
                    else:
                        debug_data["entry_signal"] = signal
                        
                        if self._execute_entry(row, signal, debug_data):
                            pos = self.active_position
                            debug_data["action"] = f"ENTRY_{pos['option_type']}_{pos['strike_type']}"
                            
                            if verbose: 
                                print(f"  🟢 ENTRY:  {pos['option_type']}@{pos['strike']} ({pos['strike_type']}) | "
                                      f"₹{pos['entry_price']:.2f} | Expiry: {pos['expiry']}")
                        else: 
                            debug_data["action"] = "SKIP_ENTRY_FAILED"
            
            # Log debug data
            if self.debug:
                self.debug_logger.log(debug_data)
        
        # Save last day
        if current_date: 
            self._save_daily(current_date, day_start_capital)
        
        # Close any open position
        if self.active_position: 
            last = df.iloc[-1]
            exit_price = self._get_current_option_price(last)
            if exit_price:
                self._execute_exit(exit_price, "END_OF_DATA", 
                                   last['datetime'], last['close'])
        
        # Print debug summary
        if self.debug:
            self.debug_logger.print_summary()
        
        # Print option fetcher stats
        self.option_fetcher.print_stats()
        
        # Calculate results
        self.results = self._calculate_results()
        return self.results
    
    def _calculate_results(self) -> Dict:
        """Calculate comprehensive results"""
        base_results = {
            "initial_capital": self.config.initial_capital,
            "final_capital": self.capital,
            "total_pnl": self.capital - self.config.initial_capital,
            "total_return_pct": (self.capital - self.config.initial_capital) / self.config.initial_capital * 100,
            "total_trades": len(self.trades),
            "winners": 0,
            "losers": 0,
            "win_rate": 0,
            "gross_profit": 0,
            "gross_loss": 0,
            "profit_factor": 0,
            "avg_win":  0,
            "avg_loss":  0,
            "max_drawdown_pct": 0,
            "sharpe_ratio": 0,
            "avg_hold_mins": 0,
            "trading_days": len(self.daily_stats),
            "best_trade": 0,
            "worst_trade": 0,
            "atm_trades": 0,
            "otm_trades": 0,
            "itm_trades": 0,
            "ce_trades": 0,
            "pe_trades": 0,
            "ce_pnl": 0,
            "pe_pnl":  0,
            "exit_reasons": {},
            "api_calls":  self.option_fetcher.api_calls,
            "cache_hits": self.option_fetcher.cache_hits,
        }
        
        if not self.trades:
            base_results["error"] = "No trades executed"
            return base_results
        
        winners = [t for t in self.trades if t.is_winner]
        losers = [t for t in self.trades if not t.is_winner]
        
        gross_profit = sum(t.pnl for t in winners) if winners else 0
        gross_loss = abs(sum(t.pnl for t in losers)) if losers else 0
        
        # Drawdown
        equity = [e[1] for e in self.equity_curve]
        if len(equity) > 0:
            peak = np.maximum.accumulate(equity)
            dd = (peak - equity) / peak * 100
            max_dd = np.max(dd)
        else:
            max_dd = 0
        
        # Sharpe
        if len(self.trades) > 1:
            rets = [t.pnl / self.config.initial_capital for t in self.trades]
            sharpe = np.mean(rets) / np.std(rets) * np.sqrt(252) if np.std(rets) > 0 else 0
        else:
            sharpe = 0
        
        return {
            "initial_capital": self.config.initial_capital,
            "final_capital": self.capital,
            "total_pnl": sum(t.pnl for t in self.trades),
            "total_return_pct": (self.capital - self.config.initial_capital) / self.config.initial_capital * 100,
            "total_trades":  len(self.trades),
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": len(winners) / len(self.trades) * 100,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            "avg_win":  np.mean([t.pnl for t in winners]) if winners else 0,
            "avg_loss": np.mean([t.pnl for t in losers]) if losers else 0,
            "max_drawdown_pct":  max_dd,
            "sharpe_ratio": sharpe,
            "avg_hold_mins": np.mean([t.hold_time_minutes for t in self.trades]),
            "trading_days": len(self.daily_stats),
            "best_trade": max(t.pnl for t in self.trades),
            "worst_trade":  min(t.pnl for t in self.trades),
            "atm_trades": len([t for t in self.trades if t.strike_type == 'ATM']),
            "otm_trades": len([t for t in self.trades if t.strike_type == 'OTM']),
            "itm_trades": len([t for t in self.trades if t.strike_type == 'ITM']),
            "ce_trades": len([t for t in self.trades if t.option_type == 'CE']),
            "pe_trades":  len([t for t in self.trades if t.option_type == 'PE']),
            "ce_pnl":  sum(t.pnl for t in self.trades if t.option_type == 'CE'),
            "pe_pnl": sum(t.pnl for t in self.trades if t.option_type == 'PE'),
            "exit_reasons": pd.Series([t.exit_reason for t in self.trades]).value_counts().to_dict(),
            "api_calls": self.option_fetcher.api_calls,
            "cache_hits": self.option_fetcher.cache_hits,
        }
    
    def print_results(self):
        """Print formatted results"""
        if not self.results:
            print("No results to display")
            return
        
        r = self.results
        
        print("\n" + "=" * 65)
        print("📊 BACKTEST RESULTS V3 (Real Option Data)")
        print("=" * 65)
        
        print("\n💰 CAPITAL")
        print("-" * 40)
        print(f"  Initial:          ₹{r['initial_capital']:>12,.2f}")
        print(f"  Final:           ₹{r['final_capital']:>12,.2f}")
        print(f"  Total P&L:       ₹{r['total_pnl']:>+12,.2f}")
        print(f"  Return:           {r['total_return_pct']:>+12.2f}%")
        
        print("\n📈 TRADES")
        print("-" * 40)
        print(f"  Total:            {r['total_trades']:>12}")
        print(f"  Winners:         {r['winners']:>12}")
        print(f"  Losers:          {r['losers']:>12}")
        print(f"  Win Rate:        {r['win_rate']:>11.1f}%")
        
        print("\n🎯 STRIKE TYPES")
        print("-" * 40)
        print(f"  ATM Trades:      {r['atm_trades']:>12}")
        print(f"  OTM Trades:      {r['otm_trades']:>12}")
        print(f"  ITM Trades:      {r['itm_trades']:>12}")
        
        print("\n💵 PROFIT")
        print("-" * 40)
        print(f"  Gross Profit:    ₹{r['gross_profit']:>12,.2f}")
        print(f"  Gross Loss:       ₹{r['gross_loss']:>12,.2f}")
        print(f"  Profit Factor:   {r['profit_factor']:>12.2f}")
        print(f"  Avg Win:         ₹{r['avg_win']:>12,.2f}")
        print(f"  Avg Loss:        ₹{r['avg_loss']:>12,.2f}")
        
        print("\n📉 RISK")
        print("-" * 40)
        print(f"  Max Drawdown:    {r['max_drawdown_pct']:>11.2f}%")
        print(f"  Sharpe Ratio:    {r['sharpe_ratio']:>12.2f}")
        
        print("\n⏱️ TIMING")
        print("-" * 40)
        print(f"  Avg Hold Time:   {r['avg_hold_mins']:>10.1f} min")
        print(f"  Trading Days:    {r['trading_days']:>12}")
        
        print("\n🎯 EXIT REASONS")
        print("-" * 40)
        for reason, count in r['exit_reasons'].items():
            print(f"  {reason}:  {count}")
        
        print("\n📞 CE vs PE")
        print("-" * 40)
        print(f"  CE Trades:       {r['ce_trades']:>12}")
        print(f"  CE P&L:          ₹{r['ce_pnl']:>+12,.2f}")
        print(f"  PE Trades:       {r['pe_trades']:>12}")
        print(f"  PE P&L:          ₹{r['pe_pnl']:>+12,.2f}")
        
        print("\n🏆 EXTREMES")
        print("-" * 40)
        print(f"  Best Trade:      ₹{r['best_trade']:>+12,.2f}")
        print(f"  Worst Trade:     ₹{r['worst_trade']:>+12,.2f}")
        
        print("\n📡 API USAGE")
        print("-" * 40)
        print(f"  API Calls:       {r['api_calls']:>12}")
        print(f"  Cache Hits:      {r['cache_hits']:>12}")
        total = r['api_calls'] + r['cache_hits']
        hit_rate = (r['cache_hits'] / total * 100) if total > 0 else 0
        print(f"  Cache Hit Rate:  {hit_rate:>11.1f}%")
        
        print("=" * 65)
    
    def export_trades(self, filepath:  str):
        """Export trades to CSV"""
        if not self.trades:
            print("No trades to export")
            return
        
        data = []
        for t in self.trades:
            data.append({
                'entry_time': t.entry_time,
                'exit_time': t.exit_time,
                'option_type': t.option_type,
                'strike': t.strike,
                'strike_type': t.strike_type,
                'expiry': t.expiry,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'entry_spot': t.entry_spot,
                'exit_spot': t.exit_spot,
                'pnl_points': t.pnl_points,
                'pnl':  t.pnl,
                'exit_reason': t.exit_reason,
                'hold_time_minutes': t.hold_time_minutes,
                'is_winner': t.is_winner
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
        print(f"✅ Trades exported:  {filepath}")
    
    def export_equity_curve(self, filepath: str):
        """Export equity curve to CSV"""
        df = pd.DataFrame(self.equity_curve, columns=['datetime', 'capital'])
        df.to_csv(filepath, index=False)
        print(f"✅ Equity curve exported: {filepath}")