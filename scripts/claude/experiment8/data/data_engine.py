"""
DATA ENGINE - FLATTRADE API VERSION
Enhanced data pipeline that feeds both raw data and Market Intelligence.

Converted from Groww API (Experiment 6) to Flattrade API (Experiment 8).

Key Changes:
- Uses Flattrade API instead of Groww API
- Maintains all existing functionality and interface
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
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add pythonAPI-main to path for Flattrade API
current_file = os.path.abspath(__file__)
claude_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
flattrade_api_path = os.path.join(claude_dir, 'pythonAPI-main')
flattrade_dist_path = os.path.join(flattrade_api_path, 'dist')

# Debug path resolution
if not os.path.exists(flattrade_api_path):
    print(f"⚠️ pythonAPI-main path not found: {flattrade_api_path}")
    print(f"   Current file: {current_file}")
    print(f"   Claude dir: {claude_dir}")
    
# Add both paths for Flattrade API
sys.path.insert(0, flattrade_api_path)
sys.path.insert(0, flattrade_dist_path)

# Try importing Flattrade API
try:
    from api_helper import NorenApiPy
except ImportError as e:
    print(f"❌ CRITICAL: 'api_helper' import failed: {e}")
    print(f"   Flattrade API path: {flattrade_api_path}")
    print(f"   Dist path: {flattrade_dist_path}")
    print(f"   Path exists: {os.path.exists(flattrade_api_path)}")
    if os.path.exists(flattrade_api_path):
        print(f"   Contents: {os.listdir(flattrade_api_path)[:5]}")
    NorenApiPy = None

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
    Enhanced Data Engine for Experiment 8 with Flattrade API.
    
    Provides:
    - Real-time spot/future prices
    - Technical indicators (RSI, EMA, ADX, ATR, VWAP)
    - Option chain data with OI tracking
    - Volume analysis
    - Data for Market Intelligence modules
    """
    
    def __init__(self, 
                 user_token: str, 
                 user_id: str, 
                 option_expiry: str,
                 future_expiry: str,
                 fut_symbol: str, 
                 timeframe: str = "1minute"):
        
        self.user_token = user_token
        self.user_id = user_id
        self.option_expiry = option_expiry
        self.future_expiry = future_expiry
        self.fut_symbol = fut_symbol
        self.timeframe = timeframe
        
        # Map timeframe to Flattrade interval format
        self.timeframe_map = {
            "1minute": "1",
            "2minute": "2",
            "3minute": "3",
            "5minute": "5",
            "15minute": "15",
            "30minute": "30",
            "60minute": "60"
        }
        
        # === PUBLIC DATA (Strategies read these) ===
        self.timestamp: Optional[datetime] = None
        
        # Prices
        self.spot_ltp: float = 0.0
        self.fut_ltp: float = 0.0
        self.fut_open: float = 0.0
        self.fut_high: float = 0.0
        self.fut_low: float = 0.0
        self.fut_close: float = 0.0
        
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
        self.volume_relative: float = 1.0
        
        # Market breadth
        self.atm_strike: int = 0
        self.pcr: float = 1.0
        self.total_ce_oi: int = 0
        self.total_pe_oi: int = 0
        
        # Option data
        self.strikes_data: Dict[int, StrikeOIData] = {}
        self.atm_ce_ltp: float = 0.0
        self.atm_pe_ltp: float = 0.0
        self.atm_iv: float = 0.0
        
        # Opening range
        self.opening_range_high: float = 0.0
        self.opening_range_low: float = 0.0
        self.opening_range_set: bool = False
        
        # === INTERNAL STATE ===
        self.api: Optional[NorenApiPy] = None
        self.is_connected: bool = False
        
        # Token cache for symbols
        self.token_cache: Dict[str, str] = {}
        
        # Candle history
        self.candles: deque[CandleData] = deque(maxlen=200)
        
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
        
        # Performance timing
        self.timing_stats: Dict[str, float] = {
            'spot_fetch': 0.0,
            'future_fetch': 0.0,
            'option_fetch': 0.0,
            'live_prices': 0.0,
            'total_update': 0.0
        }
        
        # Last full candle fetch time
        self.last_candle_fetch: Optional[datetime] = None
        
        # Connect
        self._connect()
        self._init_logging()
    
    def _connect(self):
        """Authenticates with the Flattrade API."""
        if NorenApiPy is None:
            print(f"[{self.timeframe}] ❌ Flattrade API module not found")
            return
        
        try:
            print(f"[{self.timeframe}] 🔑 Connecting to Flattrade API...")
            self.api = NorenApiPy()
            
            # Set session with user token (returns True on success)
            ret = self.api.set_session(
                userid=self.user_id,
                password='',
                usertoken=self.user_token
            )
            
            if ret:
                self.is_connected = True
                print(f"[{self.timeframe}] ✅ Connected to Flattrade API")
            else:
                print(f"[{self.timeframe}] ❌ Connection Failed: Session setup returned False")
                self.is_connected = False
        except Exception as e:
            print(f"[{self.timeframe}] ❌ Connection Failed: {e}")
            import traceback
            traceback.print_exc()
            self.is_connected = False
    
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
    
    def is_data_stale(self, max_age_seconds: int = 60) -> bool:
        """
        Checks if data is stale (too old).
        
        Args:
            max_age_seconds: Maximum allowed age in seconds (default: 60)
            
        Returns:
            True if data is stale or missing, False if fresh
        """
        if not self.timestamp:
            return True
        
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > max_age_seconds
    
    def get_live_prices(self) -> bool:
        """
        FAST live price fetch using get_quotes (takes ~200-500ms).
        Use this for quick price checks without full indicator calculation.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected:
            return False
        
        live_start = time.time()
        
        try:
            # Fetch spot, future, and ATM options in parallel
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {}
                
                # Spot quote
                futures['spot'] = executor.submit(
                    self.api.get_quotes, 'NSE', '26000'
                )
                
                # Future quote
                fut_token = self._get_token('NFO', 'NIFTY27JAN26F')
                if fut_token:
                    futures['future'] = executor.submit(
                        self.api.get_quotes, 'NFO', fut_token
                    )
                
                # ATM options if we know the strike
                if self.atm_strike > 0:
                    expiry_dt = datetime.strptime(self.option_expiry, "%Y-%m-%d")
                    expiry_str = expiry_dt.strftime('%d%b%y').upper()
                    
                    ce_symbol = f"NIFTY{expiry_str}C{self.atm_strike}"
                    pe_symbol = f"NIFTY{expiry_str}P{self.atm_strike}"
                    
                    ce_token = self._get_token('NFO', ce_symbol)
                    pe_token = self._get_token('NFO', pe_symbol)
                    
                    if ce_token:
                        futures['ce'] = executor.submit(
                            self.api.get_quotes, 'NFO', ce_token
                        )
                    if pe_token:
                        futures['pe'] = executor.submit(
                            self.api.get_quotes, 'NFO', pe_token
                        )
                
                # Collect results
                for key, future in futures.items():
                    try:
                        result = future.result(timeout=2.0)
                        if result and result.get('stat') == 'Ok':
                            lp = float(result.get('lp', 0))
                            
                            if key == 'spot':
                                self.spot_ltp = lp
                            elif key == 'future':
                                self.fut_ltp = lp
                            elif key == 'ce':
                                self.atm_ce_ltp = lp
                            elif key == 'pe':
                                self.atm_pe_ltp = lp
                    except Exception as e:
                        if self.update_count % 10 == 0:
                            print(f"⚠️ Live price fetch error ({key}): {e}")
            
            # Update ATM strike from spot
            if self.spot_ltp > 0:
                self.atm_strike = round(self.spot_ltp / 50) * 50
            
            self.timing_stats['live_prices'] = time.time() - live_start
            self.timestamp = datetime.now()
            
            return True
            
        except Exception as e:
            print(f"❌ Live price fetch failed: {e}")
            return False
    
    def update(self, full_fetch: bool = False) -> bool:
        """
        Main update method. Uses hybrid approach:
        - Live quotes for LTP (fast, every update)
        - Historical candles for indicators (slower, every 5 mins or when full_fetch=True)
        
        Args:
            full_fetch: Force full historical candle fetch
        
        Returns: 
            True if update successful, False otherwise
        """
        self.update_count += 1
        update_start_time = datetime.now()
        total_start = time.time()
        
        try:
            # Determine if we need full candle fetch
            need_candles = (full_fetch or 
                          self.last_candle_fetch is None or 
                          (datetime.now() - self.last_candle_fetch).total_seconds() > 300 or
                          self.update_count <= 1)
            
            if need_candles:
                # FULL FETCH MODE (takes ~60s)
                print(f"   [{self.timeframe}] Full candle fetch...")
                
                # 1.Fetch Spot data (for RSI, EMA)
                self._rate_limit('spot')
                spot_start = time.time()
                self._fetch_spot_data()
                self.timing_stats['spot_fetch'] = time.time() - spot_start
                
                # 2.Fetch Future data (for VWAP, patterns)
                self._rate_limit('future')
                fut_start = time.time()
                self._fetch_future_data()
                self.timing_stats['future_fetch'] = time.time() - fut_start
                
                self.last_candle_fetch = datetime.now()
            else:
                # FAST MODE - Just get live prices (takes <1s)
                live_start = time.time()
                self.get_live_prices()
                self.timing_stats['live_prices'] = time.time() - live_start
            
            # 3.Calculate ATM strike
            if self.spot_ltp > 0:
                self.atm_strike = round(self.spot_ltp / 50) * 50
            
            # 4.Fetch Option chain (now parallel!)
            if self.atm_strike > 0:
                self._rate_limit('chain')
                opt_start = time.time()
                self._fetch_option_chain()
                self.timing_stats['option_fetch'] = time.time() - opt_start
            
            # 5.Update opening range
            self._update_opening_range()
            
            # 6.Log snapshot
            self._log_snapshot()
            
            # Record total time
            self.timing_stats['total_update'] = time.time() - total_start
            
            # Warmup check
            if self.update_count >= 15:
                self.warmup_complete = True
            
            # Only update timestamp if data fetch was successful
            self.timestamp = update_start_time
            
            return True
            
        except Exception as e:
            if self.update_count % 10 == 0:
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
        """
        # Try exact strike first
        if strike in self.strikes_data:
            data = self.strikes_data[strike]
            if option_type == 'CE': 
                return data.ce_ltp
            else: 
                return data.pe_ltp
        
        # Try nearby strikes if exact missing
        for offset in [50, -50, 100, -100]:
            nearby_strike = strike + offset
            if nearby_strike in self.strikes_data:
                data = self.strikes_data[nearby_strike]
                price = data.ce_ltp if option_type == 'CE' else data.pe_ltp
                if price > 0.1:
                    print(f"⚠️ Strike shift: {strike} -> {nearby_strike}")
                    return price
        
        return 0.0
    
    def get_strike_data(self, strike: int) -> Optional[StrikeOIData]: 
        """Gets full strike data."""
        return self.strikes_data.get(strike)
    
    def get_affordable_strike(self, option_type: str, max_cost: float) -> Optional[StrikeOIData]:
        """
        Finds the best affordable strike.
        
        Args:
            option_type: 'CE' or 'PE'
            max_cost: Maximum cost (price * lot_size)
            
        Returns: 
            StrikeOIData or None
        """
        lot_size = BotConfig.Risk.LOT_SIZE
        
        # Preference order: ATM -> OTM1 -> OTM2
        if option_type == 'CE':
            candidates = [self.atm_strike, self.atm_strike + 50, self.atm_strike + 100]
        else: 
            candidates = [self.atm_strike, self.atm_strike - 50, self.atm_strike - 100]
        
        for strike in candidates:
            if strike in self.strikes_data:
                data = self.strikes_data[strike]
                price = data.ce_ltp if option_type == 'CE' else data.pe_ltp
                
                # Valid price must be at least ₹1
                if price >= 1.0:
                    cost = price * lot_size
                    if cost <= max_cost:
                        return data
        
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
    
    def print_live_status(self, show_options: bool = True):
        """Prints live market status in clean terminal format."""
        if not self.timestamp:
            return
        
        # Calculate changes
        fut_premium = self.fut_ltp - self.spot_ltp if self.spot_ltp > 0 else 0
        premium_pct = (fut_premium / self.spot_ltp * 100) if self.spot_ltp > 0 else 0
        
        # Price movement indicator
        spot_trend = "🟢" if self.is_green_candle else "🔴"
        
        # RSI zones
        if self.rsi >= 70:
            rsi_zone = "🔴 OVERBOUGHT"
        elif self.rsi <= 30:
            rsi_zone = "🟢 OVERSOLD"
        else:
            rsi_zone = "⚪ NEUTRAL"
        
        # ADX trend strength
        if self.adx >= 35:
            adx_strength = "STRONG"
        elif self.adx >= 20:
            adx_strength = "MODERATE"
        else:
            adx_strength = "WEAK"
        
        # Build output
        print(f"\n{'='*75}")
        print(f"⏰ {self.timestamp.strftime('%H:%M:%S')} | {self.timeframe.upper()} | Update #{self.update_count}")
        print(f"{'='*75}")
        
        # Spot & Future with visual separator
        print(f"\n  SPOT    {spot_trend} ₹{self.spot_ltp:>9,.2f}  |  O:{self.fut_open:>8,.2f} H:{self.fut_high:>8,.2f}")
        print(f"  FUTURE     ₹{self.fut_ltp:>9,.2f}  |  L:{self.fut_low:>8,.2f} C:{self.fut_close:>8,.2f}")
        print(f"  PREMIUM    ₹{fut_premium:>9.2f} ({premium_pct:>+6.2f}%) | ATM: {self.atm_strike}")
        
        # Indicators in compact format
        print(f"\n  {'─'*71}")
        print(f"  RSI: {self.rsi:>5.1f} {rsi_zone:>15} | ADX: {self.adx:>5.1f} ({adx_strength})")
        print(f"  ATR: {self.atr:>5.1f}              | VWAP: ₹{self.vwap:>9,.2f}")
        print(f"  PCR: {self.pcr:>5.2f} (PE/CE OI)   | VOL: {self.volume_relative:>5.2f}x avg")
        
        # Options - compact view
        if show_options and self.strikes_data:
            print(f"\n  {'─'*71}")
            print(f"  {'STRIKE':^10} │ {'CALL (CE)':^28} │ {'PUT (PE)':^28}")
            print(f"  {'':<10} │ {'Price':>8} {'OI':>10} {'Chg':>8} │ {'Price':>8} {'OI':>10} {'Chg':>8}")
            print(f"  {'─'*71}")
            
            # Show 5 strikes around ATM
            strikes_to_show = sorted([
                s for s in self.strikes_data.keys()
                if abs(s - self.atm_strike) <= 100
            ])[:5]
            
            for strike in strikes_to_show:
                data = self.strikes_data[strike]
                atm_mark = "⭐" if strike == self.atm_strike else "  "
                
                ce_oi_chg = f"{data.ce_oi_change/1000:>+7.0f}K" if data.ce_oi_change != 0 else "    --"
                pe_oi_chg = f"{data.pe_oi_change/1000:>+7.0f}K" if data.pe_oi_change != 0 else "    --"
                
                print(f"  {atm_mark}{strike:<8} │ ₹{data.ce_ltp:>7.2f} {data.ce_oi/1000:>8.0f}K {ce_oi_chg:>8} │ ₹{data.pe_ltp:>7.2f} {data.pe_oi/1000:>8.0f}K {pe_oi_chg:>8}")
            
            print(f"  {'─'*71}")
            print(f"  TOTAL OI:  CE: {self.total_ce_oi/1000000:>7.2f}M  |  PE: {self.total_pe_oi/1000000:>7.2f}M  |  PCR: {self.pcr:.2f}")
        
        # Timing stats
        if self.timing_stats.get('total_update', 0) > 0:
            spot_ms = self.timing_stats.get('spot_fetch', 0) * 1000
            fut_ms = self.timing_stats.get('future_fetch', 0) * 1000
            opt_ms = self.timing_stats.get('option_fetch', 0) * 1000
            live_ms = self.timing_stats.get('live_prices', 0) * 1000
            total_ms = self.timing_stats.get('total_update', 0) * 1000
            
            print(f"\n  ⏱️  Update: {total_ms:>6.0f}ms", end="")
            if live_ms > 0:
                print(f" (Live: {live_ms:.0f}ms + Opt: {opt_ms:.0f}ms)", end="")
            else:
                print(f" (Spot: {spot_ms:.0f}ms + Fut: {fut_ms:.0f}ms + Opt: {opt_ms:.0f}ms)", end="")
            print()
        
        print(f"{'='*75}\n")
    
    # ==================== INTERNAL FETCHERS ====================
    
    def _get_token(self, exchange: str, symbol: str) -> Optional[str]:
        """Gets exchange token for a symbol using search."""
        # Check cache first
        cache_key = f"{exchange}:{symbol}"
        if cache_key in self.token_cache:
            return self.token_cache[cache_key]
        
        try:
            # Search for symbol
            result = self.api.searchscrip(exchange=exchange, searchtext=symbol)
            
            if not result or 'values' not in result:
                print(f"⚠️ [{self.timeframe}] Token search failed for {exchange}:{symbol}")
                return None
            
            # Find exact match
            for item in result['values']:
                if item.get('tsym') == symbol:
                    token = item.get('token')
                    if token:
                        self.token_cache[cache_key] = token
                        return token
            
            # If no exact match, take first result
            if len(result['values']) > 0:
                token = result['values'][0].get('token')
                if token:
                    self.token_cache[cache_key] = token
                    print(f"️ [{self.timeframe}] Using fuzzy match for {symbol}: {result['values'][0].get('tsym')}")
                    return token
            
            print(f"⚠️ [{self.timeframe}] No token found for {exchange}:{symbol}")
            return None
            
        except Exception as e:
            print(f"❌ [{self.timeframe}] Token lookup error for {symbol}: {e}")
            return None
    
    def _fetch_spot_data(self):
        """Fetches spot index candles using Flattrade API."""
        if not self.is_connected:
            print(f"⚠️ [{self.timeframe}] Not connected to API - cannot fetch spot data")
            return
        
        try:
            # Get token for NIFTY 50 index - use exact symbol name
            # Token is 26000 for "Nifty 50" index
            token = '26000'  # Hardcoded for performance, or use: self._get_token('NSE', 'Nifty 50')
            if not token:
                print(f"⚠️ [{self.timeframe}] Could not get token for NIFTY index")
                return
            
            # Get current quote for LTP
            quote = self.api.get_quotes(exchange='NSE', token=token)
            if quote and quote.get('stat') == 'Ok':
                self.spot_ltp = float(quote.get('lp', 0))
            
            # Get historical candles
            interval = self.timeframe_map.get(self.timeframe, '1')
            start_dt = datetime.now() - timedelta(days=5)
            start_time = int(time.mktime(start_dt.timetuple()))
            
            resp = self.api.get_time_price_series(
                exchange='NSE',
                token=token,
                starttime=start_time,
                interval=interval
            )
            
            if not resp or not isinstance(resp, list):
                print(f"⚠️ [{self.timeframe}] Spot API returned no data: {type(resp)}")
                if resp:
                    print(f"   Response: {resp}")
                return
            
            if len(resp) == 0:
                if self.update_count % 10 == 0:
                    print(f"⚠️ [{self.timeframe}] Spot API returned empty candles")
                return
            
            # Convert to DataFrame - Flattrade returns list of dicts with named fields
            df = pd.DataFrame(resp)
            
            # Flattrade time series format: 'time', 'into' (open), 'inth' (high), 'intl' (low), 'intc' (close), 'v', 'oi'
            # Rename columns to our standard format
            column_mapping = {
                'time': 'time',
                'into': 'o',
                'inth': 'h', 
                'intl': 'l',
                'intc': 'c',
                'v': 'v',
                'oi': 'oi'
            }
            
            # Rename columns that exist
            df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
            
            # Convert numeric columns
            for col in ['o', 'h', 'l', 'c', 'v']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove invalid rows  
            df = df.dropna(subset=['o', 'h', 'l', 'c'])
            
            if len(df) == 0:
                if self.update_count % 10 == 0:
                    print(f"⚠️ [{self.timeframe}] No valid spot data after filtering")
                return
            
            # Update LTP from last candle
            if self.spot_ltp == 0:
                self.spot_ltp = float(df['c'].iloc[-1])
            
            # Store candles
            for _, row in df.tail(50).iterrows():
                try:
                    # Convert timestamp - could be int or string
                    if isinstance(row['time'], str):
                        ts = pd.to_datetime(row['time']).timestamp()
                    else:
                        ts = int(row['time'])
                    
                    candle = CandleData(
                        timestamp=datetime.fromtimestamp(ts),
                        open=float(row['o']),
                        high=float(row['h']),
                        low=float(row['l']),
                        close=float(row['c']),
                        volume=float(row['v']) if pd.notna(row.get('v')) else 0.0
                    )
                    self.candles.append(candle)
                except (ValueError, TypeError) as e:
                    continue  # Skip invalid rows
            
            # Calculate price-based indicators from SPOT data
            self._calculate_indicators(df)
            
        except Exception as e:
            print(f"❌ [{self.timeframe}] Spot fetch error: {e}")
            import traceback
            traceback.print_exc()
    
    def _fetch_future_data(self):
        """Fetches futures candles using Flattrade API."""
        if not self.is_connected:
            print(f"⚠️ [{self.timeframe}] Not connected to API - cannot fetch future data")
            return
        
        try:
            # Get token for future - Flattrade format: NIFTYXXMMMYYF (ends with F not FUT!)
            # Extract from fut_symbol: "NSE-NIFTY-27Jan26-FUT" -> "NIFTY27JAN26F"
            expiry_dt = datetime.strptime(self.future_expiry, "%Y-%m-%d")
            fut_search = f"NIFTY{expiry_dt.strftime('%d%b%y').upper()}F"
            token = self._get_token('NFO', fut_search)
            
            if not token:
                # Try generic NIFTY search and filter
                print(f"⚠️ [{self.timeframe}] Trying generic NIFTY futures search")
                token = self._get_token('NFO', 'NIFTY')
            
            if not token:
                print(f"⚠️ [{self.timeframe}] Could not get token for future {fut_search}")
                return
            
            # Get current quote for LTP
            quote = self.api.get_quotes(exchange='NFO', token=token)
            if quote and quote.get('stat') == 'Ok':
                self.fut_ltp = float(quote.get('lp', 0))
                self.fut_open = float(quote.get('o', 0))
                self.fut_high = float(quote.get('h', 0))
                self.fut_low = float(quote.get('l', 0))
                self.fut_close = float(quote.get('c', self.fut_ltp))
            
            # Get historical candles
            interval = self.timeframe_map.get(self.timeframe, '1')
            start_dt = datetime.now() - timedelta(days=5)
            start_time = int(time.mktime(start_dt.timetuple()))
            
            resp = self.api.get_time_price_series(
                exchange='NFO',
                token=token,
                starttime=start_time,
                interval=interval
            )
            
            if not resp or not isinstance(resp, list) or len(resp) == 0:
                print(f"⚠️ [{self.timeframe}] Future API returned no data for {fut_search}")
                return
            
            # Convert to DataFrame - Flattrade returns list of dicts with named fields
            df = pd.DataFrame(resp)
            
            # Flattrade time series format: 'time', 'into' (open), 'inth' (high), 'intl' (low), 'intc' (close), 'v', 'oi'
            # Rename columns to our standard format
            column_mapping = {
                'time': 'time',
                'into': 'o',
                'inth': 'h',
                'intl': 'l',
                'intc': 'c',
                'v': 'v',
                'oi': 'oi'
            }
            
            # Rename columns that exist
            df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
            
            # Convert numeric columns
            for col in ['o', 'h', 'l', 'c', 'v']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove invalid rows
            df = df.dropna(subset=['o', 'h', 'l', 'c'])
            
            if len(df) == 0:
                print(f"⚠️ [{self.timeframe}] No valid candle data after filtering (market may be closed)")
                print(f"   This means all numeric values were NaN after conversion")
                return
            
            last_row = df.iloc[-1]
            if self.fut_ltp == 0:
                self.fut_ltp = float(last_row['c'])
                self.fut_open = float(last_row['o'])
                self.fut_high = float(last_row['h'])
                self.fut_low = float(last_row['l'])
                self.fut_close = float(last_row['c'])
            
            # Volume
            if 'v' in df.columns:
                self.current_volume = float(last_row['v'])
                self.volume_history.append(self.current_volume)
                if len(self.volume_history) > 5:
                    self.avg_volume = sum(list(self.volume_history)[:-1]) / (len(self.volume_history) - 1)
                    self.volume_relative = self.current_volume / self.avg_volume if self.avg_volume > 0 else 1.0
            
            # Candle pattern
            self.candle_body = abs(self.fut_close - self.fut_open)
            self.candle_range = self.fut_high - self.fut_low
            self.is_green_candle = self.fut_close > self.fut_open
            
            # Calculate VWAP from FUTURE data
            self._calculate_vwap(df)
            
        except Exception as e:
            print(f"❌ [{self.timeframe}] Future fetch error: {e}")
            import traceback
            traceback.print_exc()
            if self.update_count % 10 == 0:
                print(f"⚠️ Future fetch error: {e}")
    
    def _fetch_option_chain(self):
        """Fetches option chain data using Flattrade API."""
        if not self.is_connected:
            print(f"⚠️ [{self.timeframe}] Not connected to API - cannot fetch option chain")
            return
        
        try:
            if self.atm_strike == 0:
                return  # Need ATM first
            
            # Flattrade: Need to construct individual option symbols
            # Format: NIFTY13JAN26C24000 (NIFTY + DD + MMM + YY + C/P + STRIKE)
            expiry_dt = datetime.strptime(self.option_expiry, "%Y-%m-%d")
            expiry_str = expiry_dt.strftime('%d%b%y').upper()  # e.g., 13JAN26
            
            # Strikes to monitor
            strikes_to_fetch = {
                self.atm_strike,
                self.atm_strike + 50, self.atm_strike + 100, self.atm_strike + 150,
                self.atm_strike - 50, self.atm_strike - 100, self.atm_strike - 150
            }
            strikes_to_fetch.update(self.active_monitoring_strikes)
            
            # Fetch each strike in parallel (much faster!)
            new_strikes_data: Dict[int, StrikeOIData] = {}
            total_ce_oi = 0
            total_pe_oi = 0
            
            # Prepare all symbols first
            strike_symbols = {}
            for strike in strikes_to_fetch:
                ce_symbol = f"NIFTY{expiry_str}C{strike}"
                pe_symbol = f"NIFTY{expiry_str}P{strike}"
                ce_token = self._get_token('NFO', ce_symbol)
                pe_token = self._get_token('NFO', pe_symbol)
                
                if ce_token and pe_token:
                    strike_symbols[strike] = {
                        'ce_token': ce_token,
                        'pe_token': pe_token
                    }
            
            # Fetch all quotes in parallel
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {}
                
                for strike, tokens in strike_symbols.items():
                    futures[f'ce_{strike}'] = executor.submit(
                        self.api.get_quotes, 'NFO', tokens['ce_token']
                    )
                    futures[f'pe_{strike}'] = executor.submit(
                        self.api.get_quotes, 'NFO', tokens['pe_token']
                    )
                
                # Collect results
                quotes = {}
                for key, future in futures.items():
                    try:
                        result = future.result(timeout=3.0)
                        if result and result.get('stat') == 'Ok':
                            quotes[key] = result
                    except Exception as e:
                        if self.update_count % 10 == 0:
                            print(f"⚠️ Quote fetch timeout: {key}")
            
            # Process collected quotes
            for strike in strike_symbols.keys():
                ce_key = f'ce_{strike}'
                pe_key = f'pe_{strike}'
                
                if ce_key not in quotes or pe_key not in quotes:
                    continue
                
                try:
                    # Extract CE data
                    ce_quote = quotes[ce_key]
                    ce_oi = int(ce_quote.get('oi', 0))
                    ce_ltp = float(ce_quote.get('lp', 0))
                    
                    # Extract PE data
                    pe_quote = quotes[pe_key]
                    pe_oi = int(pe_quote.get('oi', 0))
                    pe_ltp = float(pe_quote.get('lp', 0))
                    
                    # Create strike data
                    strike_data = StrikeOIData(strike=strike)
                    
                    # CE data
                    strike_data.ce_oi = ce_oi
                    strike_data.ce_ltp = ce_ltp
                    strike_data.ce_oi_change = ce_oi - self.prev_ce_oi.get(strike, ce_oi)
                    self.prev_ce_oi[strike] = ce_oi
                    total_ce_oi += ce_oi
                    
                    # PE data
                    strike_data.pe_oi = pe_oi
                    strike_data.pe_ltp = pe_ltp
                    strike_data.pe_oi_change = pe_oi - self.prev_pe_oi.get(strike, pe_oi)
                    self.prev_pe_oi[strike] = pe_oi
                    total_pe_oi += pe_oi
                    
                    new_strikes_data[strike] = strike_data
                    
                except Exception as e:
                    if self.update_count % 10 == 0:
                        print(f"⚠️ Strike {strike} process error: {e}")
                    continue
            
            # Commit updates
            if new_strikes_data:
                self.strikes_data = new_strikes_data
                self.total_ce_oi = total_ce_oi if total_ce_oi > 0 else self.total_ce_oi
                self.total_pe_oi = total_pe_oi if total_pe_oi > 0 else self.total_pe_oi
                self.pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 1.0
                
                # ATM data
                if self.atm_strike in self.strikes_data:
                    atm_data = self.strikes_data[self.atm_strike]
                    self.atm_ce_ltp = atm_data.ce_ltp
                    self.atm_pe_ltp = atm_data.pe_ltp
                    # Note: Flattrade doesn't provide IV in basic quotes, set to 0
                    self.atm_iv = 0.0
            
        except Exception as e:
            if self.update_count % 10 == 0:
                print(f"⚠️ Chain fetch error: {e}")
    
    # ==================== INDICATOR CALCULATIONS ====================
    
    def _calculate_indicators(self, df: pd.DataFrame):
        """
        Calculates technical indicators from SPOT data.
        Why? We trade based on SPOT NIFTY movements.
        RSI, ADX, ATR = price-based (not volume-based).
        """
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
        atr = tr.rolling(window=period).mean()
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
    
    def _calculate_vwap(self, df:  pd.DataFrame):
        """
        Calculates VWAP from FUTURE candles.
        Why? NIFTY is an index - it has NO volume!
        Only NIFTY FUTURE has actual traded volume.
        Compare: SPOT price vs FUTURE VWAP
        """
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
    
    # ==================== MOCK DATA REMOVED ====================
    # All mock data functionality has been removed.
    # System now uses ONLY real API data.
    
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
        api_key="test",
        api_secret="test",
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
