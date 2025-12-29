"""
NIFTY OPTIONS BACKTESTER - GROWW API INTEGRATED
================================================
Uses historical data from Groww API
Reuses indicator logic from claude_groww_data_pipeline.py
Mirrors trading logic from claud_nifty_algo_bot.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field 
from typing import List, Dict, Optional, Tuple
import os
import sys
from claude_backtest_debug_logger import BacktestDebugLogger

# Import your existing modules
try:
    from growwapi import GrowwAPI
except ImportError:
    print("⚠️ growwapi not found.Install it or ensure it's in your path.")


# ============================================================
# CONFIGURATION
# ============================================================

@dataclass
class BacktestConfig: 
    """Configuration matching your live bot settings"""
    # Capital & Risk
    initial_capital: float = 10000.0
    lot_size: int = 75
    daily_loss_limit_pct: float = 0.10  # 10%
    
    # Entry/Exit Parameters (from your bot)
    target_points: float = 10.0  # Based on target_points/2 in your code
    stop_loss_points: float = 5.0  # Based on stop_loss_points/2 in your code
    trailing_stop_activation: float = 0.50
    trailing_stop_distance: float = 0.15
    max_hold_minutes:  int = 30
    cooldown_seconds: int = 60
    
    # Strategy Parameters
    bullish_rsi_min: float = 55.0
    bullish_rsi_max: float = 75.0
    bearish_rsi_min: float = 25.0
    bearish_rsi_max: float = 45.0
    bullish_pcr_threshold: float = 1.1
    bearish_pcr_threshold:  float = 0.9
    min_signals_required: int = 3
    
    # Indicator Periods
    rsi_period: int = 14
    ema_fast:  int = 5
    ema_slow: int = 13
    rsi_warmup_candles: int = 15
    
    # Transaction Costs
    brokerage_per_trade: float = 20.0  # ₹20 per trade
    slippage_points: float = 0.5  # 0.5 points slippage
    
    # Data Settings
    use_actual_option_prices: bool = True  # Use real option data if available


@dataclass
class Trade:
    """Single trade record"""
    entry_time: datetime
    exit_time: Optional[datetime]
    option_type: str
    strike: int
    entry_price: float
    exit_price:  float = 0.0
    peak_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""
    lot_size: int = 75
    brokerage: float = 0.0
    
    @property
    def is_winner(self) -> bool:
        return self.pnl > 0
    
    @property
    def hold_time_minutes(self) -> float:
        if self.exit_time:
            return (self.exit_time - self.entry_time).total_seconds() / 60
        return 0


# ============================================================
# INDICATOR ENGINE (From your claude_groww_data_pipeline.py)
# ============================================================

class IndicatorEngine:
    """
    Replicates indicator calculations from GrowwDataEngine
    """
    
    @staticmethod
    def calculate_rsi(close_prices: pd.Series, period: int = 14) -> pd.Series:
        """
        RSI using Wilder's Smoothing - EXACT copy from your code
        """
        delta = close_prices.diff()
        gains = delta.where(delta > 0, 0.0)
        losses = (-delta.where(delta < 0, 0.0))
        
        alpha = 1.0 / period
        avg_gain = gains.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
        avg_loss = losses.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        rsi = rsi.fillna(50.0)
        rsi = rsi.clip(0, 100)
        
        return rsi
    
    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.Series:
        """
        Full day VWAP with Typical Price - EXACT copy from your code
        VWAP = Σ(Typical Price × Volume) / Σ(Volume)
        """
        df_calc = df.copy()
        df_calc['typical_price'] = (df_calc['high'] + df_calc['low'] + df_calc['close']) / 3
        df_calc['date'] = pd.to_datetime(df_calc['datetime']).dt.date
        
        # Calculate cumulative values per day
        df_calc['tp_vol'] = df_calc['typical_price'] * df_calc['volume']
        df_calc['cum_tp_vol'] = df_calc.groupby('date')['tp_vol'].cumsum()
        df_calc['cum_vol'] = df_calc.groupby('date')['volume'].cumsum()
        
        # VWAP = cumulative(TP * Vol) / cumulative(Vol)
        vwap = df_calc['cum_tp_vol'] / df_calc['cum_vol'].replace(0, np.nan)
        
        return vwap.ffill()
    
    @staticmethod
    def calculate_ema(close_prices: pd.Series, period: int) -> pd.Series:
        """EMA calculation"""
        return close_prices.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_atm_strike(spot:  float, interval: int = 50) -> int:
        """ATM strike calculation - EXACT copy from your code"""
        return int(round(spot / interval) * interval)
    
    @staticmethod
    def estimate_option_premium(spot: float, strike:  int, option_type: str,
                                days_to_expiry: float = 7, iv:  float = 0.15) -> float:
        """
        Estimate ATM option premium when actual data not available
        Uses simplified Black-Scholes approximation
        """
        t = days_to_expiry / 365
        premium = 0.4 * spot * iv * np.sqrt(t)
        
        # Moneyness adjustment
        if option_type == 'CE':
            intrinsic = max(0, spot - strike)
        else:
            intrinsic = max(0, strike - spot)
        
        return max(premium + intrinsic * 0.5, 5)  # Minimum ₹5


# ============================================================
# MAIN BACKTESTER
# ============================================================

class NiftyGrowwBacktester:
    """
    Backtester integrated with Groww API
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None, 
                 config: BacktestConfig = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.config = config or BacktestConfig()
        self.groww = None
        
        # Connect to API if credentials provided
        if api_key and api_secret:
            self._connect()
        
        # State
        self.capital = self.config.initial_capital
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.daily_stats: List[Dict] = []
        
        self.active_position: Optional[Dict] = None
        self.last_exit_time: Optional[datetime] = None
        self.daily_pnl = 0.0
        
        # Indicator engine
        self.indicators = IndicatorEngine()
        
        # Option price cache
        self.option_data_cache: Dict[str, pd.DataFrame] = {}
        
        # Results
        self.results: Dict = {}
    
    def _connect(self):
        """Connect to Groww API"""
        try: 
            token = GrowwAPI.get_access_token(
                api_key=self.api_key,
                secret=self.api_secret
            )
            self.groww = GrowwAPI(token)
            print("✅ Connected to Groww API")
        except Exception as e: 
            print(f"⚠️ API Connection failed: {e}")
            print("   Will use estimated option prices")
    
    def fetch_historical_data(self, start_date: str, end_date:  str,
                              save_path: str = None) -> pd.DataFrame:
        """
        Fetch historical NIFTY spot data from Groww API
        """
        if not self.groww:
            raise ValueError("Not connected to Groww API.Provide credentials or load data from CSV.")
        
        print(f"\n📥 Fetching NIFTY data:  {start_date} to {end_date}")
        
        all_data = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current <= end:
            if current.weekday() >= 5:  # Skip weekends
                current += timedelta(days=1)
                continue
            
            try:
                day_start = current.replace(hour=9, minute=15, second=0)
                day_end = current.replace(hour=15, minute=30, second=0)
                
                resp = self.groww.get_historical_candles(
                    "NSE", "CASH", "NSE-NIFTY",
                    day_start.strftime("%Y-%m-%d %H:%M:%S"),
                    day_end.strftime("%Y-%m-%d %H:%M:%S"),
                    "1minute"
                )
                
                if resp and 'candles' in resp: 
                    df_day = pd.DataFrame(resp['candles'])
                    all_data.append(df_day)
                    print(f"   ✓ {current.strftime('%Y-%m-%d')}: {len(df_day)} candles")
                
                import time
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e: 
                print(f"   ⚠️ {current.strftime('%Y-%m-%d')}: {e}")
            
            current += timedelta(days=1)
        
        if not all_data: 
            raise ValueError("No data fetched!")
        
        df = pd.concat(all_data, ignore_index=True)
        cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) >= 7:
            cols.append('oi')
        df.columns = cols[:len(df.columns)]
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime').reset_index(drop=True)
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        if save_path:
            df.to_csv(save_path, index=False)
            print(f"✅ Data saved to: {save_path}")
        
        print(f"✅ Total:  {len(df):,} candles")
        return df
    
    def load_data(self, filepath: str) -> pd.DataFrame:
        """Load data from CSV file"""
        print(f"📂 Loading:  {filepath}")
        
        df = pd.read_csv(filepath)
        df.columns = df.columns.str.lower().str.strip()
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        if 'volume' not in df.columns:
            df['volume'] = 100000
        
        df = df.sort_values('datetime').reset_index(drop=True)
        
        print(f"✅ Loaded {len(df):,} candles")
        print(f"   Range: {df['datetime'].min()} to {df['datetime'].max()}")
        
        return df
    
    def prepare_indicators(self, df:  pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators"""
        print("📊 Calculating indicators...")
        
        df = df.copy()
        
        # RSI
        df['rsi'] = self.indicators.calculate_rsi(df['close'], self.config.rsi_period)
        
        # EMAs
        df['ema5'] = self.indicators.calculate_ema(df['close'], self.config.ema_fast)
        df['ema13'] = self.indicators.calculate_ema(df['close'], self.config.ema_slow)
        
        # VWAP
        # Use VWAP from CSV if it exists (already calculated from futures)
        if 'vwap' in df.columns and df['vwap'].notna().any():
            print("   ℹ️ Using VWAP from CSV (futures-based)")
        else:
            df['vwap'] = self.indicators.calculate_vwap(df)
        
        # ATM Strike
        df['atm_strike'] = df['close'].apply(self.indicators.calculate_atm_strike)
        
        # Simulated PCR (based on price momentum)
        # PCR not available in historical data - set to neutral (won't affect signals)
        df['pcr'] = 1.0
        
        # RSI warmup flag
        df['rsi_ready'] = df.index >= self.config.rsi_warmup_candles
        
        # Market hours filter
        df['in_market'] = df['datetime'].apply(self._in_market_hours)
        
        print("✅ Indicators ready")
        return df
    
    def _in_market_hours(self, dt: datetime) -> bool:
        """Check if within trading hours"""
        market_open = dt.replace(hour=9, minute=15, second=0)
        market_close = dt.replace(hour=15, minute=25, second=0)
        return market_open <= dt <= market_close
    
    def _analyze_market(self, row: pd.Series) -> str:
        """
        Analyze market conditions - MIRRORS your analyze_market_conditions()
        """
        spot = row['close']
        vwap = row['vwap']
        rsi = row['rsi']
        ema5 = row['ema5']
        ema13 = row['ema13']
        pcr = row['pcr']
        
        if pd.isna(vwap) or vwap == 0:
            return 'NEUTRAL'
        
        bullish = 0
        bearish = 0
        
        # 1.VWAP (2 points)
        if spot > vwap: 
            bullish += 2
        elif spot < vwap: 
            bearish += 2
        
        # 2.EMA Crossover (1 point)
        if ema5 > ema13 and spot > ema5:
            bullish += 1
        elif ema5 < ema13 and spot < ema5:
            bearish += 1
        
        # 3.RSI (1 point)
        if rsi > 60:
            bullish += 1
        elif rsi < 40:
            bearish += 1
        
        # 4.PCR (1 point)
        # if pcr > self.config.bullish_pcr_threshold:
        #     bullish += 1
        # elif pcr < self.config.bearish_pcr_threshold:
        #     bearish += 1
        
        if bullish >= self.config.min_signals_required: 
            return 'BULLISH'
        elif bearish >= self.config.min_signals_required: 
            return 'BEARISH'
        
        return 'NEUTRAL'
    
    def _check_entry(self, row: pd.Series, bias: str) -> Optional[str]:
        """
        Check entry conditions - MIRRORS your check_entry_conditions()
        """
        # Cooldown
        if self.last_exit_time: 
            elapsed = (row['datetime'] - self.last_exit_time).total_seconds()
            if elapsed < self.config.cooldown_seconds: 
                return None
        
        if bias == 'NEUTRAL' or not row['rsi_ready']: 
            return None
        
        spot = row['close']
        vwap = row['vwap']
        rsi = row['rsi']
        
        if bias == 'BULLISH':
            if spot <= vwap: 
                return None
            if not (self.config.bullish_rsi_min <= rsi <= self.config.bullish_rsi_max):
                return None
            return 'BUY_CE'
        
        elif bias == 'BEARISH': 
            if spot >= vwap: 
                return None
            if not (self.config.bearish_rsi_min <= rsi <= self.config.bearish_rsi_max):
                return None
            return 'BUY_PE'
        
        return None
    
    def _get_option_price(self, row:  pd.Series, strike: int, 
                          option_type: str, entry_spot: float = None) -> float:
        """
        Get option price - uses actual data if available, else estimates
        """
        spot = row['close']
        
        # If we have actual option data cached, use it
        cache_key = f"{strike}{option_type}"
        if cache_key in self.option_data_cache: 
            opt_df = self.option_data_cache[cache_key]
            match = opt_df[opt_df['datetime'] == row['datetime']]
            if len(match) > 0:
                return float(match['close'].iloc[0])
        
        # Otherwise, estimate using delta simulation
        if entry_spot is not None:
            # Simulate option price change based on underlying movement
            spot_change = spot - entry_spot
            delta = 0.5  # ATM delta approximation
            
            if option_type == 'CE':
                price_change = spot_change * delta
            else: 
                price_change = -spot_change * delta
            
            return price_change  # Return just the change
        
        # New position - estimate full premium
        return self.indicators.estimate_option_premium(spot, strike, option_type)
    
    def _execute_entry(self, row:  pd.Series, signal: str) -> bool:
        """Execute trade entry"""
        spot = row['close']
        strike = row['atm_strike']
        option_type = 'CE' if signal == 'BUY_CE' else 'PE'
        
        entry_price = self._get_option_price(row, strike, option_type)
        
        # Affordability check
        cost = entry_price * self.config.lot_size
        if cost > self.capital * 0.7: 
            return False
        
        self.active_position = {
            'entry_time': row['datetime'],
            'option_type': option_type,
            'strike': strike,
            'entry_price': entry_price,
            'entry_spot': spot,
            'peak':  entry_price,
            'target': entry_price + self.config.target_points,
            'stop_loss': entry_price - self.config.stop_loss_points,
            'trailing_active': False
        }
        
        return True
    
    def _manage_position(self, row: pd.Series) -> Optional[Tuple[float, str]]:
        """Manage active position - returns (exit_price, reason) if should exit"""
        if not self.active_position:
            return None
        
        pos = self.active_position
        spot = row['close']
        
        # Calculate current option price
        price_change = self._get_option_price(
            row, pos['strike'], pos['option_type'], pos['entry_spot']
        )
        current_price = pos['entry_price'] + price_change
        current_price = max(current_price, 1)  # Minimum price
        
        # Update peak
        if current_price > pos['peak']: 
            pos['peak'] = current_price
        
        entry = pos['entry_price']
        peak = pos['peak']
        target = pos['target']
        stop = pos['stop_loss']
        
        # Exit checks
        reason = None
        
        # 1.Target
        if current_price >= target: 
            reason = "TARGET"
        
        # 2.Stop Loss
        elif current_price <= stop:
            reason = "STOP_LOSS"
        
        # 3.Trailing Stop
        else:
            profit_pct = (current_price - entry) / entry
            target_pct = (target - entry) / entry
            
            if profit_pct >= target_pct * self.config.trailing_stop_activation:
                if not pos['trailing_active']:
                    pos['trailing_active'] = True
                
                trail_stop = peak * (1 - self.config.trailing_stop_distance)
                if current_price <= trail_stop: 
                    reason = "TRAILING_STOP"
        
        # 4.Time Exit
        hold_mins = (row['datetime'] - pos['entry_time']).total_seconds() / 60
        if hold_mins >= self.config.max_hold_minutes: 
            reason = "TIME_EXIT"
        
        if reason:
            return (current_price, reason)
        
        return None
    
    def _execute_exit(self, exit_price: float, reason:  str, 
                      exit_time: datetime) -> Trade:
        """Execute exit and record trade"""
        pos = self.active_position
        
        # Apply slippage
        exit_price -= self.config.slippage_points
        
        # Calculate P&L
        pnl_points = exit_price - pos['entry_price']
        pnl = pnl_points * self.config.lot_size
        
        # Deduct brokerage (entry + exit)
        brokerage = self.config.brokerage_per_trade * 2
        pnl -= brokerage
        
        pnl_pct = (pnl_points / pos['entry_price']) * 100 if pos['entry_price'] > 0 else 0
        
        trade = Trade(
            entry_time=pos['entry_time'],
            exit_time=exit_time,
            option_type=pos['option_type'],
            strike=pos['strike'],
            entry_price=pos['entry_price'],
            exit_price=exit_price,
            peak_price=pos['peak'],
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=reason,
            lot_size=self.config.lot_size,
            brokerage=brokerage
        )
        
        # Update state
        self.capital += pnl
        self.daily_pnl += pnl
        self.trades.append(trade)
        self.equity_curve.append((exit_time, self.capital))
        self.last_exit_time = exit_time
        self.active_position = None
        
        return trade
    
    def run(self, df: pd.DataFrame, verbose: bool = True, debug: bool = True) -> Dict:
        """Run the backtest with optional debug logging"""
        print("\n" + "=" * 60)
        print("🚀 STARTING BACKTEST")
        print("=" * 60)
        print(f"Capital: ₹{self.config.initial_capital:,.2f}")
        print(f"Period: {df['datetime'].min()} to {df['datetime'].max()}")
        print(f"Debug Mode: {'ON' if debug else 'OFF'}")
        print("=" * 60)
        
        # Initialize debug logger
        debug_logger = BacktestDebugLogger() if debug else None
        
        # Reset
        self.capital = self.config.initial_capital
        self.trades = []
        self.equity_curve = [(df['datetime'].iloc[0], self.capital)]
        self.daily_stats = []
        self.active_position = None
        self.last_exit_time = None
        
        current_date = None
        day_start_capital = self.capital
        
        for idx, row in df.iterrows():
            # Build debug data
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
                "pcr": row['pcr'],
                "rsi_ready":  row['rsi_ready'],
                "in_market": row['in_market'],
                "capital": self.capital,
                "daily_pnl": self.daily_pnl if hasattr(self, 'daily_pnl') else 0,
                "has_position": self.active_position is not None,
                "action": "SKIP_NOT_MARKET_HOURS",
            }
            
            if not row['in_market']: 
                if debug: 
                    debug_logger.log(debug_data)
                continue
            
            # Get current time
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
                
                if verbose and idx % 500 == 0:
                    print(f"📅 {current_date} | Capital: ₹{self.capital:,.2f}")
            
            debug_data["daily_pnl"] = self.daily_pnl
            
            # Check cooldown
            in_cooldown = False
            if self.last_exit_time: 
                elapsed = (row['datetime'] - self.last_exit_time).total_seconds()
                in_cooldown = elapsed < self.config.cooldown_seconds
            debug_data["in_cooldown"] = in_cooldown
            
            # Daily loss limit
            if abs(self.daily_pnl) >= self.config.initial_capital * self.config.daily_loss_limit_pct:
                debug_data["action"] = "SKIP_DAILY_LOSS_LIMIT"
                if debug:
                    debug_logger.log(debug_data)
                continue
            
            # Force exit at 15:25
            if self.active_position and current_time >= force_exit_time: 
                price_change = self._get_option_price(
                    row,
                    self.active_position['strike'],
                    self.active_position['option_type'],
                    self.active_position['entry_spot']
                )
                current_price = self.active_position['entry_price'] + price_change
                current_price = max(current_price, 1)
                trade = self._execute_exit(current_price, "EOD_EXIT", row['datetime'])
                
                debug_data["action"] = "EXIT_EOD"
                debug_data["exit_reason"] = "EOD_EXIT"
                debug_data["position_current_price"] = current_price
                debug_data["position_pnl"] = trade.pnl
                
                if verbose: 
                    emoji = "✅" if trade.is_winner else "❌"
                    print(f"  {emoji} {trade.option_type}@{trade.strike} | ₹{trade.pnl:+,.2f} | EOD_EXIT")
                
                if debug: 
                    debug_logger.log(debug_data)
                continue
            
            # No new entries after 15:20
            if current_time >= no_entry_time and not self.active_position:
                debug_data["action"] = "SKIP_AFTER_1520"
                if debug:
                    debug_logger.log(debug_data)
                continue
            
            # Analyze market
            spot = row['fut_close'] if 'fut_close' in row and pd.notna(row['fut_close']) else row['close']
            vwap = row['vwap']
            rsi = row['rsi']
            ema5 = row['ema5']
            ema13 = row['ema13']
            pcr = row['pcr']
            
            # Spot vs VWAP
            debug_data["spot_vs_vwap"] = "ABOVE" if spot > vwap else "BELOW" if spot < vwap else "EQUAL"
            
            # EMA Crossover
            if ema5 > ema13 and spot > ema5:
                debug_data["ema_crossover"] = "BULLISH"
            elif ema5 < ema13 and spot < ema5:
                debug_data["ema_crossover"] = "BEARISH"
            else:
                debug_data["ema_crossover"] = "NEUTRAL"
            
            # RSI Zone
            if rsi > 60:
                debug_data["rsi_zone"] = "BULLISH"
            elif rsi < 40:
                debug_data["rsi_zone"] = "BEARISH"
            else:
                debug_data["rsi_zone"] = "NEUTRAL"
            
            # PCR Signal
            # if pcr > self.config.bullish_pcr_threshold:
            #     debug_data["pcr_signal"] = "BULLISH"
            # elif pcr < self.config.bearish_pcr_threshold:
            #     debug_data["pcr_signal"] = "BEARISH"
            # else:
            #     debug_data["pcr_signal"] = "NEUTRAL"
            
            # Count signals
            bullish_signals = 0
            bearish_signals = 0
            
            if spot > vwap: 
                bullish_signals += 2
            elif spot < vwap: 
                bearish_signals += 2
            
            if ema5 > ema13 and spot > ema5:
                bullish_signals += 1
            elif ema5 < ema13 and spot < ema5:
                bearish_signals += 1
            
            if rsi > 60:
                bullish_signals += 1
            elif rsi < 40:
                bearish_signals += 1
            
            # if pcr > self.config.bullish_pcr_threshold:
            #     bullish_signals += 1
            # elif pcr < self.config.bearish_pcr_threshold: 
            #     bearish_signals += 1
            
            # PCR not used in backtesting (no historical option chain data)
            debug_data["pcr_signal"] = "NOT_USED"
            
            debug_data["bullish_signals"] = bullish_signals
            debug_data["bearish_signals"] = bearish_signals
            
            # Market bias
            if bullish_signals >= self.config.min_signals_required:
                market_bias = "BULLISH"
            elif bearish_signals >= self.config.min_signals_required:
                market_bias = "BEARISH"
            else:
                market_bias = "NEUTRAL"
            
            debug_data["market_bias"] = market_bias
            
            # Position management
            if self.active_position: 
                pos = self.active_position
                debug_data["position_type"] = pos['option_type']
                debug_data["position_strike"] = pos['strike']
                debug_data["position_entry_price"] = pos['entry_price']
                
                price_change = self._get_option_price(
                    row, pos['strike'], pos['option_type'], pos['entry_spot']
                )
                current_price = pos['entry_price'] + price_change
                current_price = max(current_price, 1)
                
                debug_data["position_current_price"] = current_price
                debug_data["position_pnl"] = (current_price - pos['entry_price']) * self.config.lot_size
                debug_data["position_pnl_pct"] = (current_price - pos['entry_price']) / pos['entry_price'] * 100
                
                exit_result = self._manage_position(row)
                if exit_result: 
                    price, reason = exit_result
                    trade = self._execute_exit(price, reason, row['datetime'])
                    
                    debug_data["action"] = f"EXIT_{reason}"
                    debug_data["exit_reason"] = reason
                    
                    if verbose: 
                        emoji = "✅" if trade.is_winner else "❌"
                        print(f"  {emoji} {trade.option_type}@{trade.strike} | ₹{trade.pnl:+,.2f} | {reason}")
                else:
                    debug_data["action"] = "HOLD_POSITION"
            
            else:
                # Look for entry
                debug_data["entry_signal"] = None
                debug_data["entry_blocked_reason"] = ""
                
                # Check entry conditions
                if market_bias == "NEUTRAL":
                    debug_data["entry_blocked_reason"] = "NEUTRAL_BIAS"
                    debug_data["action"] = "SKIP_NEUTRAL"
                
                elif not row['rsi_ready']: 
                    debug_data["entry_blocked_reason"] = "RSI_NOT_READY"
                    debug_data["action"] = "SKIP_RSI_WARMUP"
                
                elif in_cooldown: 
                    debug_data["entry_blocked_reason"] = "IN_COOLDOWN"
                    debug_data["action"] = "SKIP_COOLDOWN"
                
                elif market_bias == "BULLISH":
                    # Check bullish entry conditions
                    if spot <= vwap: 
                        debug_data["entry_blocked_reason"] = "SPOT_NOT_ABOVE_VWAP"
                        debug_data["action"] = "SKIP_VWAP_CHECK"
                    elif rsi < self.config.bullish_rsi_min or rsi > self.config.bullish_rsi_max: 
                        debug_data["entry_blocked_reason"] = f"RSI_{rsi:.1f}_NOT_IN_55-75"
                        debug_data["action"] = "SKIP_RSI_RANGE"
                    else:
                        debug_data["entry_signal"] = "BUY_CE"
                        if self._execute_entry(row, "BUY_CE"):
                            debug_data["action"] = "ENTRY_CE"
                            debug_data["position_type"] = "CE"
                            debug_data["position_strike"] = self.active_position['strike']
                            debug_data["position_entry_price"] = self.active_position['entry_price']
                            
                            if verbose:
                                pos = self.active_position
                                print(f"  🟢 ENTRY: {pos['option_type']}@{pos['strike']} | ₹{pos['entry_price']:.2f}")
                        else:
                            debug_data["entry_blocked_reason"] = "ENTRY_EXECUTE_FAILED"
                            debug_data["action"] = "SKIP_ENTRY_FAILED"
                
                elif market_bias == "BEARISH": 
                    # Check bearish entry conditions
                    if spot >= vwap:
                        debug_data["entry_blocked_reason"] = "SPOT_NOT_BELOW_VWAP"
                        debug_data["action"] = "SKIP_VWAP_CHECK"
                    elif rsi < self.config.bearish_rsi_min or rsi > self.config.bearish_rsi_max:
                        debug_data["entry_blocked_reason"] = f"RSI_{rsi:.1f}_NOT_IN_25-45"
                        debug_data["action"] = "SKIP_RSI_RANGE"
                    else: 
                        debug_data["entry_signal"] = "BUY_PE"
                        if self._execute_entry(row, "BUY_PE"):
                            debug_data["action"] = "ENTRY_PE"
                            debug_data["position_type"] = "PE"
                            debug_data["position_strike"] = self.active_position['strike']
                            debug_data["position_entry_price"] = self.active_position['entry_price']
                            
                            if verbose: 
                                pos = self.active_position
                                print(f"  🟢 ENTRY: {pos['option_type']}@{pos['strike']} | ₹{pos['entry_price']:.2f}")
                        else: 
                            debug_data["entry_blocked_reason"] = "ENTRY_EXECUTE_FAILED"
                            debug_data["action"] = "SKIP_ENTRY_FAILED"
            
            # Log debug data
            if debug: 
                debug_logger.log(debug_data)
        
        # Save last day
        if current_date:
            self._save_daily(current_date, day_start_capital)
        
        # Close any remaining open position
        if self.active_position: 
            last = df.iloc[-1]
            price = self.active_position['entry_price']
            self._execute_exit(price, "END_OF_DATA", last['datetime'])
        
        # Print debug summary
        if debug:
            debug_logger.print_summary()
        
        self.results = self._calculate_results()
        return self.results
    
    def _save_daily(self, date, start_capital:  float):
        """Save daily stats"""
        day_trades = [t for t in self.trades if t.entry_time.date() == date]
        self.daily_stats.append({
            'date': str(date),
            'trades': len(day_trades),
            'wins': sum(1 for t in day_trades if t.is_winner),
            'pnl': sum(t.pnl for t in day_trades),
            'start':  start_capital,
            'end': self.capital
        })
    
    def _calculate_results(self) -> Dict: 
        """Calculate comprehensive results"""
        
        # Base results (always included)
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
            "total_brokerage":  0,
            "ce_trades": 0,
            "pe_trades": 0,
            "ce_pnl": 0,
            "pe_pnl":  0,
            "exit_reasons": {},
            "trading_days": len(self.daily_stats),
            "best_trade": 0,
            "worst_trade": 0,
        }
        
        # If no trades, return base results
        if not self.trades:
            base_results["error"] = "No trades executed"
            return base_results
        
        # Calculate full results
        total = len(self.trades)
        winners = [t for t in self.trades if t.is_winner]
        losers = [t for t in self.trades if not t.is_winner]
        
        total_pnl = sum(t.pnl for t in self.trades)
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
            "total_pnl": total_pnl,
            "total_return_pct": (self.capital - self.config.initial_capital) / self.config.initial_capital * 100,
            "total_trades":  total,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": len(winners) / total * 100 if total > 0 else 0,
            "gross_profit":  gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            "avg_win":  np.mean([t.pnl for t in winners]) if winners else 0,
            "avg_loss": np.mean([t.pnl for t in losers]) if losers else 0,
            "max_drawdown_pct": max_dd,
            "sharpe_ratio": sharpe,
            "avg_hold_mins": np.mean([t.hold_time_minutes for t in self.trades]),
            "total_brokerage": sum(t.brokerage for t in self.trades),
            "ce_trades":  len([t for t in self.trades if t.option_type == 'CE']),
            "pe_trades": len([t for t in self.trades if t.option_type == 'PE']),
            "ce_pnl": sum(t.pnl for t in self.trades if t.option_type == 'CE'),
            "pe_pnl": sum(t.pnl for t in self.trades if t.option_type == 'PE'),
            "exit_reasons": pd.Series([t.exit_reason for t in self.trades]).value_counts().to_dict(),
            "trading_days": len(self.daily_stats),
            "best_trade": max(t.pnl for t in self.trades),
            "worst_trade":  min(t.pnl for t in self.trades),
        }
    
    def print_results(self):
        """Print formatted results"""
        r = self.results
        
        print("\n" + "=" * 65)
        print("📊 BACKTEST RESULTS")
        print("=" * 65)
        
        print("\n💰 CAPITAL")
        print("-" * 40)
        print(f"  Initial:         ₹{r['initial_capital']:>12,.2f}")
        print(f"  Final:          ₹{r['final_capital']:>12,.2f}")
        print(f"  Total P&L:      ₹{r['total_pnl']:>+12,.2f}")
        print(f"  Return:          {r['total_return_pct']:>+11.2f}%")
        
        print("\n📈 TRADES")
        print("-" * 40)
        print(f"  Total:            {r['total_trades']:>12}")
        print(f"  Winners:          {r['winners']:>12}")
        print(f"  Losers:           {r['losers']:>12}")
        print(f"  Win Rate:         {r['win_rate']:>11.1f}%")
        
        print("\n💵 PROFIT")
        print("-" * 40)
        print(f"  Gross Profit:   ₹{r['gross_profit']:>12,.2f}")
        print(f"  Gross Loss:      ₹{r['gross_loss']:>12,.2f}")
        print(f"  Profit Factor:   {r['profit_factor']:>12.2f}")
        print(f"  Avg Win:        ₹{r['avg_win']:>12,.2f}")
        print(f"  Avg Loss:       ₹{r['avg_loss']:>12,.2f}")
        
        print("\n📉 RISK")
        print("-" * 40)
        print(f"  Max Drawdown:    {r['max_drawdown_pct']:>11.2f}%")
        print(f"  Sharpe Ratio:    {r['sharpe_ratio']:>12.2f}")
        
        print("\n⏱️ TIMING")
        print("-" * 40)
        print(f"  Avg Hold Time:   {r['avg_hold_mins']:>11.1f} min")
        print(f"  Trading Days:    {r['trading_days']:>12}")
        
        print("\n🎯 EXIT REASONS")
        print("-" * 40)
        for reason, count in r['exit_reasons'].items():
            pct = count / r['total_trades'] * 100
            print(f"  {reason: <18} {count:>5} ({pct:>5.1f}%)")
        
        print("\n📞 CE vs PE")
        print("-" * 40)
        print(f"  CE Trades:       {r['ce_trades']:>12}")
        print(f"  CE P&L:         ₹{r['ce_pnl']:>+12,.2f}")
        print(f"  PE Trades:       {r['pe_trades']:>12}")
        print(f"  PE P&L:         ₹{r['pe_pnl']:>+12,.2f}")
        
        print("\n🏆 EXTREMES")
        print("-" * 40)
        print(f"  Best Trade:     ₹{r['best_trade']:>+12,.2f}")
        print(f"  Worst Trade:    ₹{r['worst_trade']:>+12,.2f}")
        print(f"  Brokerage Paid: ₹{r['total_brokerage']:>12,.2f}")
        
        print("\n" + "=" * 65)
    
    def export_trades(self, filepath:  str = "backtest_trades.csv"):
        """Export trade log"""
        data = [{
            'entry_time': t.entry_time,
            'exit_time': t.exit_time,
            'type': t.option_type,
            'strike': t.strike,
            'entry_price': t.entry_price,
            'exit_price': t.exit_price,
            'peak': t.peak_price,
            'pnl': t.pnl,
            'pnl_pct': t.pnl_pct,
            'exit_reason': t.exit_reason,
            'hold_mins': t.hold_time_minutes,
            'brokerage': t.brokerage
        } for t in self.trades]
        
        pd.DataFrame(data).to_csv(filepath, index=False)
        print(f"✅ Trades exported:  {filepath}")
    
    def export_equity(self, filepath: str = "equity_curve.csv"):
        """Export equity curve"""
        pd.DataFrame(self.equity_curve, columns=['datetime', 'equity']).to_csv(filepath, index=False)
        print(f"✅ Equity curve exported:  {filepath}")
    
    def plot_results(self, save_dir: str = "backtest_charts"):
        """Generate visualization charts"""
        try:
            import matplotlib.pyplot as plt
        except ImportError: 
            print("⚠️ matplotlib not installed.Run: pip install matplotlib")
            return
        
        os.makedirs(save_dir, exist_ok=True)
        
        # 1.Equity Curve
        fig, axes = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={'height_ratios':  [3, 1]})
        
        dates = [e[0] for e in self.equity_curve]
        equity = [e[1] for e in self.equity_curve]
        
        axes[0].plot(dates, equity, 'b-', linewidth=1.5)
        axes[0].axhline(y=self.config.initial_capital, color='gray', linestyle='--', alpha=0.5)
        axes[0].fill_between(dates, self.config.initial_capital, equity,
                            where=[e >= self.config.initial_capital for e in equity],
                            alpha=0.3, color='green')
        axes[0].fill_between(dates, self.config.initial_capital, equity,
                            where=[e < self.config.initial_capital for e in equity],
                            alpha=0.3, color='red')
        axes[0].set_title('Equity Curve', fontsize=14, fontweight='bold')
        axes[0].set_ylabel('Capital (₹)')
        axes[0].grid(True, alpha=0.3)
        
        # Drawdown
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / peak * 100
        axes[1].fill_between(dates, 0, dd, color='red', alpha=0.5)
        axes[1].set_title('Drawdown %')
        axes[1].set_ylabel('DD %')
        axes[1].invert_yaxis()
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f"{save_dir}/equity_curve.png", dpi=150)
        plt.close()
        
        # 2.Trade Distribution
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        pnls = [t.pnl for t in self.trades]
        colors = ['green' if p > 0 else 'red' for p in pnls]
        
        axes[0, 0].bar(range(len(pnls)), pnls, color=colors, alpha=0.7)
        axes[0, 0].axhline(y=0, color='black', linewidth=0.5)
        axes[0, 0].set_title('Trade P&L Sequence')
        axes[0, 0].set_xlabel('Trade #')
        axes[0, 0].set_ylabel('P&L (₹)')
        
        axes[0, 1].hist(pnls, bins=25, color='steelblue', alpha=0.7, edgecolor='black')
        axes[0, 1].axvline(x=0, color='red', linestyle='--')
        axes[0, 1].axvline(x=np.mean(pnls), color='green', linestyle='--', 
                          label=f'Mean: ₹{np.mean(pnls):.0f}')
        axes[0, 1].set_title('P&L Distribution')
        axes[0, 1].legend()
        
        # Exit Reasons
        reasons = self.results['exit_reasons']
        axes[1, 0].pie(reasons.values(), labels=reasons.keys(), autopct='%1.1f%%')
        axes[1, 0].set_title('Exit Reasons')
        
        # CE vs PE
        ce_pnl = self.results['ce_pnl']
        pe_pnl = self.results['pe_pnl']
        colors = ['green' if p > 0 else 'red' for p in [ce_pnl, pe_pnl]]
        axes[1, 1].bar(['CE', 'PE'], [ce_pnl, pe_pnl], color=colors, alpha=0.7)
        axes[1, 1].axhline(y=0, color='black', linewidth=0.5)
        axes[1, 1].set_title('CE vs PE Performance')
        axes[1, 1].set_ylabel('P&L (₹)')
        
        plt.tight_layout()
        plt.savefig(f"{save_dir}/trade_analysis.png", dpi=150)
        plt.close()
        
        print(f"✅ Charts saved to:  {save_dir}/")


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    # Your Groww API credentials
    API_KEY = "YOUR_API_KEY_HERE"
    API_SECRET = "YOUR_API_SECRET_HERE"
    
    # Configuration
    config = BacktestConfig(
        initial_capital=10000,
        lot_size=75,
        daily_loss_limit_pct=0.10,
        target_points=10,
        stop_loss_points=5,
        trailing_stop_activation=0.50,
        trailing_stop_distance=0.15,
        max_hold_minutes=30,
        cooldown_seconds=60,
        brokerage_per_trade=20,
        slippage_points=0.5
    )
    
    # Initialize backtester
    bt = NiftyGrowwBacktester(
        api_key=API_KEY,
        api_secret=API_SECRET,
        config=config
    )
    
    # OPTION 1: Fetch fresh data from Groww API
    # df = bt.fetch_historical_data(
    #     start_date="2024-11-25",
    #     end_date="2024-12-25",
    #     save_path="data/nifty_1min.csv"
    # )
    
    # OPTION 2: Load from existing CSV
    df = bt.load_data("data/nifty_1min.csv")
    
    # Prepare indicators
    df = bt.prepare_indicators(df)
    
    # Run backtest
    results = bt.run(df, verbose=True)
    
    # Print results
    bt.print_results()
    
    # Export
    bt.export_trades("reports/trades.csv")
    bt.export_equity("reports/equity.csv")
    bt.plot_results("reports/charts")
    
    print("\n✅ Backtest Complete!")