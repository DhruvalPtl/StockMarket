"""
DATA PIPELINE MODULE
Handles all interactions with the Groww API.
Manages real-time data fetching, indicator calculation, and strike monitoring.
"""

import pandas as pd
import numpy as np
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

# Try importing GrowwAPI; handle if missing (for structural checking)
try:
    from growwapi import GrowwAPI
except ImportError:
    print("⚠️ WARNING: 'growwapi.py' not found. Ensure it exists in the directory.")
    GrowwAPI = None

from config import BotConfig, get_timeframe_display_name

class GrowwDataEngine:
    """
    The heart of the data system.
    Fetches Spot, Future, and Option Chain data.
    Calculates technical indicators (RSI, EMA, VWAP).
    """

    def __init__(self, api_key: str, api_secret: str, expiry_date: str, fut_symbol: str, timeframe: str = "1minute"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.expiry_date = expiry_date
        self.fut_symbol = fut_symbol
        self.timeframe = timeframe
        
        # --- Public Data Interface (Strategies read these) ---
        self.timestamp = None
        self.spot_ltp = 0.0
        self.fut_ltp = 0.0
        self.fut_open = 0.0
        self.fut_high = 0.0
        self.fut_low = 0.0
        
        # Indicators
        self.rsi = 50.0
        self.ema5 = 0.0
        self.ema13 = 0.0
        self.vwap = 0.0
        self.candle_body = 0.0
        self.candle_green = False
        
        # Market Breadth
        self.atm_strike = 0
        self.pcr = 0.0
        self.total_ce_oi = 0
        self.total_pe_oi = 0
        
        # Option Data Containers
        self.atm_ce = {}
        self.atm_pe = {}
        # Stores data for {strike: {'CE': {...}, 'PE': {...}}}
        self.strikes_data = {} 
        
        # --- Critical Fix: Active Strike Monitoring ---
        # A set of strikes that we MUST fetch every tick because we hold positions in them.
        self.active_monitoring_strikes: Set[int] = set()
        
        # --- Internal State ---
        self.groww = None
        self.rsi_warmup_complete = False
        self.rsi_period = BotConfig.RSI_PERIOD
        self.update_count = 0
        self.last_api_call = {'spot': 0, 'future': 0, 'chain': 0}
        
        # Connect immediately
        self._connect()
        self._init_csv_logging()

    def _connect(self):
        """Authenticates with the Groww API."""
        if GrowwAPI is None:
            return
            
        try:
            print(f"[{self.timeframe}] 🔑 Authenticating...")
            token = GrowwAPI.get_access_token(api_key=self.api_key, secret=self.api_secret)
            self.groww = GrowwAPI(token)
            print(f"[{self.timeframe}] ✅ Connected to Groww API.")
        except Exception as e:
            print(f"[{self.timeframe}] ❌ Connection Failed: {e}")
            sys.exit(1)

    def _init_csv_logging(self):
        """Sets up the CSV logger for this engine."""
        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Use config for path safety
        log_dir = BotConfig.get_log_paths()['engine_log']
        fname = f"Engine_{get_timeframe_display_name(self.timeframe)}_{date_str}.csv"
        self.log_file = os.path.join(log_dir, fname)
        
        cols = [
            "Timestamp", "Spot_LTP", "Fut_LTP", "RSI", "VWAP", "EMA5", "EMA13",
            "ATM_Strike", "PCR", "CE_LTP", "PE_LTP"
        ]
        with open(self.log_file, 'w') as f:
            f.write(",".join(cols) + "\n")

    # ==================================================================
    # EXTERNAL METHODS (Called by Bot)
    # ==================================================================

    def register_active_strike(self, strike: int):
        """CRITICAL: Adds a strike to the 'must-watch' list."""
        self.active_monitoring_strikes.add(int(strike))
        # print(f"[{self.timeframe}] 👁️ Monitoring active strike: {strike}")

    def unregister_active_strike(self, strike: int):
        """Removes a strike from the 'must-watch' list."""
        if int(strike) in self.active_monitoring_strikes:
            self.active_monitoring_strikes.remove(int(strike))
            # print(f"[{self.timeframe}] 🙈 Stopped monitoring strike: {strike}")

    def update(self):
        """Main loop: Fetches all data and calculates indicators."""
        self.update_count += 1
        self.timestamp = datetime.now()
        
        # 1. Fetch Spot (for EMA/RSI)
        self._rate_limit('spot')
        self._fetch_spot_data()
        
        # 2. Fetch Future (for VWAP/Patterns)
        self._rate_limit('future')
        self._fetch_future_data()
        
        # 3. Calculate ATM Strike
        if self.spot_ltp > 0:
            self.atm_strike = round(self.spot_ltp / 50) * 50
            
        # 4. Fetch Option Chain (Includes Active Strikes)
        if self.atm_strike > 0:
            self._rate_limit('chain')
            self._fetch_option_chain()
            
        # 5. Log
        self._log_snapshot()

    # ==================================================================
    # INTERNAL FETCHERS
    # ==================================================================

    def _fetch_spot_data(self):
        """Fetches Spot Index candles for RSI and EMA."""
        try:
            # We need enough candles for RSI(14) and EMA(13)
            # Fetching last 200 candles is usually safe and fast
            start_dt = datetime.now() - timedelta(days=5) 
            end_dt = datetime.now()
            
            resp = self.groww.get_historical_candles(
                "NSE", "CASH", "NSE-NIFTY",
                start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                self.timeframe
            )
            
            if not resp or 'candles' not in resp or len(resp['candles']) == 0:
                return

            df = pd.DataFrame(resp['candles'])
            # Groww returns: [t, o, h, l, c, v]
            cols = ['t', 'o', 'h', 'l', 'c', 'v']
            # Sometimes 'oi' is present, handle dynamic columns
            df = df.iloc[:, :len(cols)] 
            df.columns = cols[:len(df.columns)]
            
            # Update LTP
            self.spot_ltp = float(df['c'].iloc[-1])
            
            # Calculate Indicators
            self._calculate_indicators(df)
            
        except Exception as e:
            if self.update_count % 10 == 0:
                print(f"⚠️ Spot Fetch Error: {e}")

    def _calculate_indicators(self, df):
        """Calculates RSI and EMAs."""
        closes = df['c']
        
        # EMA
        if len(closes) >= 13:
            self.ema5 = float(closes.ewm(span=5, adjust=False).mean().iloc[-1])
            self.ema13 = float(closes.ewm(span=13, adjust=False).mean().iloc[-1])
            
        # RSI (Wilder's Smoothing)
        if len(closes) > self.rsi_period:
            delta = closes.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean() # Simple for warmup
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
            
            # Switch to exponential for live accuracy if we had full history, 
            # but for standard bots, Pandas EWM is best:
            gain = delta.where(delta > 0, 0.0).ewm(alpha=1/self.rsi_period, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/self.rsi_period, adjust=False).mean()
            
            rs = gain / loss
            self.rsi = float(100 - (100 / (1 + rs)).iloc[-1])
            self.rsi_warmup_complete = True
        else:
            self.rsi_warmup_complete = False

    def _fetch_future_data(self):
        """Fetches Futures candles for VWAP and candle patterns."""
        try:
            # For VWAP, we strictly need today's data from 09:15
            today_open = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
            now = datetime.now()
            
            resp = self.groww.get_historical_candles(
                "NSE", "FNO", self.fut_symbol,
                today_open.strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%Y-%m-%d %H:%M:%S"),
                self.timeframe
            )
            
            if not resp or 'candles' not in resp or len(resp['candles']) == 0:
                return

            df = pd.DataFrame(resp['candles'])
            cols = ['t', 'o', 'h', 'l', 'c', 'v']
            df = df.iloc[:, :len(cols)]
            df.columns = cols[:len(df.columns)]
            
            last_row = df.iloc[-1]
            self.fut_ltp = float(last_row['c'])
            self.fut_open = float(last_row['o'])
            self.fut_high = float(last_row['h'])
            self.fut_low = float(last_row['l'])
            
            # Candle Pattern
            self.candle_body = abs(self.fut_ltp - self.fut_open)
            self.candle_green = self.fut_ltp > self.fut_open
            
            # VWAP Calculation
            self._calculate_vwap(df)
            
        except Exception as e:
            if self.update_count % 10 == 0:
                print(f"⚠️ Future Fetch Error: {e}")

    def _calculate_vwap(self, df):
        """Volume Weighted Average Price."""
        try:
            if 'v' not in df.columns or df['v'].sum() == 0:
                # Fallback if no volume
                self.vwap = float(df['c'].mean())
                return

            df['tp'] = (df['h'] + df['l'] + df['c']) / 3
            df['vol_price'] = df['tp'] * df['v']
            
            cumulative_vp = df['vol_price'].sum()
            cumulative_vol = df['v'].sum()
            
            self.vwap = cumulative_vp / cumulative_vol
        except Exception:
            self.vwap = self.fut_ltp # Ultimate fallback

    def _fetch_option_chain(self):
        """
        Fetches option chain.
        CRITICAL: Combines standard ATM strikes with Active Monitoring strikes.
        """
        try:
            chain = self.groww.get_option_chain("NSE", "NIFTY", self.expiry_date)
            if not chain or 'strikes' not in chain:
                return

            # 1. Define Standard Strikes (ATM ± 2)
            strikes_to_fetch = {
                self.atm_strike,
                self.atm_strike + 50, self.atm_strike + 100,
                self.atm_strike - 50, self.atm_strike - 100
            }
            
            # 2. Add Active Strikes (Fix for Issue #2)
            strikes_to_fetch.update(self.active_monitoring_strikes)
            
            # 3. Process Data
            temp_strikes_data = {}
            total_ce_oi = 0
            total_pe_oi = 0
            
            for strike_str, data in chain['strikes'].items():
                strike = int(float(strike_str))
                
                # Accumulate OI (Global)
                ce = data.get('CE', {})
                pe = data.get('PE', {})
                total_ce_oi += ce.get('open_interest', 0)
                total_pe_oi += pe.get('open_interest', 0)
                
                # Store if in target list
                if strike in strikes_to_fetch:
                    temp_strikes_data[strike] = {}
                    
                    if ce:
                        temp_strikes_data[strike]['CE'] = self._parse_option_node(ce, strike)
                    if pe:
                        temp_strikes_data[strike]['PE'] = self._parse_option_node(pe, strike)
            
            # 4. Commit updates
            self.strikes_data = temp_strikes_data
            self.total_ce_oi = total_ce_oi
            self.total_pe_oi = total_pe_oi
            self.pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0.0
            
            # Update convenience ATM references
            if self.atm_strike in self.strikes_data:
                self.atm_ce = self.strikes_data[self.atm_strike].get('CE', {})
                self.atm_pe = self.strikes_data[self.atm_strike].get('PE', {})

        except Exception as e:
            if self.update_count % 10 == 0:
                print(f"⚠️ Chain Fetch Error: {e}")

    def _parse_option_node(self, node, strike):
        """Helper to extract clean dict from raw API node."""
        greeks = node.get('greeks', {})
        return {
            'symbol': node.get('trading_symbol'),
            'strike': strike,
            'ltp': node.get('ltp', 0.0),
            'oi': node.get('open_interest', 0),
            'delta': greeks.get('delta', 0.0),
            'iv': greeks.get('iv', 0.0)
        }

    # ==================================================================
    # HELPER UTILITIES
    # ==================================================================

    def get_option_price(self, symbol: str, strike: int, type_: str) -> float:
        """
        Robust Price Fetcher.
        1. Checks Cache.
        2. Falls back to API if cache miss/zero.
        """
        # 1. Check Cache
        if strike in self.strikes_data and type_ in self.strikes_data[strike]:
            price = self.strikes_data[strike][type_]['ltp']
            if price > 0:
                return price
        
        # 2. Fallback to API
        try:
            # print(f"⚠️ Cache miss for {symbol}, fetching live...")
            # Note: construct search key for groww. Usually "NSE_SYMBOL"
            search_key = f"NSE_{symbol}"
            ltp_data = self.groww.get_ltp("FNO", [search_key])
            if ltp_data and search_key in ltp_data:
                return float(ltp_data[search_key])
        except Exception:
            pass
            
        return 0.0

    def get_affordable_strike(self, type_: str, max_cost: float) -> Optional[Dict]:
        """Finds the best strike within budget."""
        # Preference: ATM -> OTM1 -> OTM2
        if type_ == 'CE':
            candidates = [self.atm_strike, self.atm_strike + 50, self.atm_strike + 100]
        else:
            candidates = [self.atm_strike, self.atm_strike - 50, self.atm_strike - 100]
            
        for strike in candidates:
            if strike in self.strikes_data and type_ in self.strikes_data[strike]:
                opt = self.strikes_data[strike][type_]
                price = opt['ltp']
                
                # Safety: Ignore zero price
                if price <= 0.1: 
                    continue
                    
                cost = price * BotConfig.LOT_SIZE
                if cost <= max_cost:
                    return opt
        return None

    def _rate_limit(self, type_):
        """Simple sleep-based rate limiter."""
        limits = {
            'spot': BotConfig.RATE_LIMIT_SPOT,
            'future': BotConfig.RATE_LIMIT_FUTURE,
            'chain': BotConfig.RATE_LIMIT_CHAIN
        }
        
        now = time.time()
        elapsed = now - self.last_api_call[type_]
        wait = limits[type_] - elapsed
        
        if wait > 0:
            time.sleep(wait)
            
        self.last_api_call[type_] = time.time()

    def _log_snapshot(self):
        """Writes current state to CSV."""
        if not hasattr(self, 'log_file'): return
        
        row = [
            datetime.now().strftime("%H:%M:%S"),
            self.spot_ltp, self.fut_ltp, round(self.rsi, 1), round(self.vwap, 2),
            round(self.ema5, 2), round(self.ema13, 2),
            self.atm_strike, self.pcr,
            self.atm_ce.get('ltp', 0), self.atm_pe.get('ltp', 0)
        ]
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
        except Exception:
            pass

# ==================================================================
# SELF-TEST BLOCK
# ==================================================================
if __name__ == "__main__":
    print("\n🔬 RUNNING DIAGNOSTIC TEST on GrowwDataEngine...\n")
    
    # Validate Config first
    try:
        BotConfig.validate()
        
        # Initialize Engine
        engine = GrowwDataEngine(
            BotConfig.API_KEY, 
            BotConfig.API_SECRET,
            BotConfig.OPTION_EXPIRY,
            f"NSE-NIFTY-27Jan26-FUT", # Example future symbol
            "1minute"
        )
        
        print("\n⏳ Fetching initial data (this takes a few seconds)...")
        engine.update()
        
        print("\n✅ DATA SNAPSHOT:")
        print(f"   Spot: {engine.spot_ltp}")
        print(f"   Fut:  {engine.fut_ltp}")
        print(f"   RSI:  {engine.rsi}")
        print(f"   VWAP: {engine.vwap}")
        print(f"   ATM:  {engine.atm_strike}")
        
        if engine.spot_ltp > 0:
            print("\n🎉 Engine is WORKING correctly.")
        else:
            print("\n⚠️ Engine initialized, but returned 0 values. Market might be closed or API invalid.")
            
    except Exception as e:
        print(f"\n❌ DIAGNOSTIC FAILED: {e}")