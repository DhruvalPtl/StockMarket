"""
OPTION FETCHER - Fetch option prices from cache
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict


class OptionFetcher:
    """Fetches option prices from local cache"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self.memory_cache = {}
        self.expiry_cache = {}
        
        # Invalid expiry dates (holidays, non-expiry days)
        self.invalid_expiries = {
            "2025-12-24",  # Not a Thursday
            "2025-12-25",  # Christmas
            "2025-12-31",
            "2025-01-01",
        }
        
        # Stats
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Load available expiries from cache files
        self._load_available_expiries()
    
    def _load_available_expiries(self):
        """Load all available expiries from cache files"""
        self.available_expiries = set()
        
        if not os.path.exists(self.cache_dir):
            print(f"⚠️ Cache directory not found: {self.cache_dir}")
            return
        
        for filename in os.listdir(self.cache_dir):
            if filename.startswith("NIFTY_") and filename.endswith(".csv"):
                # Format: NIFTY_26000_CE_20251125.csv
                parts = filename.replace(".csv", "").split("_")
                if len(parts) >= 4:
                    date_str = parts[3]  # 20251125
                    try:
                        exp = f"{date_str[: 4]}-{date_str[4:6]}-{date_str[6:8]}"
                        self.available_expiries.add(exp)
                    except: 
                        pass
        
        print(f"📅 Loaded {len(self.available_expiries)} expiries from cache")
    
    def get_expiry_for_date(self, dt: datetime) -> str:
        """Get the correct expiry for a trading date"""
        date_str = dt.strftime("%Y-%m-%d")
        
        # Check cache first
        if date_str in self.expiry_cache: 
            return self.expiry_cache[date_str]
        
        # Find first valid expiry >= current date
        valid_expiries = sorted([
            exp for exp in self.available_expiries 
            if exp >= date_str and exp not in self.invalid_expiries
        ])
        
        if valid_expiries: 
            expiry = valid_expiries[0]
            self.expiry_cache[date_str] = expiry
            return expiry
        
        # Fallback:  calculate next Thursday
        return self._calculate_next_thursday(dt)
    
    def _calculate_next_thursday(self, dt: datetime) -> str:
        """Calculate next Thursday expiry"""
        days_until_thursday = (3 - dt.weekday()) % 7
        if days_until_thursday == 0 and dt.hour >= 15:
            days_until_thursday = 7
        next_thursday = dt + timedelta(days=days_until_thursday)
        return next_thursday.strftime("%Y-%m-%d")
    
    def _get_cache_file(self, strike: int, option_type: str, expiry: str) -> str:
        """Get cache file path"""
        expiry_formatted = expiry.replace("-", "")
        return os.path.join(
            self.cache_dir,
            f"NIFTY_{strike}_{option_type}_{expiry_formatted}.csv"
        )
    
    def get_option_price(self, strike: int, option_type:  str, 
                         dt: datetime) -> Optional[Dict]:
        """
        Get option price at specific datetime
        
        Returns:
            Dict with:  close, open, high, low, volume, oi, expiry
            None if not found
        """
        expiry = self.get_expiry_for_date(dt)
        
        # Check memory cache
        cache_key = f"{strike}_{option_type}_{expiry}"
        
        if cache_key not in self.memory_cache:
            # Load from file
            cache_file = self._get_cache_file(strike, option_type, expiry)
            
            if not os.path.exists(cache_file):
                self.cache_misses += 1
                return None
            
            try:
                df = pd.read_csv(cache_file)
                df['datetime'] = pd.to_datetime(df['datetime'])
                self.memory_cache[cache_key] = df
                self.cache_hits += 1
            except Exception as e: 
                self.cache_misses += 1
                return None
        
        df = self.memory_cache[cache_key]
        
        # Find the candle at or before the requested time
        target_time = pd.Timestamp(dt)
        mask = df['datetime'] <= target_time
        
        if not mask.any():
            return None
        
        row = df[mask].iloc[-1]
        
        return {
            "close": float(row['close']),
            "open": float(row['open']),
            "high": float(row['high']),
            "low":  float(row['low']),
            "volume": int(row['volume']) if pd.notna(row['volume']) else 0,
            "oi": int(row['oi']) if pd.notna(row['oi']) else 0,
            "expiry": expiry
        }
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": round(hit_rate, 1)
        }