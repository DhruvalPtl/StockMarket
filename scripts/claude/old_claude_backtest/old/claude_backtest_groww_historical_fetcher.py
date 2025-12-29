"""
GROWW API HISTORICAL DATA FETCHER
=================================
Fetches historical NIFTY data using your paid Groww API
Prepares data for backtesting
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from growwapi import GrowwAPI
import time
import os


class GrowwHistoricalFetcher:
    """
    Fetch historical data from Groww API for backtesting
    """
    
    def __init__(self, api_key:  str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self. groww = None
        self._connect()
    
    def _connect(self):
        """Connect to Groww API"""
        try: 
            token = GrowwAPI. get_access_token(
                api_key=self.api_key,
                secret=self.api_secret
            )
            self.groww = GrowwAPI(token)
            print("✅ Connected to Groww API")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            raise
    
    def fetch_spot_data(self, start_date: str, end_date: str, 
                        interval: str = "1minute",
                        output_file: str = None) -> pd.DataFrame:
        """
        Fetch NIFTY spot historical data
        
        Parameters:
        -----------
        start_date : str
            Start date in YYYY-MM-DD format
        end_date :  str
            End date in YYYY-MM-DD format
        interval : str
            Candle interval:  "1minute", "5minute", "15minute", "1hour", "1day"
        output_file : str
            Optional CSV file to save data
            
        Returns: 
        --------
        pd.DataFrame with OHLCV data
        """
        print(f"\n📥 Fetching NIFTY Spot Data")
        print(f"   Date Range: {start_date} to {end_date}")
        print(f"   Interval: {interval}")
        
        all_data = []
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current_date <= end_dt:
            # Skip weekends
            if current_date.weekday() >= 5: 
                current_date += timedelta(days=1)
                continue
            
            try:
                # Fetch one day at a time (API might have limits)
                day_start = current_date. replace(hour=9, minute=15, second=0)
                day_end = current_date. replace(hour=15, minute=30, second=0)
                
                resp = self.groww.get_historical_candles(
                    "NSE", 
                    "CASH", 
                    "NSE-NIFTY",
                    day_start.strftime("%Y-%m-%d %H:%M:%S"),
                    day_end.strftime("%Y-%m-%d %H:%M:%S"),
                    interval
                )
                
                if resp and 'candles' in resp and len(resp['candles']) > 0:
                    df_day = pd.DataFrame(resp['candles'])
                    all_data.append(df_day)
                    print(f"   ✓ {current_date.strftime('%Y-%m-%d')}:  {len(df_day)} candles")
                else: 
                    print(f"   ✗ {current_date.strftime('%Y-%m-%d')}: No data")
                
                # Rate limiting
                time. sleep(0.5)
                
            except Exception as e: 
                print(f"   ⚠️ {current_date.strftime('%Y-%m-%d')}: Error - {e}")
            
            current_date += timedelta(days=1)
        
        if not all_data: 
            print("❌ No data fetched!")
            return pd. DataFrame()
        
        # Combine all days
        df = pd.concat(all_data, ignore_index=True)
        
        # Format columns
        cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) == 7:
            cols. append('oi')
        df.columns = cols[: len(df.columns)]
        
        # Parse datetime
        df['datetime'] = pd. to_datetime(df['datetime'])
        df = df.sort_values('datetime').reset_index(drop=True)
        
        # Convert to numeric
        for col in ['open', 'high', 'low', 'close', 'volume']: 
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        print(f"\n✅ Total candles fetched: {len(df):,}")
        print(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
        
        # Save to file
        if output_file:
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
            df.to_csv(output_file, index=False)
            print(f"✅ Saved to: {output_file}")
        
        return df
    
    def fetch_futures_data(self, expiry_date: str, start_date: str, end_date: str,
                           interval:  str = "1minute",
                           output_file: str = None) -> pd.DataFrame:
        """
        Fetch NIFTY futures historical data
        
        Parameters:
        -----------
        expiry_date : str
            Expiry date in YYYY-MM-DD format
        start_date : str
            Start date in YYYY-MM-DD format
        end_date : str
            End date in YYYY-MM-DD format
        """
        # Format expiry for symbol:  30Dec25
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        expiry_str = dt.strftime("%d%b%y")
        fut_symbol = f"NSE-NIFTY-{expiry_str}-FUT"
        
        print(f"\n📥 Fetching NIFTY Futures Data")
        print(f"   Symbol: {fut_symbol}")
        print(f"   Date Range: {start_date} to {end_date}")
        
        all_data = []
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current_date <= end_dt: 
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            try:
                day_start = current_date.replace(hour=9, minute=15, second=0)
                day_end = current_date.replace(hour=15, minute=30, second=0)
                
                resp = self.groww.get_historical_candles(
                    "NSE",
                    "FNO",
                    fut_symbol,
                    day_start. strftime("%Y-%m-%d %H:%M:%S"),
                    day_end.strftime("%Y-%m-%d %H:%M:%S"),
                    interval
                )
                
                if resp and 'candles' in resp and len(resp['candles']) > 0:
                    df_day = pd.DataFrame(resp['candles'])
                    all_data.append(df_day)
                    print(f"   ✓ {current_date.strftime('%Y-%m-%d')}: {len(df_day)} candles")
                else: 
                    print(f"   ✗ {current_date.strftime('%Y-%m-%d')}: No data")
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"   ⚠️ {current_date.strftime('%Y-%m-%d')}: Error - {e}")
            
            current_date += timedelta(days=1)
        
        if not all_data: 
            return pd.DataFrame()
        
        df = pd.concat(all_data, ignore_index=True)
        cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) == 7:
            cols.append('oi')
        df.columns = cols[:len(df.columns)]
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df. sort_values('datetime').reset_index(drop=True)
        
        for col in ['open', 'high', 'low', 'close', 'volume']: 
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        print(f"\n✅ Total candles fetched:  {len(df):,}")
        
        if output_file:
            df.to_csv(output_file, index=False)
            print(f"✅ Saved to: {output_file}")
        
        return df
    
    def fetch_option_chain_snapshot(self, expiry_date: str) -> dict:
        """
        Fetch current option chain (for reference)
        Historical option chain data may not be available via API
        """
        try:
            chain = self.groww. get_option_chain("NSE", "NIFTY", expiry_date)
            return chain
        except Exception as e: 
            print(f"⚠️ Option chain error: {e}")
            return {}
    
    def fetch_historical_option_data(self, strike:  int, option_type: str,
                                     expiry_date:  str, start_date: str, 
                                     end_date: str, interval: str = "1minute",
                                     output_file: str = None) -> pd.DataFrame:
        """
        Fetch historical data for a specific option contract
        
        Parameters:
        -----------
        strike :  int
            Strike price (e.g., 24000)
        option_type : str
            'CE' or 'PE'
        expiry_date : str
            Expiry in YYYY-MM-DD format
        """
        # Build option symbol:  NIFTY25DEC24000CE
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        year = dt.strftime("%y")
        month = dt.strftime("%b").upper()
        symbol = f"NSE-NIFTY{year}{month}{strike}{option_type}"
        
        print(f"\n📥 Fetching Option Data:  {symbol}")
        
        all_data = []
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current_date <= end_dt: 
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            try:
                day_start = current_date.replace(hour=9, minute=15, second=0)
                day_end = current_date. replace(hour=15, minute=30, second=0)
                
                resp = self.groww. get_historical_candles(
                    "NSE",
                    "FNO",
                    symbol,
                    day_start. strftime("%Y-%m-%d %H:%M:%S"),
                    day_end.strftime("%Y-%m-%d %H:%M:%S"),
                    interval
                )
                
                if resp and 'candles' in resp and len(resp['candles']) > 0:
                    df_day = pd.DataFrame(resp['candles'])
                    df_day['strike'] = strike
                    df_day['option_type'] = option_type
                    all_data. append(df_day)
                    print(f"   ✓ {current_date.strftime('%Y-%m-%d')}: {len(df_day)} candles")
                
                time.sleep(0.3)
                
            except Exception as e: 
                print(f"   ⚠️ {current_date.strftime('%Y-%m-%d')}: {e}")
            
            current_date += timedelta(days=1)
        
        if not all_data:
            return pd.DataFrame()
        
        df = pd.concat(all_data, ignore_index=True)
        
        if output_file:
            df.to_csv(output_file, index=False)
            print(f"✅ Saved to: {output_file}")
        
        return df


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    # Your API credentials (from your code)
    API_KEY    = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ5NTMwMzAsImlhdCI6MTc2NjU1MzAzMCwibmJmIjoxNzY2NTUzMDMwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCI3NTc2NzhiMS1mYjQxLTRkZjgtODc5Zi0yMDc3NTI2MTI5YzFcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjEwYzcxYzg2LWM2NzYtNDRhMS05N2VmLTc0N2EzYzdmMTM3Y1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmFkNDU6YzJiZDo2ZmZhOjJjNDksMTcyLjcwLjIxOC41MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDk1MzAzMDAwNX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.qfClpvX56UsEn5qeLufKny_uF8ztmx0TA8WL2_FD_pLcv1l7kMkgec8lw997gwqHLXPu6YJPzdn4ECjXUwhYqQ"
    API_SECRET = "84ENDHT5g1DQE86e2k8(Of*s4ukp!Ari"  # Replace with your secret
    
    # Initialize fetcher
    fetcher = GrowwHistoricalFetcher(API_KEY, API_SECRET)
    
    # Fetch 1 month of NIFTY spot data
    spot_df = fetcher.fetch_spot_data(
        start_date="2025-11-26",
        end_date="2025-12-26",
        interval="1minute",
        output_file="D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\data\\nifty_spot_1min.csv"
    )
    
    print(f"\nSample data:")
    print(spot_df.head(10))