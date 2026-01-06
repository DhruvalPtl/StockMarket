"""
UNIFIED OPTION FETCHER
======================
Option data fetcher that works with both Groww and Flate Trade APIs.
Port of groww_option_fetcher.py using UnifiedAPI.

Features:
- Same interface as GrowwOptionFetcher
- Works with both Groww and Flate Trade
- Caching mechanism to minimize API calls
- Same method signatures for drop-in replacement

Usage:
    # Groww
    fetcher = UnifiedOptionFetcher(
        provider="groww",
        api_key=key,
        api_secret=secret
    )
    
    # Flate Trade
    fetcher = UnifiedOptionFetcher(
        provider="flate",
        user_id=uid,
        user_token=token
    )
    
    # Both work identically
    data = fetcher.fetch_option_data(strike=24000, option_type="CE", date=datetime.now())

Author: Claude
Date: 2026-01-06
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import time
import os
import json

# Import unified API
try:
    from unified_api import UnifiedAPI
except ImportError:
    from .unified_api import UnifiedAPI


class UnifiedOptionFetcher:
    """
    Fetches option data from either Groww or Flate Trade API with caching.
    
    Drop-in replacement for GrowwOptionFetcher.
    """
    
    def __init__(self, provider: str = "groww", cache_dir: str = None, **api_credentials):
        """
        Initialize option fetcher
        
        Args:
            provider: "groww" or "flate"
            cache_dir: Directory for caching option data
            **api_credentials: API credentials (varies by provider)
        """
        self.provider = provider
        self.api = None
        
        # Invalid expiry dates (not trading days / no expiry on these dates)
        self.invalid_expiries = {
            "2025-12-24",  # Wednesday, no expiry
            "2025-12-25",  # Christmas
            "2025-12-31",  # New Year Eve
            "2025-01-01",  # New Year
            "2026-01-26",  # Republic Day
            # Add more as needed
        }
        
        # Cache settings
        if cache_dir is None:
            cache_dir = os.path.join(
                os.path.dirname(__file__),
                "cache",
                f"{provider}_option_cache"
            )
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # In-memory cache for current session
        self.memory_cache = {}
        
        # Expiry cache
        self.expiry_cache = {}
        
        # API call counter
        self.api_calls = 0
        self.cache_hits = 0
        
        self._connect(**api_credentials)
    
    def _connect(self, **api_credentials):
        """Connect to API"""
        try:
            self.api = UnifiedAPI(provider=self.provider, **api_credentials)
            print(f"✅ Option Fetcher connected to {self.provider.upper()} API")
        except Exception as e:
            print(f"❌ Option Fetcher connection error: {e}")
            raise
    
    def _get_cache_key(self, strike: int, option_type: str, date: str) -> str:
        """Generate cache key for option data"""
        return f"NIFTY_{strike}_{option_type}_{date}"
    
    def _get_cache_file(self, strike: int, option_type: str, expiry: str) -> str:
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
        Format expiry date for symbol
        Input: 2025-12-26
        Output: 26Dec25
        """
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        return dt.strftime("%d%b%y")
    
    def _build_option_symbol(self, strike: int, option_type: str, expiry: str) -> str:
        """
        Build option symbol (Groww format)
        Example: NSE-NIFTY-26Dec25-24000-CE
        """
        expiry_formatted = self._format_expiry_for_symbol(expiry)
        return f"NSE-NIFTY-{expiry_formatted}-{strike}-{option_type}"
    
    def get_expiry_for_date(self, dt: datetime) -> str:
        """Get the correct expiry for a trading date"""
        date_str = dt.strftime("%Y-%m-%d")
        
        # Check cache first
        if date_str in self.expiry_cache:
            return self.expiry_cache[date_str]
        
        try:
            year = dt.year
            month = dt.month
            
            resp = self.api.get_expiries(
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
                resp2 = self.api.get_expiries(
                    exchange="NSE",
                    underlying_symbol="NIFTY",
                    year=next_year,
                    month=next_month
                )
                if resp2 and 'expiries' in resp2:
                    all_expiries.extend(resp2['expiries'])
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
            print(f"⚠️ Error getting expiry: {e}")
        
        return self._get_weekly_expiry(dt)
    
    def fetch_option_data(self, strike: int, option_type: str,
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
            
            # Get data for the specific date
            start = date.replace(hour=9, minute=15, second=0)
            end = date.replace(hour=15, minute=30, second=0)
            
            self.api_calls += 1
            
            resp = self.api.get_historical_candles(
                "NSE", "FNO", symbol,
                start.strftime("%Y-%m-%d %H:%M:%S"),
                end.strftime("%Y-%m-%d %H:%M:%S"),
                "1minute"
            )
            
            if not resp or 'candles' not in resp or len(resp['candles']) == 0:
                print(f"⚠️ No data for {symbol} on {date.strftime('%Y-%m-%d')}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(resp['candles'])
            
            # Ensure correct columns
            if 't' not in df.columns and len(df.columns) >= 6:
                cols = ['t', 'o', 'h', 'l', 'c', 'v']
                if len(df.columns) >= 7:
                    cols.append('oi')
                df.columns = cols[:len(df.columns)]
            
            # Rename for consistency
            df = df.rename(columns={
                't': 'datetime',
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume',
                'oi': 'oi'
            })
            
            # Ensure datetime column
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
            
            # Save to cache
            df.to_csv(cache_file, index=False)
            self.memory_cache[cache_key] = df
            
            print(f"✅ Fetched {len(df)} candles for {symbol}")
            
            # Rate limiting
            time.sleep(0.5)
            
            return df
            
        except Exception as e:
            print(f"❌ Error fetching option data: {e}")
            return None
    
    def get_ltp(self, strike: int, option_type: str, expiry: str) -> float:
        """
        Get last traded price for an option
        
        Args:
            strike: Strike price
            option_type: "CE" or "PE"
            expiry: Expiry date "YYYY-MM-DD"
            
        Returns:
            Last traded price
        """
        try:
            symbol = self._build_option_symbol(strike, option_type, expiry)
            
            self.api_calls += 1
            resp = self.api.get_ltp("NSE", symbol, "FNO")
            
            if resp and 'ltp' in resp:
                return float(resp['ltp'])
            else:
                return 0.0
                
        except Exception as e:
            print(f"❌ LTP fetch error: {e}")
            return 0.0
    
    def get_option_chain(self, expiry: str, strike_range: int = 500) -> pd.DataFrame:
        """
        Get option chain for a specific expiry
        
        Args:
            expiry: Expiry date "YYYY-MM-DD"
            strike_range: Range around ATM (default: 500 points)
            
        Returns:
            DataFrame with option chain data
        """
        try:
            self.api_calls += 1
            chain = self.api.get_option_chain("NSE", "NIFTY", expiry)
            
            if not chain or 'strikes' not in chain:
                return pd.DataFrame()
            
            # Convert to DataFrame
            rows = []
            for strike_str, data in chain['strikes'].items():
                strike = float(strike_str)
                
                ce_data = data.get('CE', {})
                pe_data = data.get('PE', {})
                
                row = {
                    'strike': strike,
                    'ce_ltp': ce_data.get('ltp', 0),
                    'ce_oi': ce_data.get('open_interest', 0),
                    'ce_volume': ce_data.get('volume', 0),
                    'ce_iv': ce_data.get('greeks', {}).get('iv', 0),
                    'pe_ltp': pe_data.get('ltp', 0),
                    'pe_oi': pe_data.get('open_interest', 0),
                    'pe_volume': pe_data.get('volume', 0),
                    'pe_iv': pe_data.get('greeks', {}).get('iv', 0),
                }
                rows.append(row)
            
            df = pd.DataFrame(rows)
            df = df.sort_values('strike')
            
            return df
            
        except Exception as e:
            print(f"❌ Option chain fetch error: {e}")
            return pd.DataFrame()
    
    def get_stats(self) -> Dict:
        """Get fetcher statistics"""
        return {
            'provider': self.provider,
            'api_calls': self.api_calls,
            'cache_hits': self.cache_hits,
            'cache_hit_rate': f"{(self.cache_hits / max(self.api_calls + self.cache_hits, 1)) * 100:.1f}%",
            'cache_dir': self.cache_dir
        }


# For backward compatibility
GrowwOptionFetcher = UnifiedOptionFetcher


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    """Test the option fetcher"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Unified Option Fetcher')
    parser.add_argument('--api', type=str, default='groww', choices=['groww', 'flate'],
                       help='API provider to use (groww or flate)')
    
    args = parser.parse_args()
    
    print(f"🧪 Testing Unified Option Fetcher with {args.api.upper()} API\n")
    
    # Prepare credentials
    try:
        from config import BotConfig
        
        if args.api == 'groww':
            credentials = {
                'api_key': BotConfig.GROWW_API_KEY,
                'api_secret': BotConfig.GROWW_API_SECRET
            }
        else:
            credentials = {
                'user_id': BotConfig.USER_ID,
                'user_token': BotConfig.USER_TOKEN
            }
    except ImportError:
        print("❌ Config not found. Please provide credentials manually.")
        credentials = {}
    
    # Initialize fetcher
    fetcher = UnifiedOptionFetcher(provider=args.api, **credentials)
    
    # Test 1: Get expiry
    test_date = datetime.now()
    expiry = fetcher.get_expiry_for_date(test_date)
    print(f"✅ Expiry for {test_date.strftime('%Y-%m-%d')}: {expiry}")
    
    # Test 2: Fetch option data
    strike = 24000
    option_type = "CE"
    print(f"\n📊 Fetching {strike} {option_type} data...")
    
    data = fetcher.fetch_option_data(strike, option_type, test_date)
    if data is not None:
        print(f"✅ Got {len(data)} candles")
        print(data.head())
    else:
        print("❌ No data received")
    
    # Test 3: Get LTP
    ltp = fetcher.get_ltp(strike, option_type, expiry)
    print(f"\n💰 LTP for {strike} {option_type}: ₹{ltp:.2f}")
    
    # Test 4: Get option chain
    print(f"\n📈 Fetching option chain...")
    chain = fetcher.get_option_chain(expiry)
    if not chain.empty:
        print(f"✅ Got chain with {len(chain)} strikes")
        print(chain.head())
    else:
        print("❌ No chain data")
    
    # Print stats
    print(f"\n📊 Fetcher Statistics:")
    stats = fetcher.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
