"""
Historical Data Fetcher for Backtesting
Uses Groww API to fetch historical option chain data
"""

from growwapi import GrowwAPI
import pandas as pd
from datetime import datetime, timedelta
import time

class HistoricalDataFetcher:
    def __init__(self, api_token):
        """
        Initialize with Groww API credentials
        """
        self.groww = GrowwAPI(api_token)
        
    def fetch_historical_candles(self, trading_symbol, exchange, segment, 
                                  start_date, end_date, interval='5minute'):
        """
        Fetch historical candle data for backtesting
        
        Parameters: 
        -----------
        trading_symbol : str
            Symbol like 'NIFTY'
        exchange : str
            Exchange (NSE/BSE)
        segment : str
            CASH/FNO
        start_date : str
            Start date 'YYYY-MM-DD'
        end_date : str
            End date 'YYYY-MM-DD'
        interval : str
            Candle interval (5minute recommended for scalping)
        """
        try:
            # Convert dates to epoch
            start_time = datetime.strptime(start_date, '%Y-%M-%d').timestamp() * 1000
            end_time = datetime.strptime(end_date, '%Y-%M-%d').timestamp() * 1000
            
            response = self.groww.get_historical_candles(
                exchange=exchange,
                segment=segment,
                groww_symbol=f"{exchange}-{trading_symbol}",
                start_time=int(start_time),
                end_time=int(end_time),
                candle_interval=interval
            )
            
            # Convert to DataFrame
            candles = response.get('candles', [])
            df = pd.DataFrame(candles, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'OI'])
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            
            return df
            
        except Exception as e:
            print(f"Error fetching candles: {e}")
            return None
    
    def fetch_option_chain_historical(self, underlying, expiry_date, start_date, end_date):
        """
        Fetch historical option chain data
        
        This requires multiple API calls and rate limiting
        """
        all_data = []
        
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current_date <= end:
            try:
                # Fetch option chain for the day
                option_chain = self.groww. get_option_chain(
                    exchange=self.groww. EXCHANGE_NSE,
                    underlying=underlying,
                    expiry_date=expiry_date
                )
                
                # Process and store data
                # Add timestamp
                # Add to all_data list
                
                # Rate limiting (max 10 requests per second)
                time.sleep(0.15)
                
                current_date += timedelta(days=1)
                
            except Exception as e:
                print(f"Error on {current_date}: {e}")
                time.sleep(1)
                continue
        
        return pd.DataFrame(all_data)
    
    def prepare_backtest_data(self, spot_data, option_chain_data):
        """
        Merge spot data with option chain data for backtesting
        """
        # Merge dataframes on timestamp
        # Calculate RSI, PCR, etc.
        # Return formatted dataframe
        pass


# Example usage: 
# fetcher = HistoricalDataFetcher("YOUR_API_TOKEN")
# data = fetcher.fetch_historical_candles("NIFTY", "NSE", "CASH", "2024-01-01", "2024-12-31")