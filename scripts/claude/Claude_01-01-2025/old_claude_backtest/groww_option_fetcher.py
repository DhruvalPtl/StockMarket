"""
GROWW OPTION FETCHER
====================
Fetches real option prices from Groww API for backtesting
Includes caching to minimize API calls

Author: Claude
Date: 2025-12-27
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from growwapi import GrowwAPI
import time
import os
import json


class GrowwOptionFetcher: 
    """
    Fetches real option data from Groww API with caching
    """
    
    def __init__(self, api_key: str, api_secret: str, cache_dir: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.groww = None
        
        # Invalid expiry dates (not trading days / no expiry on these dates)
        self.invalid_expiries = {
            "2025-12-24",  # Wednesday, no expiry
            "2025-12-25",  # Christmas
            "2025-12-31",  # New Year Eve
            "2025-01-01",  # New Year
            # Add more as needed
        }
        
        # Cache settings
        if cache_dir is None:
            cache_dir = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\option_cache"
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # In-memory cache for current session
        self.memory_cache = {}
        
        # Expiry cache
        self.expiry_cache = {}
        
        # API call counter
        self.api_calls = 0
        self.cache_hits = 0
        
        self._connect()
    
    def _connect(self):
        """Connect to Groww API"""
        try: 
            token = GrowwAPI.get_access_token(
                api_key=self.api_key,
                secret=self.api_secret
            )
            self.groww = GrowwAPI(token)
            print("✅ Option Fetcher connected to Groww API")
        except Exception as e:
            print(f"❌ Option Fetcher connection error: {e}")
            raise
    
    def _get_cache_key(self, strike: int, option_type: str, date: str) -> str:
        """Generate cache key for option data"""
        return f"NIFTY_{strike}_{option_type}_{date}"
    
    def _get_cache_file(self, strike:  int, option_type: str, expiry: str) -> str:
        """Get cache file path"""
        return os.path.join(
            self.cache_dir,
            f"NIFTY_{strike}_{option_type}_{expiry.replace('-', '')}.csv"
        )
    
    def _get_weekly_expiry(self, date: datetime) -> str:
        """
        Get weekly expiry date for a given date
        Weekly expiry is every Thursday
        """
        # Find next Thursday
        days_until_thursday = (3 - date.weekday()) % 7
        if days_until_thursday == 0:
            # If it's Thursday after 3:30 PM, use next week
            if date.hour >= 15 and date.minute >= 30:
                days_until_thursday = 7
        
        expiry = date + timedelta(days=days_until_thursday)
        return expiry.strftime("%Y-%m-%d")
    
    def _format_expiry_for_symbol(self, expiry_date: str) -> str:
        """
        Format expiry date for Groww symbol
        Input: 2025-12-26
        Output: 26Dec25
        """
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        return dt.strftime("%d%b%y")
    
    def _build_option_symbol(self, strike:  int, option_type: str, expiry: str) -> str:
        """
        Build Groww option symbol
        Example: NSE-NIFTY-26Dec25-24000-CE
        """
        expiry_formatted = self._format_expiry_for_symbol(expiry)
        return f"NSE-NIFTY-{expiry_formatted}-{strike}-{option_type}"
    
    def get_expiry_for_date(self, dt: datetime) -> str:
        """Get the correct expiry for a trading date"""
        date_str = dt. strftime("%Y-%m-%d")
        
        # Check cache first
        if date_str in self.expiry_cache: 
            return self.expiry_cache[date_str]
        
        try:
            year = dt.year
            month = dt.month
            
            resp = self.groww.get_expiries(
                exchange="NSE",
                underlying_symbol="NIFTY",
                year=year,
                month=month
            )
            
            all_expiries = []
            
            if resp and 'expiries' in resp:
                all_expiries.extend(resp['expiries'])
            
            # Also get next month
            if month == 12:
                next_month, next_year = 1, year + 1
            else: 
                next_month, next_year = month + 1, year
            
            try:
                resp2 = self.groww.get_expiries(
                    exchange="NSE",
                    underlying_symbol="NIFTY",
                    year=next_year,
                    month=next_month
                )
                if resp2 and 'expiries' in resp2:
                    all_expiries. extend(resp2['expiries'])
            except:
                pass
            
            # Sort and filter out invalid expiries
            all_expiries = sorted(set(all_expiries))
            all_expiries = [exp for exp in all_expiries if exp not in self.invalid_expiries]
            
            # Find first expiry >= current date
            for exp in all_expiries:
                if exp >= date_str: 
                    self.expiry_cache[date_str] = exp
                    return exp
            
            if all_expiries: 
                return all_expiries[-1]
                
        except Exception as e:
            print(f"⚠️ Error getting expiry:  {e}")
        
        return self._get_weekly_expiry(dt)
    
    def fetch_option_data(self, strike: int, option_type:  str, 
                          date: datetime, expiry: str = None) -> Optional[pd.DataFrame]:
        """
        Fetch option data for a specific strike, type, and date
        Returns DataFrame with columns: datetime, open, high, low, close, volume, oi
        """
        if expiry is None:
            expiry = self.get_expiry_for_date(date)
        
        cache_file = self._get_cache_file(strike, option_type, expiry)
        
        # Check file cache
        if os.path.exists(cache_file):
            self.cache_hits += 1
            df = pd.read_csv(cache_file)
            df['datetime'] = pd.to_datetime(df['datetime'])
            return df
        
        # Check memory cache
        cache_key = f"{strike}_{option_type}_{expiry}"
        if cache_key in self.memory_cache:
            self.cache_hits += 1
            return self.memory_cache[cache_key]
        
        # Fetch from API
        try:
            symbol = self._build_option_symbol(strike, option_type, expiry)
            print(f"🔍 Fetching:  {symbol} for expiry {expiry}")
            # Get data for the entire expiry period (up to 7 days before expiry)
            expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
            start_dt = expiry_dt - timedelta(days=6)
            
            # Adjust start if it's before the expiry period
            if date < start_dt: 
                start_dt = date
            
            start_str = start_dt.strftime("%Y-%m-%d 09:15:00")
            end_str = expiry_dt.strftime("%Y-%m-%d 15:30:00")
            
            self.api_calls += 1
            
            resp = self.groww.get_historical_candles(
                exchange="NSE",
                segment="FNO",
                groww_symbol=symbol,
                start_time=start_str,
                end_time=end_str,
                candle_interval="1minute"
            )
            
            if resp and 'candles' in resp and len(resp['candles']) > 0:
                df = pd.DataFrame(resp['candles'], 
                    columns=['datetime', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                
                # Save to file cache
                df.to_csv(cache_file, index=False)
                
                # Save to memory cache
                self.memory_cache[cache_key] = df
                
                return df
            else:
                return None
                
        except Exception as e: 
            print(f"⚠️ Error fetching {strike} {option_type}:  {e}")
            return None
        
        finally: 
            # Rate limiting
            time.sleep(0.2)
    
    def get_option_price_at_time(self, strike:  int, option_type: str,
                                  dt: datetime, expiry: str = None) -> Optional[Dict]:
        """
        Get option price at a specific datetime
        Returns dict with:  open, high, low, close, volume, oi
        """
        df = self.fetch_option_data(strike, option_type, dt, expiry)
        
        if df is None or df.empty:
            return None
        
        # Find the exact candle or nearest one
        target_time = pd.Timestamp(dt)
        
        # Try exact match first
        exact = df[df['datetime'] == target_time]
        if not exact.empty:
            row = exact.iloc[0]
            return {
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close':  float(row['close']),
                'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                'oi': int(row['oi']) if pd.notna(row['oi']) else 0
            }
        
        # Try nearest before
        before = df[df['datetime'] <= target_time]
        if not before.empty:
            row = before.iloc[-1]
            return {
                'open': float(row['open']),
                'high': float(row['high']),
                'low':  float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                'oi':  int(row['oi']) if pd.notna(row['oi']) else 0
            }
        
        return None
    
    def get_option_chain_oi(self, spot_price: float, dt: datetime, 
                            num_strikes: int = 10) -> Dict:
        """
        Get OI for multiple strikes to calculate PCR
        Returns dict with: ce_oi_total, pe_oi_total, pcr
        """
        atm = round(spot_price / 50) * 50
        expiry = self.get_expiry_for_date(dt)
        
        ce_oi_total = 0
        pe_oi_total = 0
        
        strikes = []
        for i in range(-num_strikes, num_strikes + 1):
            strikes.append(atm + (i * 50))
        
        for strike in strikes: 
            # Get CE OI
            ce_data = self.get_option_price_at_time(strike, 'CE', dt, expiry)
            if ce_data: 
                ce_oi_total += ce_data['oi']
            
            # Get PE OI
            pe_data = self.get_option_price_at_time(strike, 'PE', dt, expiry)
            if pe_data:
                pe_oi_total += pe_data['oi']
        
        pcr = pe_oi_total / ce_oi_total if ce_oi_total > 0 else 1.0
        
        return {
            'ce_oi_total': ce_oi_total,
            'pe_oi_total': pe_oi_total,
            'pcr': round(pcr, 4)
        }
    
    def find_affordable_strike(self, spot_price: float, option_type: str,
                                dt: datetime, capital: float, lot_size: int,
                                min_price: float = 50) -> Optional[Dict]:
        """
        Find an affordable strike within capital limits
        
        Logic:
        1.Try ATM first
        2.If too expensive → Try 1 OTM
        3.If too cheap → Try 1 ITM
        
        Returns dict with:  strike, price, cost, strike_type (ATM/OTM/ITM)
        """
        atm = round(spot_price / 50) * 50
        expiry = self.get_expiry_for_date(dt)
        
        max_cost = capital * 0.95  # Use 95% of capital max
        
        # Define strike order based on option type
        if option_type == 'CE': 
            # CE: OTM is higher strike, ITM is lower strike
            strikes_to_try = [
                (atm, 'ATM'),
                (atm + 50, 'OTM'),
                (atm - 50, 'ITM')
            ]
        else:  # PE
            # PE: OTM is lower strike, ITM is higher strike
            strikes_to_try = [
                (atm, 'ATM'),
                (atm - 50, 'OTM'),
                (atm + 50, 'ITM')
            ]
        
        for strike, strike_type in strikes_to_try: 
            data = self.get_option_price_at_time(strike, option_type, dt, expiry)
            
            if data is None:
                continue
            
            price = data['close']
            cost = price * lot_size
            
            # Check if affordable and not too cheap
            if cost <= max_cost and price >= min_price: 
                return {
                    'strike':  strike,
                    'price': price,
                    'cost': cost,
                    'strike_type': strike_type,
                    'oi': data['oi'],
                    'volume': data['volume'],
                    'expiry': expiry
                }
        
        # No affordable strike found
        return None
    
    def print_stats(self):
        """Print API usage stats"""
        total = self.api_calls + self.cache_hits
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        
        print(f"\n📊 Option Fetcher Stats:")
        print(f"   API Calls: {self.api_calls}")
        print(f"   Cache Hits: {self.cache_hits}")
        print(f"   Hit Rate: {hit_rate:.1f}%")