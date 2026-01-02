"""
OPTION DATA DOWNLOADER
======================
Pre-downloads all option data for backtesting period
Run this ONCE before backtesting - then backtests run instantly! 

Author: Claude
Date: 2025-12-27
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Set
from growwapi import GrowwAPI
import time
import os


class OptionDataDownloader:
    """Downloads all option data for a given period"""
    
    def __init__(self, api_key: str, api_secret: str, cache_dir: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        
        if cache_dir is None:
            cache_dir = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\option_cache"
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        self.groww = None
        self.api_calls = 0
        self.errors = 0
        self.skipped = 0
        
        self._connect()
    
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
            print(f"❌ Connection error: {e}")
            raise
    
    def _format_expiry_for_symbol(self, expiry_date: str) -> str:
        """
        Format expiry date for Groww symbol
        Input: 2025-12-26
        Output: 26Dec25
        """
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        return dt.strftime("%d%b%y")
    
    def _get_cache_file(self, strike: int, option_type: str, expiry: str) -> str:
        """Get cache file path"""
        expiry_formatted = expiry.replace("-", "")
        return os.path.join(
            self.cache_dir,
            f"NIFTY_{strike}_{option_type}_{expiry_formatted}.csv"
        )
    
    def get_expiries_for_period(self, start_date: datetime, end_date:  datetime) -> List[str]:
        """Get all expiries within a date range"""
        expiries = set()
        
        current = start_date
        while current <= end_date:
            year = current.year
            month = current.month
            
            try:
                resp = self.groww.get_expiries(
                    exchange="NSE",
                    underlying_symbol="NIFTY",
                    year=year,
                    month=month
                )
                
                if resp and 'expiries' in resp:
                    for exp in resp['expiries']:
                        exp_dt = datetime.strptime(exp, "%Y-%m-%d")
                        # Only include expiries within our range
                        if start_date <= exp_dt <= end_date + timedelta(days=7):
                            expiries.add(exp)
                
                time.sleep(0.2)
                
            except Exception as e:
                print(f"⚠️ Error getting expiries for {year}-{month}: {e}")
            
            # Move to next month
            if month == 12:
                current = current.replace(year=year + 1, month=1, day=1)
            else:
                current = current.replace(month=month + 1, day=1)
        
        return sorted(list(expiries))
    
    def get_strikes_for_range(self, min_price: float, max_price: float, 
                              buffer: int = 500, step: int = 50) -> List[int]:
        """
        Get all strikes for a price range
        
        Args:
            min_price: Minimum spot price in period
            max_price: Maximum spot price in period
            buffer:  Extra points above/below range
            step: Strike step (50 for NIFTY)
        """
        min_strike = int((min_price - buffer) // step * step)
        max_strike = int((max_price + buffer) // step * step)
        
        strikes = list(range(min_strike, max_strike + step, step))
        return strikes
    
    def download_option(self, strike: int, option_type:  str, expiry:  str) -> bool:
        """
        Download option data for a specific strike, type, and expiry
        Returns True if successful or already cached
        """
        cache_file = self._get_cache_file(strike, option_type, expiry)
        
        # Skip if already cached
        if os.path.exists(cache_file):
            self.skipped += 1
            return True
        
        try:
            # Build symbol
            expiry_formatted = self._format_expiry_for_symbol(expiry)
            symbol = f"NSE-NIFTY-{expiry_formatted}-{strike}-{option_type}"
            
            # Calculate date range (7 days before expiry to expiry)
            expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
            start_dt = expiry_dt - timedelta(days=6)
            
            start_str = start_dt.strftime("%Y-%m-%d") + " 09:15:00"
            end_str = expiry_dt.strftime("%Y-%m-%d") + " 15:30:00"
            
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
                df.to_csv(cache_file, index=False)
                return True
            else: 
                # No data available for this strike
                return False
            
        except Exception as e:
            self.errors += 1
            if "No data" not in str(e) and "not found" not in str(e).lower():
                print(f"   ⚠️ Error {strike} {option_type}:  {e}")
            return False
        
        finally:
            # Rate limiting
            time.sleep(0.15)
    
    def download_all(self, spot_data_file: str, verbose: bool = True):
        """
        Download all option data based on spot price range
        
        Args:
            spot_data_file: Path to CSV with spot/futures data
            verbose: Print progress
        """
        print("\n" + "=" * 70)
        print("📥 OPTION DATA DOWNLOADER")
        print("=" * 70)
        
        # Load spot data to find price range
        print(f"\n📂 Loading spot data:  {spot_data_file}")
        df = pd.read_csv(spot_data_file)
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        start_date = df['datetime'].min()
        end_date = df['datetime'].max()
        min_price = df['close'].min()
        max_price = df['close'].max()
        
        print(f"   Period: {start_date.date()} to {end_date.date()}")
        print(f"   Price Range: {min_price:.0f} to {max_price:.0f}")
        
        # Get expiries
        print(f"\n📅 Finding expiries...")
        expiries = self.get_expiries_for_period(start_date, end_date)
        print(f"   Found {len(expiries)} expiries: {expiries}")
        
        # Get strikes
        print(f"\n🎯 Calculating strikes...")
        strikes = self.get_strikes_for_range(min_price, max_price, buffer=500)
        print(f"   Strikes: {strikes[0]} to {strikes[-1]} ({len(strikes)} strikes)")
        
        # Calculate total downloads
        total_contracts = len(expiries) * len(strikes) * 2  # CE + PE
        print(f"\n📊 Total contracts to download: {total_contracts}")
        print(f"   Estimated time: {total_contracts * 0.2 / 60:.1f} minutes")
        
        # Confirm
        print("\n" + "-" * 70)
        input("Press ENTER to start downloading (Ctrl+C to cancel)...")
        print("-" * 70)
        
        # Download
        start_time = time.time()
        downloaded = 0
        
        for exp_idx, expiry in enumerate(expiries):
            print(f"\n📅 Expiry {exp_idx + 1}/{len(expiries)}: {expiry}")
            
            exp_downloaded = 0
            exp_skipped = 0
            
            for strike in strikes:
                for option_type in ['CE', 'PE']:
                    cache_file = self._get_cache_file(strike, option_type, expiry)
                    
                    if os.path.exists(cache_file):
                        exp_skipped += 1
                        continue
                    
                    success = self.download_option(strike, option_type, expiry)
                    if success:
                        exp_downloaded += 1
                        downloaded += 1
                    
                    # Progress
                    if verbose and (exp_downloaded + exp_skipped) % 20 == 0:
                        elapsed = time.time() - start_time
                        rate = self.api_calls / elapsed if elapsed > 0 else 0
                        print(f"   Progress: {exp_downloaded} downloaded, {exp_skipped} cached | "
                              f"API calls: {self.api_calls} | Rate: {rate:.1f}/sec")
            
            print(f"   ✅ Expiry complete:  {exp_downloaded} new, {exp_skipped} cached")
        
        # Summary
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 70)
        print("✅ DOWNLOAD COMPLETE!")
        print("=" * 70)
        print(f"   Total API Calls: {self.api_calls}")
        print(f"   New Downloads: {downloaded}")
        print(f"   Already Cached: {self.skipped}")
        print(f"   Errors: {self.errors}")
        print(f"   Time: {elapsed / 60:.1f} minutes")
        print(f"   Cache Directory: {self.cache_dir}")
        print("=" * 70)
        
        # Count cache files
        cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith('.csv')]
        print(f"\n📁 Total cached files: {len(cache_files)}")
    
    def download_for_pcr(self, spot_data_file: str, num_strikes: int = 10):
        """
        Download option data specifically for PCR calculation
        Downloads OI data for strikes around ATM
        """
        print("\n" + "=" * 70)
        print("📥 DOWNLOADING PCR DATA")
        print("=" * 70)
        
        # Load spot data
        df = pd.read_csv(spot_data_file)
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        # Get unique dates and ATM strikes
        df['date'] = df['datetime'].dt.date
        df['atm'] = (df['close'] / 50).round() * 50
        
        daily_atm = df.groupby('date')['atm'].first().to_dict()
        
        print(f"   Trading days: {len(daily_atm)}")
        
        # Get expiries
        start_date = df['datetime'].min()
        end_date = df['datetime'].max()
        expiries = self.get_expiries_for_period(start_date, end_date)
        
        # For each day, download ATM +/- num_strikes
        all_strikes_to_download = set()
        
        for date, atm in daily_atm.items():
            atm = int(atm)
            for i in range(-num_strikes, num_strikes + 1):
                all_strikes_to_download.add(atm + i * 50)
        
        strikes = sorted(list(all_strikes_to_download))
        print(f"   Strikes for PCR: {len(strikes)}")
        
        # Download
        total = len(expiries) * len(strikes) * 2
        print(f"   Total contracts: {total}")
        
        downloaded = 0
        for expiry in expiries: 
            for strike in strikes:
                for option_type in ['CE', 'PE']:
                    if self.download_option(strike, option_type, expiry):
                        downloaded += 1
        
        print(f"✅ PCR data download complete: {downloaded} contracts")


def main():
    """Main function to run the downloader"""
    
    # ========================================
    # CONFIGURATION
    # ========================================
    
    API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
    API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
    
    SPOT_DATA_FILE = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\data\\nifty_complete_1min.csv"
    
    CACHE_DIR = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\option_cache"
    
    # ========================================
    # RUN DOWNLOADER
    # ========================================
    
    downloader = OptionDataDownloader(
        api_key=API_KEY,
        api_secret=API_SECRET,
        cache_dir=CACHE_DIR
    )
    
    # Download all option data
    downloader.download_all(SPOT_DATA_FILE, verbose=True)


if __name__ == "__main__": 
    main()