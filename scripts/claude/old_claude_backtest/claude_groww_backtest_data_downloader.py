"""
GROWW BACKTEST DATA DOWNLOADER v2.0
====================================
Downloads BOTH Spot and Futures data and creates ONE final CSV

Final CSV contains:
- Spot data:  close (for RSI, EMA, ATM Strike)
- Futures data: volume, oi (for VWAP)

Current Date: 2025-12-27
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from growwapi import GrowwAPI
import time
import os


class GrowwBacktestDataDownloader:
    """
    Downloads complete data for backtesting from Groww API
    """
    
    def __init__(self, api_key:  str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.groww = None
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
            print(f"❌ Connection Error: {e}")
            raise
    
    def _get_futures_symbol(self, date: datetime) -> str:
        """
        Get futures symbol for a given date
        Monthly expiry is LAST TUESDAY of each month
        """
        year = date.year
        month = date.month
        
        # Find last Tuesday of current month
        # Start from last day of month and go backwards
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        
        last_day = next_month - timedelta(days=1)
        
        # Find last Tuesday (weekday 1 = Tuesday)
        days_since_tuesday = (last_day.weekday() - 1) % 7
        last_tuesday = last_day - timedelta(days=days_since_tuesday)
        
        # If current date is AFTER this month's expiry, use next month's expiry
        if date.date() > last_tuesday.date():
            # Move to next month
            if month == 12:
                month = 1
                year += 1
            else: 
                month += 1
            
            # Find last Tuesday of next month
            if month == 12:
                next_month = datetime(year + 1, 1, 1)
            else:
                next_month = datetime(year, month + 1, 1)
            
            last_day = next_month - timedelta(days=1)
            days_since_tuesday = (last_day.weekday() - 1) % 7
            last_tuesday = last_day - timedelta(days=days_since_tuesday)
        
        # Format: NSE-NIFTY-30Dec25-FUT
        return f"NSE-NIFTY-{last_tuesday.strftime('%d%b%y')}-FUT"
    
    def download_complete_data(self, start_date: str, end_date:  str,
                                output_file: str = None) -> pd.DataFrame:
        """
        Download both SPOT and FUTURES data, merge them into one CSV
        
        Parameters:
        -----------
        start_date : str
            Start date in YYYY-MM-DD format
        end_date : str
            End date in YYYY-MM-DD format
        output_file :  str
            Path to save final CSV
            
        Returns: 
        --------
        pd.DataFrame with columns: 
            datetime, open, high, low, close (from SPOT)
            volume, oi, vwap (from FUTURES)
        """
        print("\n" + "=" * 60)
        print("📥 GROWW BACKTEST DATA DOWNLOADER v2.0")
        print("=" * 60)
        print(f"📅 Date Range: {start_date} to {end_date}")
        print("=" * 60)
        
        # Download both
        print("\n📊 STEP 1: Downloading SPOT data (for RSI, EMA, ATM)...")
        spot_df = self._download_spot(start_date, end_date)
        
        print("\n📊 STEP 2: Downloading FUTURES data (for VWAP, Volume, OI)...")
        futures_df = self._download_futures(start_date, end_date)
        
        # Merge
        print("\n📊 STEP 3: Merging data...")
        final_df = self._merge_data(spot_df, futures_df)
        
        # Calculate VWAP
        print("\n📊 STEP 4: Calculating VWAP...")
        final_df = self._calculate_vwap(final_df)
        
        # Save
        if output_file:
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
            final_df.to_csv(output_file, index=False)
            print(f"\n✅ Final CSV saved:  {output_file}")
        
        # Summary
        self._print_summary(final_df)
        
        return final_df
    
    def _download_spot(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Download NIFTY Spot/Index data"""
        all_data = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        total_days = (end - current).days + 1
        day_count = 0
        
        while current <= end: 
            day_count += 1
            
            # Skip weekends
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            
            try:
                day_start = current.replace(hour=9, minute=15, second=0)
                day_end = current.replace(hour=15, minute=30, second=0)
                
                resp = self.groww.get_historical_candles(
                    "NSE",
                    "CASH",
                    "NSE-NIFTY",
                    day_start.strftime("%Y-%m-%d %H:%M:%S"),
                    day_end.strftime("%Y-%m-%d %H:%M:%S"),
                    "1minute"
                )
                
                if resp and 'candles' in resp and len(resp['candles']) > 0:
                    df_day = pd.DataFrame(resp['candles'])
                    all_data.append(df_day)
                    print(f"   ✓ SPOT {current.strftime('%Y-%m-%d')}: {len(df_day)} candles")
                else:
                    print(f"   ✗ SPOT {current.strftime('%Y-%m-%d')}: No data")
                
                time.sleep(0.3)
                
            except Exception as e:
                print(f"   ⚠️ SPOT {current.strftime('%Y-%m-%d')}: {e}")
            
            current += timedelta(days=1)
        
        if not all_data:
            print("❌ No spot data fetched!")
            return pd.DataFrame()
        
        df = pd.concat(all_data, ignore_index=True)
        
        # Format columns
        cols = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'oi']
        df.columns = cols[: len(df.columns)]
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        for col in ['open', 'high', 'low', 'close']: 
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Drop spot volume/oi (they are empty anyway)
        df = df[['datetime', 'open', 'high', 'low', 'close']]
        
        print(f"   📊 Total SPOT candles: {len(df):,}")
        
        return df.sort_values('datetime').reset_index(drop=True)
    
    def _download_futures(self, start_date: str, end_date:  str) -> pd.DataFrame:
        """Download NIFTY Futures data with full OHLC"""
        all_data = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current <= end:
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            
            try:
                fut_symbol = self._get_futures_symbol(current)
                
                day_start = current.replace(hour=9, minute=15, second=0)
                day_end = current.replace(hour=15, minute=30, second=0)
                
                resp = self.groww.get_historical_candles(
                    "NSE",
                    "FNO",
                    fut_symbol,
                    day_start.strftime("%Y-%m-%d %H:%M:%S"),
                    day_end.strftime("%Y-%m-%d %H:%M:%S"),
                    "1minute"
                )
                
                if resp and 'candles' in resp and len(resp['candles']) > 0:
                    df_day = pd.DataFrame(resp['candles'])
                    df_day['fut_symbol'] = fut_symbol
                    all_data.append(df_day)
                    print(f"   ✓ FUT {current.strftime('%Y-%m-%d')} [{fut_symbol[-12:]}]:  {len(df_day)} candles")
                else: 
                    print(f"   ✗ FUT {current.strftime('%Y-%m-%d')}: No data")
                
                time.sleep(0.3)
                
            except Exception as e:
                print(f"   ⚠️ FUT {current.strftime('%Y-%m-%d')}: {e}")
            
            current += timedelta(days=1)
        
        if not all_data: 
            print("❌ No futures data fetched!")
            return pd.DataFrame()
        
        df = pd.concat(all_data, ignore_index=True)
        
        # Format columns - KEEP ALL OHLC
        cols = ['datetime', 'fut_open', 'fut_high', 'fut_low', 'fut_close', 'volume']
        if len(df.columns) >= 7:
            cols.append('oi')
        if len(df.columns) >= 8:
            cols.append('fut_symbol')
        
        df.columns = cols[: len(df.columns)]
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        for col in ['fut_open', 'fut_high', 'fut_low', 'fut_close', 'volume']: 
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'oi' in df.columns:
            df['oi'] = pd.to_numeric(df['oi'], errors='coerce').fillna(0)
        else:
            df['oi'] = 0
        
        # Keep full OHLC for VWAP
        keep_cols = ['datetime', 'fut_open', 'fut_high', 'fut_low', 'fut_close', 'volume', 'oi']
        df = df[[c for c in keep_cols if c in df.columns]]
        
        print(f"   📊 Total FUTURES candles: {len(df):,}")
        
        return df.sort_values('datetime').reset_index(drop=True)
    
    def _merge_data(self, spot_df: pd.DataFrame, futures_df: pd.DataFrame) -> pd.DataFrame:
        """Merge spot and futures data on datetime"""
        
        if spot_df.empty:
            print("❌ Cannot merge:  Spot data is empty")
            return pd.DataFrame()
        
        if futures_df.empty:
            print("⚠️ Futures data empty - using spot only (no VWAP)")
            spot_df['volume'] = 0
            spot_df['oi'] = 0
            spot_df['fut_open'] = spot_df['open']
            spot_df['fut_high'] = spot_df['high']
            spot_df['fut_low'] = spot_df['low']
            spot_df['fut_close'] = spot_df['close']
            return spot_df
        
        # Merge on datetime
        merged = pd.merge(
            spot_df,
            futures_df,
            on='datetime',
            how='left'
        )
        
        # Fill missing futures data with spot data
        merged['volume'] = merged['volume'].fillna(0)
        merged['oi'] = merged['oi'].fillna(0)
        merged['fut_open'] = merged['fut_open'].fillna(merged['open'])
        merged['fut_high'] = merged['fut_high'].fillna(merged['high'])
        merged['fut_low'] = merged['fut_low'].fillna(merged['low'])
        merged['fut_close'] = merged['fut_close'].fillna(merged['close'])
        
        print(f"   ✅ Merged:  {len(merged):,} rows")
        print(f"   ✅ With volume data: {(merged['volume'] > 0).sum():,} rows")
        
        return merged
    
    def _calculate_vwap(self, df:  pd.DataFrame) -> pd.DataFrame:
        """
        Calculate VWAP using FUTURES OHLC and volume
        This matches Groww's VWAP exactly
        """
        
        df = df.copy()
        df['date'] = pd.to_datetime(df['datetime']).dt.date
        
        if df['volume'].sum() == 0:
            print("   ⚠️ No volume data - VWAP will use simple mean")
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            df['vwap'] = df.groupby('date')['typical_price'].transform(
                lambda x: x.expanding().mean()
            )
        else:
            # Typical price from FUTURES OHLC
            df['typical_price'] = (df['fut_high'] + df['fut_low'] + df['fut_close']) / 3
            
            # VWAP = cumulative(TP * Volume) / cumulative(Volume)
            df['tp_vol'] = df['typical_price'] * df['volume']
            df['cum_tp_vol'] = df.groupby('date')['tp_vol'].cumsum()
            df['cum_vol'] = df.groupby('date')['volume'].cumsum()
            
            df['vwap'] = df['cum_tp_vol'] / df['cum_vol'].replace(0, np.nan)
            df['vwap'] = df['vwap'].ffill()
            
            # Cleanup temp columns
            df = df.drop(columns=['tp_vol', 'cum_tp_vol', 'cum_vol', 'typical_price'])
        
        df = df.drop(columns=['date'])
        
        print(f"   ✅ VWAP calculated (using futures OHLC)")
        
        return df
    
    def _print_summary(self, df:  pd.DataFrame):
        """Print data summary"""
        print("\n" + "=" * 60)
        print("📊 FINAL DATA SUMMARY")
        print("=" * 60)
        print(f"Total Candles:      {len(df):,}")
        print(f"Date Range:        {df['datetime'].min()} to {df['datetime'].max()}")
        print(f"Trading Days:      {df['datetime'].dt.date.nunique()}")
        print(f"Rows with Volume:  {(df['volume'] > 0).sum():,}")
        print(f"Rows with OI:      {(df['oi'] > 0).sum():,}")
        print(f"VWAP Valid:        {df['vwap'].notna().sum():,}")
        
        print("\n📈 Columns in final CSV:")
        for col in df.columns:
            print(f"   - {col}")
        
        print("\n📋 Sample Data (first 5 rows):")
        print(df.head().to_string())
        
        print("\n📋 Sample Data (last 5 rows):")
        print(df.tail().to_string())
        print("=" * 60)


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__": 
    
    # ========================================
    # CONFIGURATION - EDIT THIS
    # ========================================
    
    API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
    API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
    
    # Date range (1 month back from today:  2025-12-27)
    START_DATE = "2025-11-24"
    END_DATE = "2025-12-27"
    
    # Output file
    OUTPUT_FILE = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\data\\nifty_complete_1min.csv"
    
    # ========================================
    # RUN
    # ========================================
    
    downloader = GrowwBacktestDataDownloader(API_KEY, API_SECRET)
    
    df = downloader.download_complete_data(
        start_date=START_DATE,
        end_date=END_DATE,
        output_file=OUTPUT_FILE
    )
    
    print("\n✅ DONE!  Use this file for backtesting:")
    print(f"   {OUTPUT_FILE}")