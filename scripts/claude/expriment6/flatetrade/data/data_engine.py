"""
DATA ENGINE
Enhanced data pipeline that feeds both raw data and Market Intelligence.

Upgrades from Experiment 4:
- Integrates with MarketContext building
- Tracks IV percentile
- Calculates ADX for regime detection
- Provides StrikeOIData for order flow tracking
- Volume tracking for confirmation signals
"""

import pandas as pd
import numpy as np
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from collections import deque
from dataclasses import dataclass

# Add parent directory to import config
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from utils.flattrade_wrapper import FlattradeWrapper
from config import BotConfig, get_timeframe_display_name


@dataclass
class StrikeOIData:
    """OI data for a specific strike."""
    strike: int
    ce_oi: int = 0
    pe_oi: int = 0
    ce_oi_change: int = 0
    pe_oi_change: int = 0
    ce_ltp: float = 0.0
    pe_ltp:  float = 0.0
    ce_iv: float = 0.0
    pe_iv: float = 0.0
    ce_delta: float = 0.0
    pe_delta: float = 0.0


@dataclass
class CandleData:
    """Single candle data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataEngine:
    """
    Enhanced Data Engine for Experiment 6.
    
    Provides:
    - Real-time spot/future prices
    - Technical indicators (RSI, EMA, ADX, ATR, VWAP)
    - Option chain data with OI tracking
    - Volume analysis
    - Data for Market Intelligence modules
    """
    
    def __init__(self, 
                 api_key: str, 
                 api_secret: str, 
                 option_expiry:  str,
                 future_expiry: str,
                 fut_symbol: str, 
                 timeframe: str = "1minute"):
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.option_expiry = option_expiry
        self.future_expiry = future_expiry
        self.fut_symbol = fut_symbol
        self.timeframe = timeframe
        
        # === PUBLIC DATA (Strategies read these) ===
        self.timestamp:  Optional[datetime] = None
        
        # Prices
        self.spot_ltp: float = 0.0
        self.fut_ltp: float = 0.0
        self.fut_open: float = 0.0
        self.fut_high: float = 0.0
        self.fut_low: float = 0.0
        self.fut_close: float = 0.0
        
        # Gap Tracking (NEW)
        self.yesterday_close: float = 0.0
        self.today_open: float = 0.0
        self.gap_points: float = 0.0
        
        # Indicators
        self.rsi: float = 50.0
        self.ema_5: float = 0.0
        self.ema_13: float = 0.0
        self.ema_21: float = 0.0
        self.ema_50: float = 0.0
        self.vwap: float = 0.0
        self.adx: float = 0.0
        self.atr: float = 0.0
        
        # Candle pattern
        self.candle_body: float = 0.0
        self.candle_range: float = 0.0
        self.is_green_candle: bool = False
        
        # Volume
        self.current_volume: float = 0.0
        self.avg_volume: float = 0.0
        self.volume_relative:  float = 1.0
        
        # Market breadth
        self.atm_strike: int = 0
        self.pcr: float = 1.0
        self.total_ce_oi: int = 0
        self.total_pe_oi: int = 0
        
        # Option data
        self.strikes_data: Dict[int, StrikeOIData] = {}
        self.atm_ce_ltp: float = 0.0
        self.atm_pe_ltp:  float = 0.0
        self.atm_iv: float = 0.0
        
        # Opening range
        self.opening_range_high: float = 0.0
        self.opening_range_low: float = 0.0
        self.opening_range_set: bool = False
        
        # === INTERNAL STATE ===
        self.api: Optional[FlattradeWrapper] = None
        self.is_connected: bool = False
        
        # Candle history
        self.candles: deque[CandleData] = deque(maxlen=300)
        
        # OI history for change calculation
        self.prev_ce_oi: Dict[int, int] = {}
        self.prev_pe_oi: Dict[int, int] = {}
        
        # Volume history
        self.volume_history: deque[float] = deque(maxlen=20)
        
        # ADX components
        self.tr_history: deque[float] = deque(maxlen=30)
        self.plus_dm_history: deque[float] = deque(maxlen=30)
        self.minus_dm_history: deque[float] = deque(maxlen=30)
        
        # IV history for percentile
        self.iv_history: deque[float] = deque(maxlen=100)
        
        # Active strike monitoring
        self.active_monitoring_strikes: Set[int] = set()
        
        # Rate limiting
        self.last_api_call: Dict[str, float] = {'spot': 0, 'future': 0, 'chain': 0}
        
        # Update counter
        self.update_count:  int = 0
        self.warmup_complete: bool = False
        
        # Connect
        self._connect()
        self._init_logging()
    
    def _connect(self):
        """Connect to Flattrade API"""
        try:
            print(f"[{self.timeframe}] 🔑 Connecting to Flattrade...")
            self.api = FlattradeWrapper(
                user_id=BotConfig.USER_ID,
                user_token=BotConfig.USER_TOKEN
            )
            
            if self.api.is_connected:
                self.is_connected = True
                print(f"[{self.timeframe}] ✅ Connected to Flattrade")
            else:
                print(f"[{self.timeframe}] ❌ Connection Failed")
                raise ConnectionError("Flattrade connection failed")
                
        except Exception as e:
            print(f"[{self.timeframe}] ❌ Connection Failed: {e}")
            print(f"[{self.timeframe}] 🛑 STOPPING - Fix your API credentials in config.py")
            raise
    
    def _init_logging(self):
        """Sets up CSV logging."""
        try:
            date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_dir = BotConfig.get_log_paths()['engine_log']
            fname = f"Engine_{get_timeframe_display_name(self.timeframe)}_{date_str}.csv"
            self.log_file = os.path.join(log_dir, fname)
            
            cols = [
                "Timestamp", "Spot", "Future", "RSI", "ADX", "ATR", 
                "VWAP", "EMA5", "EMA13", "ATM", "PCR", "Volume_Rel"
            ]
            with open(self.log_file, 'w') as f:
                f.write(",".join(cols) + "\n")
        except Exception as e: 
            print(f"⚠️ Logging init failed: {e}")
            self.log_file = None
    
    # ==================== PUBLIC METHODS ====================
    
    def update(self) -> bool:
        """
        Main update method. Fetches all data and calculates indicators.
        
        Returns: 
            True if update successful, False otherwise
        """
        self.update_count += 1
        self.timestamp = datetime.now()
        
        try:
            # 1.Fetch Spot data (for RSI, EMA)
            self._rate_limit('spot')
            self._fetch_spot_data()
            
            # 2.Fetch Future data (for VWAP, patterns)
            self._rate_limit('future')
            self._fetch_future_data()
            
            # 3.Calculate ATM strike
            if self.spot_ltp > 0:
                self.atm_strike = round(self.spot_ltp / 50) * 50
            
            # 4.Fetch Option chain
            if self.atm_strike > 0:
                self._rate_limit('chain')
                self._fetch_option_chain()
            
            # 5.Update opening range
            self._update_opening_range()
            
            # 6.Log snapshot
            self._log_snapshot()
            
            # Warmup check
            if self.update_count >= 15:
                self.warmup_complete = True
            
            return True
            
        except Exception as e:
            if self.update_count == 1 or self.update_count % 10 == 0:
                print(f"⚠️ [{self.timeframe}] Update error: {e}")
            return False
    
    def register_active_strike(self, strike: int):
        """Adds a strike to the monitoring list."""
        self.active_monitoring_strikes.add(int(strike))
    
    def unregister_active_strike(self, strike: int):
        """Removes a strike from the monitoring list."""
        self.active_monitoring_strikes.discard(int(strike))
    
    def get_option_price(self, strike:  int, option_type: str) -> float:
        """
        Gets current price for an option.
        
        Args:
            strike: Strike price
            option_type:  'CE' or 'PE'
            
        Returns:
            LTP or 0 if not found
            
        NOTE: For position strikes, fetches directly from API if not in strikes_data
        This handles ATM shift where position strike is out of option chain range
        """
        # Try strikes_data first (fast path)
        if strike in self.strikes_data:
            data = self.strikes_data[strike]
            if option_type == 'CE': 
                return data.ce_ltp
            else: 
                return data.pe_ltp
        
        # ⚠️ CRITICAL: Strike not in cached data (ATM shifted)
        # For active positions, fetch price directly from API
        if strike in self.active_monitoring_strikes:
            try:
                # Get the option symbol and token
                expiry_dt = datetime.strptime(self.option_expiry, "%Y-%m-%d")
                day = expiry_dt.strftime("%d")
                month = expiry_dt.strftime("%b").upper()
                year = expiry_dt.strftime("%y")
                
                option_symbol = f"NIFTY{day}{month}{year}{'C' if option_type == 'CE' else 'P'}{int(strike)}"
                
                # Search for the option token
                search_result = self.api.api.searchscrip(exchange="NFO", searchtext=option_symbol)
                if search_result and 'values' in search_result and len(search_result['values']) > 0:
                    token = search_result['values'][0]['token']
                    
                    # Get live quote
                    quote_data = self.api.api.get_quotes(exchange='NFO', token=token)
                    if quote_data and 'lp' in quote_data:
                        price = float(quote_data.get('lp', 0))
                        if price > 0.1:
                            print(f"📡 Fetched {option_symbol} directly: ₹{price:.2f}")
                            return price
            except Exception as e:
                print(f"⚠️ Failed to fetch {strike} {option_type} directly: {e}")
        
        # Strike not found and not a monitored position
        return 0.0
    
    def get_strike_data(self, strike: int) -> Optional[StrikeOIData]: 
        """Gets full strike data."""
        return self.strikes_data.get(strike)
    
    def get_affordable_strike(self, option_type: str, max_cost: float) -> Optional[StrikeOIData]:
        """
        Finds the best affordable strike with OTM limit but unlimited ITM.
        
        Rules:
        - OTM Limit: Max 2 strikes away (+50, +100 for CE | -50, -100 for PE)
        - ITM Limit: Unlimited (can go deep ITM as long as premium ≥ ₹80 and within budget)
        - Min Premium: ₹80
        - Max Premium: Budget limit
        
        Preference: ATM → OTM+1 → OTM+2 → ITM-1 → ITM-2 → ITM-3...
        
        Args:
            option_type: 'CE' or 'PE'
            max_cost: Maximum cost (price * lot_size)
            
        Returns: 
            StrikeOIData or None
        """
        lot_size = BotConfig.Risk.LOT_SIZE
        MIN_PREMIUM = 80.0  # Minimum acceptable premium
        
        candidates = []
        
        if option_type == 'CE':
            # ATM → OTM (max 2) → ITM (unlimited)
            candidates.append(self.atm_strike)
            candidates.append(self.atm_strike + 50)   # OTM+1
            candidates.append(self.atm_strike + 100)  # OTM+2
            
            # ITM: Unlimited depth (26050, 26000, 25950...)
            itm_strike = self.atm_strike - 50
            while itm_strike in self.strikes_data:
                candidates.append(itm_strike)
                itm_strike -= 50
                
        else:  # PE
            # ATM → OTM (max 2) → ITM (unlimited)
            candidates.append(self.atm_strike)
            candidates.append(self.atm_strike - 50)   # OTM+1
            candidates.append(self.atm_strike - 100)  # OTM+2
            
            # ITM: Unlimited depth (26150, 26200, 26250...)
            itm_strike = self.atm_strike + 50
            while itm_strike in self.strikes_data:
                candidates.append(itm_strike)
                itm_strike += 50
        
        # Find first strike meeting all criteria
        for strike in candidates:
            if strike in self.strikes_data:
                data = self.strikes_data[strike]
                price = data.ce_ltp if option_type == 'CE' else data.pe_ltp
                
                # Must meet minimum premium requirement
                if price < MIN_PREMIUM:
                    continue
                
                # Must be within budget
                cost = price * lot_size
                if cost <= max_cost:
                    return data
        
        # No affordable strike found
        return None
    
    def get_candle_history(self, count: int = 50) -> List[CandleData]: 
        """Returns recent candle history."""
        return list(self.candles)[-count:]
    
    def get_iv_percentile(self) -> float:
        """Returns current IV percentile."""
        if len(self.iv_history) < 20:
            return 50.0
        
        current_iv = self.atm_iv
        if current_iv <= 0:
            return 50.0
        
        sorted_iv = sorted(list(self.iv_history))
        count_below = sum(1 for iv in sorted_iv if iv < current_iv)
        return (count_below / len(sorted_iv)) * 100
    
    # ==================== INTERNAL FETCHERS ====================
    
    def _fetch_spot_data(self):
        """Fetches spot data handling Weekends, Duplicates, and Indicators."""
        if not self.is_connected:
            return

        try:
            # 1. SMART TIME WINDOW
            start_dt = datetime.now() - timedelta(days=5)
            end_dt = datetime.now()

            resp = self.api.get_historical_candles(
                "NSE", "CASH", "NSE-NIFTY",
                start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                self.timeframe
            )

            # Fallback to Live Quote
            if not resp or 'candles' not in resp or len(resp['candles']) == 0:
                try:
                    quote = self.api.get_quote("NSE-NIFTY")
                    self.spot_ltp = float(quote['last_price'])
                except: 
                    pass
                return

            df = pd.DataFrame(resp['candles'])
            cols = ['t', 'o', 'h', 'l', 'c', 'v']
            if len(df.columns) > len(cols):
                df = df.iloc[:, :len(cols)]
            df.columns = cols[:len(df.columns)]
            df['t'] = pd.to_datetime(df['t'])

            # 2. DEDUPLICATION
            last_stored_time = self.candles[-1].timestamp if self.candles else datetime.min
            new_candles_added = False
            
            for _, row in df.iterrows():
                candle_ts = row['t']
                if candle_ts > last_stored_time:
                    # ✅ FIXED: Applied pd.notna check inside the loop too
                    candle = CandleData(
                        timestamp=candle_ts,
                        open=float(row['o']) if pd.notna(row['o']) else 0.0,
                        high=float(row['h']) if pd.notna(row['h']) else 0.0,
                        low=float(row['l']) if pd.notna(row['l']) else 0.0,
                        close=float(row['c']) if pd.notna(row['c']) else 0.0,
                        volume=float(row.get('v')) if pd.notna(row.get('v')) else 0.0
                    )
                    self.candles.append(candle)
                    new_candles_added = True

            # Update LTP (Safe Version)
            last_close = df['c'].iloc[-1]
            self.spot_ltp = float(last_close) if pd.notna(last_close) else 0.0

            # 3. CALCULATE INDICATORS
            if new_candles_added or not self.warmup_complete:
                full_df = pd.DataFrame([
                    {'c': c.close, 'h': c.high, 'l': c.low, 'v': c.volume} 
                    for c in self.candles
                ])
                if len(full_df) > 0:
                    self._calculate_indicators(full_df)

        except Exception as e:
            print(f"❌ [{self.timeframe}] Spot fetch error: {e}")
    
    def _fetch_future_data(self):
        """Fetches future data with Gap Detection and Intraday VWAP."""
        if not self.is_connected:
            return

        try:
            # 1. SMART TIME WINDOW
            start_dt = datetime.now() - timedelta(days=5)
            end_dt = datetime.now()

            resp = self.api.get_historical_candles(
                "NSE", "FNO", self.fut_symbol,
                start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                self.timeframe
            )

            if not resp or 'candles' not in resp or len(resp['candles']) == 0:
                return

            df = pd.DataFrame(resp['candles'])
            cols = ['t', 'o', 'h', 'l', 'c', 'v']
            if len(df.columns) > len(cols):
                df = df.iloc[:, :len(cols)]
            df.columns = cols[:len(df.columns)]
            df['t'] = pd.to_datetime(df['t'])

            # 2. UPDATE CURRENT PRICE (Always latest)
            last_row = df.iloc[-1]
            
            # ✅ ROBUST FIX: All price fields protected
            self.fut_ltp = float(last_row['c']) if pd.notna(last_row['c']) else 0.0
            self.fut_open = float(last_row['o']) if pd.notna(last_row['o']) else 0.0
            self.fut_high = float(last_row['h']) if pd.notna(last_row['h']) else 0.0
            self.fut_low = float(last_row['l']) if pd.notna(last_row['l']) else 0.0
            self.fut_close = float(last_row['c']) if pd.notna(last_row['c']) else 0.0

            self.candle_body = abs(self.fut_close - self.fut_open)
            self.candle_range = self.fut_high - self.fut_low
            self.is_green_candle = self.fut_close > self.fut_open

            # Volume (Safe Version)
            if 'v' in df.columns:
                vol = last_row['v']
                self.current_volume = float(vol) if pd.notna(vol) else 0.0
                
                self.volume_history.append(self.current_volume)
                if len(self.volume_history) > 5:
                    self.avg_volume = sum(list(self.volume_history)[:-1]) / (len(self.volume_history) - 1)
                    self.volume_relative = self.current_volume / self.avg_volume if self.avg_volume > 0 else 1.0

            # 3. GAP DETECTION
            today_date = datetime.now().date()
            today_df = df[df['t'].dt.date == today_date].copy()
            
            if len(today_df) > 0 and self.today_open == 0:
                val_open = today_df.iloc[0]['o']
                self.today_open = float(val_open) if pd.notna(val_open) else 0.0
                
                yesterday_df = df[df['t'].dt.date < today_date]
                if len(yesterday_df) > 0:
                    val_close = yesterday_df.iloc[-1]['c']
                    self.yesterday_close = float(val_close) if pd.notna(val_close) else 0.0
                    self.gap_points = self.today_open - self.yesterday_close
                    
                    if abs(self.gap_points) > 50:
                        print(f"📊 [{self.timeframe}] GAP DETECTED: {self.gap_points:+.2f} points")

            # 4. VWAP LOGIC
            if len(today_df) > 0:
                self._calculate_vwap(today_df)
            else:
                self.vwap = self.fut_close

        except Exception as e:
            print(f"❌ [{self.timeframe}] Future fetch error: {e}")
    
    def _fetch_option_chain(self):
        """Fetches option chain data."""
        if not self.is_connected:
            print(f"❌ [{self.timeframe}] No API connection")
            return
        
        try:
            chain = self.api.get_option_chain("NSE", "NIFTY", self.option_expiry)
            
            if not chain or 'strikes' not in chain:
                print(f"⚠️ [{self.timeframe}] No option chain data received") 
                return
            
            # Strikes to fetch
            strikes_to_fetch = {
                self.atm_strike,
                self.atm_strike + 50, self.atm_strike + 100, self.atm_strike + 150,
                self.atm_strike - 50, self.atm_strike - 100, self.atm_strike - 150
            }
            strikes_to_fetch.update(self.active_monitoring_strikes)
            
            # Process chain
            new_strikes_data:  Dict[int, StrikeOIData] = {}
            total_ce_oi = 0
            total_pe_oi = 0
            
            for strike_str, data in chain['strikes'].items():
                strike = int(float(strike_str))
                
                ce = data.get('CE', {})
                pe = data.get('PE', {})
                
                ce_oi = ce.get('open_interest', 0)
                pe_oi = pe.get('open_interest', 0)
                
                total_ce_oi += ce_oi
                total_pe_oi += pe_oi
                
                if strike in strikes_to_fetch:
                    # Calculate OI change
                    ce_oi_change = ce_oi - self.prev_ce_oi.get(strike, ce_oi)
                    pe_oi_change = pe_oi - self.prev_pe_oi.get(strike, pe_oi)
                    
                    # Get greeks
                    ce_greeks = ce.get('greeks', {})
                    pe_greeks = pe.get('greeks', {})
                    
                    new_strikes_data[strike] = StrikeOIData(
                        strike=strike,
                        ce_oi=ce_oi,
                        pe_oi=pe_oi,
                        ce_oi_change=ce_oi_change,
                        pe_oi_change=pe_oi_change,
                        ce_ltp=ce.get('ltp', 0.0),
                        pe_ltp=pe.get('ltp', 0.0),
                        ce_iv=ce_greeks.get('iv', 0.0),
                        pe_iv=pe_greeks.get('iv', 0.0),
                        ce_delta=ce_greeks.get('delta', 0.0),
                        pe_delta=pe_greeks.get('delta', 0.0)
                    )
                    
                    # Update previous OI
                    self.prev_ce_oi[strike] = ce_oi
                    self.prev_pe_oi[strike] = pe_oi
            
            # Commit updates
            self.strikes_data = new_strikes_data
            self.total_ce_oi = total_ce_oi
            self.total_pe_oi = total_pe_oi
            self.pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 1.0
            
            # ATM data
            if self.atm_strike in self.strikes_data:
                atm_data = self.strikes_data[self.atm_strike]
                self.atm_ce_ltp = atm_data.ce_ltp
                self.atm_pe_ltp = atm_data.pe_ltp
                self.atm_iv = (atm_data.ce_iv + atm_data.pe_iv) / 2
                
                if self.atm_iv > 0:
                    self.iv_history.append(self.atm_iv)
            
        except Exception as e:  
            print(f"❌ [{self.timeframe}] CRITICAL ERROR fetching option chain: {e}")
            raise e
    
    # ==================== INDICATOR CALCULATIONS ====================
    
    def _calculate_indicators(self, df: pd.DataFrame):
        """Calculates technical indicators."""
        closes = df['c'].astype(float)
        highs = df['h'].astype(float)
        lows = df['l'].astype(float)
        
        # EMAs
        if len(closes) >= 50:
            self.ema_5 = float(closes.ewm(span=5, adjust=False).mean().iloc[-1])
            self.ema_13 = float(closes.ewm(span=13, adjust=False).mean().iloc[-1])
            self.ema_21 = float(closes.ewm(span=21, adjust=False).mean().iloc[-1])
            self.ema_50 = float(closes.ewm(span=50, adjust=False).mean().iloc[-1])
        
        # RSI
        if len(closes) > 14:
            delta = closes.diff()
            gain = delta.where(delta > 0, 0.0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            self.rsi = float(100 - (100 / (1 + rs)).iloc[-1])
        
        # ADX and ATR
        if len(df) > 14:
            self._calculate_adx_atr(highs, lows, closes)
    
    def _calculate_adx_atr(self, highs: pd.Series, lows: pd.Series, closes: pd.Series):
        """Calculates ADX and ATR."""
        period = 14
        
        if len(closes) < period + 1:
            return
        
        # True Range
        prev_close = closes.shift(1)
        tr1 = highs - lows
        tr2 = abs(highs - prev_close)
        tr3 = abs(lows - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR
        atr = tr.rolling(window=period, min_periods=1).mean()
        self.atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
        
        # Directional Movement
        up_move = highs - highs.shift(1)
        down_move = lows.shift(1) - lows
        
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
        
        # Smoothed
        atr_smooth = tr.ewm(span=period, adjust=False).mean()
        plus_dm_smooth = plus_dm.ewm(span=period, adjust=False).mean()
        minus_dm_smooth = minus_dm.ewm(span=period, adjust=False).mean()
        
        # DI
        plus_di = 100 * plus_dm_smooth / atr_smooth
        minus_di = 100 * minus_dm_smooth / atr_smooth
        
        # DX and ADX
        di_sum = plus_di + minus_di
        dx = 100 * abs(plus_di - minus_di) / di_sum.where(di_sum != 0, 1)
        adx = dx.ewm(span=period, adjust=False).mean()
        
        self.adx = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0
    
    def _calculate_vwap(self, df:pd.DataFrame):
        """Calculates VWAP."""
        if 'v' not in df.columns or df['v'].sum() == 0:
            self.vwap = float(df['c'].mean())
            return
        
        typical_price = (df['h'] + df['l'] + df['c']) / 3
        cumulative_tp_vol = (typical_price * df['v']).cumsum()
        cumulative_vol = df['v'].cumsum()
        
        vwap_series = cumulative_tp_vol / cumulative_vol
        self.vwap = float(vwap_series.iloc[-1])
    
    def _update_opening_range(self):
        """Updates opening range during first 15 minutes."""
        if self.opening_range_set: 
            return
        
        current_time = datetime.now().time()
        
        # Opening range:  9:15 - 9:30
        from datetime import time as dt_time
        
        if current_time < dt_time(9, 15):
            return
        
        if current_time <= dt_time(9, 30):
            # Still forming
            if self.fut_high > 0:
                if self.opening_range_high == 0:
                    self.opening_range_high = self.fut_high
                    self.opening_range_low = self.fut_low
                else: 
                    self.opening_range_high = max(self.opening_range_high, self.fut_high)
                    self.opening_range_low = min(self.opening_range_low, self.fut_low)
        else:
            # Range complete
            if self.opening_range_high > 0:
                self.opening_range_set = True
      
    # ==================== UTILITIES ====================
    
    def _rate_limit(self, api_type: str):
        """Simple rate limiting."""
        limits = {
            'spot': BotConfig.RATE_LIMIT_SPOT,
            'future': BotConfig.RATE_LIMIT_FUTURE,
            'chain': BotConfig.RATE_LIMIT_CHAIN
        }
        
        now = time.time()
        elapsed = now - self.last_api_call.get(api_type, 0)
        wait = limits.get(api_type, 0.5) - elapsed
        
        if wait > 0:
            time.sleep(wait)
        
        self.last_api_call[api_type] = time.time()
    
    def _log_snapshot(self):
        """Logs current state to CSV."""
        if not self.log_file:
            return
        
        try: 
            row = [
                datetime.now().strftime("%H:%M:%S"),
                f"{self.spot_ltp:.2f}",
                f"{self.fut_ltp:.2f}",
                f"{self.rsi:.1f}",
                f"{self.adx:.1f}",
                f"{self.atr:.1f}",
                f"{self.vwap:.2f}",
                f"{self.ema_5:.2f}",
                f"{self.ema_13:.2f}",
                str(self.atm_strike),
                f"{self.pcr:.2f}",
                f"{self.volume_relative:.2f}"
            ]
            
            with open(self.log_file, 'a') as f:
                f.write(",".join(row) + "\n")
        except Exception: 
            pass
    
    def is_ready(self) -> bool:
        """Checks if engine has enough data."""
        return self.warmup_complete and self.spot_ltp > 0


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing Data Engine...\n")
    
    engine = DataEngine(
        api_key=BotConfig.USER_ID,
        api_secret=BotConfig.USER_TOKEN,
        option_expiry="2026-01-06",
        future_expiry="2026-01-27",
        fut_symbol="NSE-NIFTY-27Jan26-FUT",
        timeframe="1minute"
    )
    
    print("Running mock updates...")
    for i in range(5):
        engine.update()
        print(f"Update {i+1}:  Spot={engine.spot_ltp:.2f}, RSI={engine.rsi:.1f}, "
              f"ADX={engine.adx:.1f}, ATM={engine.atm_strike}")
    
    print(f"\nOpening Range: {engine.opening_range_low:.2f} - {engine.opening_range_high:.2f}")
    print(f"PCR: {engine.pcr:.2f}")
    print(f"Volume Relative: {engine.volume_relative:.2f}x")
    
    print("\n✅ Data Engine Test Complete!")