"""
FLATE TRADE API ADAPTER
========================
Adapter that makes Flate Trade API compatible with Groww API interface.
This allows existing Groww-based code to work with Flate Trade without changes.

Key Features:
- Same method signatures as Groww API
- Same data structures returned
- Automatic symbol format conversion
- Error handling and retry logic
- Rate limiting

Author: Claude
Date: 2026-01-06
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import time
import logging

# Import the Flatte Trade API wrapper
try:
    from utils.flattrade_wrapper import FlattradeWrapper
    from utils.NorenRestApiPy.NorenApi import NorenApi
except ImportError:
    # Fallback for different import paths
    try:
        from .utils.flattrade_wrapper import FlattradeWrapper
        from .utils.NorenRestApiPy.NorenApi import NorenApi
    except ImportError:
        print("⚠️ Warning: Flattrade wrapper not found. Some functionality may be limited.")
        FlattradeWrapper = None
        NorenApi = None


class FlateTradeAdapter:
    """
    Flate Trade API Adapter that mimics Groww API interface.
    
    Usage:
        adapter = FlateTradeAdapter(user_id="YOUR_ID", user_token="YOUR_TOKEN")
        candles = adapter.get_historical_candles("NSE", "CASH", "NSE-NIFTY", start, end, "1minute")
    """
    
    def __init__(self, user_id: str, user_token: str):
        """
        Initialize Flate Trade API Adapter
        
        Args:
            user_id: Flate Trade user ID
            user_token: Flate Trade authentication token
        """
        self.user_id = user_id
        self.user_token = user_token
        self.api = None
        self.is_connected = False
        
        # Rate limiting
        self.last_api_call = {
            'spot': 0,
            'future': 0,
            'chain': 0,
            'ltp': 0,
            'order': 0
        }
        self.min_delay = {
            'spot': 0.5,
            'future': 0.5,
            'chain': 1.0,
            'ltp': 0.3,
            'order': 0.5
        }
        
        # Symbol token cache
        self.token_cache = {}
        
        # Error tracking
        self.errors = {
            'connection': 0,
            'data_fetch': 0,
            'symbol_lookup': 0
        }
        
        # Retry settings
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Connect
        self._connect()
    
    def _connect(self):
        """Connect to Flate Trade API"""
        try:
            if FlattradeWrapper is None:
                raise ImportError("Flattrade wrapper not available")
            
            self.api = FlattradeWrapper(self.user_id, self.user_token)
            
            if self.api.is_connected:
                self.is_connected = True
                self.logger.info("✅ Flate Trade Adapter connected successfully")
            else:
                self.is_connected = False
                self.logger.error("❌ Flate Trade connection failed")
                
        except Exception as e:
            self.errors['connection'] += 1
            self.is_connected = False
            self.logger.error(f"❌ Connection error: {e}")
            raise
    
    def _rate_limit(self, api_type: str):
        """Apply rate limiting to prevent API throttling"""
        now = time.time()
        elapsed = now - self.last_api_call.get(api_type, 0)
        
        min_delay = self.min_delay.get(api_type, 0.5)
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)
        
        self.last_api_call[api_type] = time.time()
    
    def _convert_symbol_groww_to_flate(self, symbol: str, exchange: str) -> Optional[str]:
        """
        Convert Groww symbol format to Flate Trade token/symbol
        
        Args:
            symbol: Groww format symbol (e.g., "NSE-NIFTY", "NSE-NIFTY-06Jan26-24000-CE")
            exchange: Exchange code
            
        Returns:
            Flate Trade token or search string
        """
        # Check cache first
        cache_key = f"{exchange}:{symbol}"
        if cache_key in self.token_cache:
            return self.token_cache[cache_key]
        
        try:
            # Handle NIFTY spot
            if symbol == "NSE-NIFTY" or symbol == "NIFTY":
                token = "26000"
                self.token_cache[cache_key] = token
                return token
            
            # Handle BANKNIFTY spot  
            if symbol == "NSE-BANKNIFTY" or symbol == "BANKNIFTY":
                token = "26009"
                self.token_cache[cache_key] = token
                return token
            
            # Handle futures: "NSE-NIFTY-27Jan26-FUT" -> "NIFTY 27JAN FUT"
            if "-FUT" in symbol:
                parts = symbol.split('-')
                if len(parts) >= 3:
                    underlying = parts[1]  # NIFTY
                    date_part = parts[2].upper()  # 27JAN26
                    # Convert to Flate format: "NIFTY 27JAN FUT"
                    search_str = f"{underlying} {date_part[:5]} FUT"
                    self.token_cache[cache_key] = search_str
                    return search_str
            
            # Handle options: "NSE-NIFTY-06Jan26-24000-CE" -> "NIFTY 06JAN 24000 CE"
            if "-CE" in symbol or "-PE" in symbol:
                parts = symbol.split('-')
                if len(parts) >= 5:
                    underlying = parts[1]  # NIFTY
                    date_part = parts[2].upper()[:5]  # 06JAN
                    strike = parts[3]  # 24000
                    option_type = parts[4]  # CE or PE
                    # Convert to Flate format: "NIFTY 06JAN 24000 CE"
                    search_str = f"{underlying} {date_part} {strike} {option_type}"
                    self.token_cache[cache_key] = search_str
                    return search_str
            
            # If no conversion matched, return as-is
            self.logger.warning(f"⚠️ No conversion rule for symbol: {symbol}")
            return symbol
            
        except Exception as e:
            self.errors['symbol_lookup'] += 1
            self.logger.error(f"❌ Symbol conversion error: {e}")
            return None
    
    def _get_token_from_search(self, symbol: str, exchange: str) -> Optional[str]:
        """
        Get Flate Trade token by searching for symbol
        
        Args:
            symbol: Symbol to search (e.g., "NIFTY 27JAN FUT")
            exchange: Exchange code
            
        Returns:
            Token string or None
        """
        try:
            if not self.api or not self.api.api:
                return None
            
            result = self.api.api.searchscrip(exchange=exchange, searchtext=symbol)
            
            if result and 'values' in result and len(result['values']) > 0:
                token = result['values'][0].get('token')
                self.logger.debug(f"✅ Found token {token} for {symbol}")
                return token
            else:
                self.logger.warning(f"⚠️ No token found for {symbol}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Token search error: {e}")
            return None
    
    def get_historical_candles(self, exchange: str, segment: str, symbol: str,
                              start: str, end: str, interval: str) -> Dict[str, List]:
        """
        Get historical candles data (Groww-compatible interface)
        
        Args:
            exchange: Exchange code (e.g., "NSE")
            segment: Segment code (e.g., "CASH", "FNO")
            symbol: Symbol in Groww format (e.g., "NSE-NIFTY")
            start: Start datetime string "YYYY-MM-DD HH:MM:SS"
            end: End datetime string "YYYY-MM-DD HH:MM:SS"
            interval: Timeframe (e.g., "1minute", "5minute")
            
        Returns:
            Dict with 'candles' key containing list of candle dicts
            Each candle: {'t': datetime, 'o': float, 'h': float, 'l': float, 'c': float, 'v': int}
        """
        self._rate_limit('spot' if segment == 'CASH' else 'future')
        
        for attempt in range(self.max_retries):
            try:
                # Convert symbol format
                flate_symbol = self._convert_symbol_groww_to_flate(symbol, exchange)
                if not flate_symbol:
                    return {'candles': []}
                
                # Get token if needed
                if not flate_symbol.isdigit():
                    token = self._get_token_from_search(flate_symbol, exchange)
                    if not token:
                        return {'candles': []}
                else:
                    token = flate_symbol
                
                # Convert interval format
                interval_map = {
                    '1minute': '1',
                    '2minute': '2',
                    '3minute': '3',
                    '5minute': '5',
                    '15minute': '15',
                    '30minute': '30',
                    '60minute': '60',
                    '1day': '1440'
                }
                flate_interval = interval_map.get(interval, '1')
                
                # Convert time to epoch
                start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
                start_epoch = str(int(start_dt.timestamp()))
                
                # Fetch data using Flate Trade API
                if not self.api or not self.api.api:
                    return {'candles': []}
                
                result = self.api.api.get_time_price_series(
                    exchange=exchange,
                    token=token,
                    starttime=start_epoch,
                    interval=flate_interval
                )
                
                if not result:
                    return {'candles': []}
                
                # Convert to Groww format
                candles = []
                for candle in result:
                    try:
                        # Flate time format: "05-01-2026 09:15:00"
                        time_str = candle.get('time', '')
                        candle_dt = datetime.strptime(time_str, "%d-%m-%Y %H:%M:%S")
                        
                        # Filter by end time
                        end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
                        if candle_dt > end_dt:
                            continue
                        
                        candles.append({
                            't': candle_dt,
                            'o': float(candle.get('into', 0)),
                            'h': float(candle.get('inth', 0)),
                            'l': float(candle.get('intl', 0)),
                            'c': float(candle.get('intc', 0)),
                            'v': int(candle.get('intv', 0)),
                            'oi': int(candle.get('intoi', 0))
                        })
                    except Exception as e:
                        self.logger.debug(f"⚠️ Skipping candle due to error: {e}")
                        continue
                
                # Sort by time
                candles.sort(key=lambda x: x['t'])
                
                return {'candles': candles}
                
            except Exception as e:
                self.errors['data_fetch'] += 1
                self.logger.error(f"❌ Data fetch error (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    return {'candles': []}
        
        return {'candles': []}
    
    def get_option_chain(self, exchange: str, symbol: str, expiry: str) -> Dict[str, Any]:
        """
        Get option chain data (Groww-compatible interface)
        
        Args:
            exchange: Exchange code (e.g., "NSE")
            symbol: Underlying symbol (e.g., "NIFTY")
            expiry: Expiry date "YYYY-MM-DD"
            
        Returns:
            Dict with option chain data including strikes, CE/PE data, OI, Greeks
        """
        self._rate_limit('chain')
        
        try:
            # Note: Flate Trade doesn't have a direct option chain API
            # We need to construct it by fetching individual options
            # This is a simplified implementation
            
            # For now, return empty structure
            # In a production implementation, you would:
            # 1. Determine ATM strike
            # 2. Fetch data for strikes around ATM (±500 points)
            # 3. Get LTP, OI, IV for each strike
            # 4. Calculate Greeks or fetch if available
            
            self.logger.warning("⚠️ Option chain not fully implemented for Flate Trade")
            
            return {
                'expiry': expiry,
                'strikes': [],
                'data': {}
            }
            
        except Exception as e:
            self.logger.error(f"❌ Option chain error: {e}")
            return {'expiry': expiry, 'strikes': [], 'data': {}}
    
    def get_ltp(self, exchange: str, trading_symbol: str, segment: str) -> Dict[str, Any]:
        """
        Get last traded price (Groww-compatible interface)
        
        Args:
            exchange: Exchange code (e.g., "NSE")
            trading_symbol: Symbol in Groww format
            segment: Segment code (e.g., "CASH", "FNO")
            
        Returns:
            Dict with 'ltp' key containing the last price
        """
        self._rate_limit('ltp')
        
        try:
            # Convert symbol
            flate_symbol = self._convert_symbol_groww_to_flate(trading_symbol, exchange)
            if not flate_symbol:
                return {'ltp': 0.0}
            
            # Get token
            if not flate_symbol.isdigit():
                token = self._get_token_from_search(flate_symbol, exchange)
                if not token:
                    return {'ltp': 0.0}
            else:
                token = flate_symbol
            
            # Get quote
            if not self.api or not self.api.api:
                return {'ltp': 0.0}
            
            result = self.api.api.get_quotes(exchange=exchange, token=token)
            
            if result and 'lp' in result:
                return {'ltp': float(result['lp'])}
            else:
                return {'ltp': 0.0}
                
        except Exception as e:
            self.logger.error(f"❌ LTP fetch error: {e}")
            return {'ltp': 0.0}
    
    def place_order(self, **kwargs) -> Dict[str, Any]:
        """
        Place order (Groww-compatible interface)
        
        Note: This is a placeholder. Actual order placement requires
        additional parameters and proper risk management.
        
        Returns:
            Dict with order response
        """
        self._rate_limit('order')
        
        try:
            self.logger.warning("⚠️ Order placement not implemented in adapter")
            return {'status': 'error', 'message': 'Not implemented'}
            
        except Exception as e:
            self.logger.error(f"❌ Order placement error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_expiries(self, exchange: str, underlying_symbol: str, 
                    year: int, month: int) -> Dict[str, List]:
        """
        Get available expiry dates
        
        Args:
            exchange: Exchange code
            underlying_symbol: Underlying symbol (e.g., "NIFTY")
            year: Year
            month: Month
            
        Returns:
            Dict with 'expiries' list
        """
        try:
            # Flate Trade doesn't have a direct expiries API
            # Calculate weekly expiries for the month
            expiries = []
            
            # Find all Thursdays in the month (weekly expiry day)
            from calendar import monthrange
            _, last_day = monthrange(year, month)
            
            for day in range(1, last_day + 1):
                date = datetime(year, month, day)
                if date.weekday() == 3:  # Thursday
                    expiries.append(date.strftime("%Y-%m-%d"))
            
            return {'expiries': expiries}
            
        except Exception as e:
            self.logger.error(f"❌ Expiries fetch error: {e}")
            return {'expiries': []}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics"""
        return {
            'is_connected': self.is_connected,
            'errors': self.errors.copy(),
            'cache_size': len(self.token_cache)
        }
