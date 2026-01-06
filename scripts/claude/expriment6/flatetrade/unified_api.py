"""
UNIFIED API - FLATTRADE WRAPPER
================================
Provides a consistent interface for Flattrade API.
This maintains backward compatibility with existing code that uses UnifiedAPI.

Usage:
    from unified_api import UnifiedAPI
    api = UnifiedAPI(user_id="FZ31397", user_token="your_token")
    
    # All existing code works unchanged!
    data = api.get_historical_candles(...)

Author: Claude
Date: 2026-01-06
"""

import logging
from typing import Dict, Optional, List, Any

# Import Flattrade API
try:
    from flate_api_adapter import FlateTradeAdapter
    FLATE_AVAILABLE = True
except ImportError:
    try:
        from .flate_api_adapter import FlateTradeAdapter
        FLATE_AVAILABLE = True
    except ImportError:
        FLATE_AVAILABLE = False
        print("⚠️ Warning: Flattrade API not available")


class UnifiedAPI:
    """
    Unified API that works with Flattrade.
    
    This class provides a single interface for Flattrade API.
    Existing code can use this without changes.
    
    Example:
        api = UnifiedAPI(user_id=uid, user_token=token)
        candles = api.get_historical_candles("NSE", "CASH", "NSE-NIFTY", start, end, "1minute")
    """
    
    # Class constants for exchange/segment codes
    EXCHANGE_NSE = "NSE"
    EXCHANGE_BSE = "BSE"
    SEGMENT_CASH = "CASH"
    SEGMENT_FNO = "FNO"
    SEGMENT_INDEX = "INDEX"
    
    # Interval constants
    INTERVAL_1MIN = "1minute"
    INTERVAL_2MIN = "2minute"
    INTERVAL_3MIN = "3minute"
    INTERVAL_5MIN = "5minute"
    INTERVAL_15MIN = "15minute"
    INTERVAL_30MIN = "30minute"
    INTERVAL_60MIN = "60minute"
    INTERVAL_1DAY = "1day"
    
    def __init__(self, user_id: str = None, user_token: str = None, **kwargs):
        """
        Initialize Unified API with Flattrade
        
        Args:
            user_id: Flattrade user ID
            user_token: Flattrade authentication token
        """
        self.api = None
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize Flattrade API
        self._init_flate(user_id=user_id, user_token=user_token, **kwargs)
        
        self.logger.info(f"✅ Unified API initialized with Flattrade")
    
    def _init_flate(self, **kwargs):
        """Initialize Flattrade API"""
        if not FLATE_AVAILABLE:
            raise ImportError("Flattrade API not available")
        
        try:
            if 'user_id' not in kwargs or 'user_token' not in kwargs:
                raise ValueError("Provide 'user_id' and 'user_token' for Flate Trade")
            
            self.api = FlateTradeAdapter(
                user_id=kwargs['user_id'],
                user_token=kwargs['user_token']
            )
            
            self.logger.info("✅ Flate Trade API connected")
            
        except Exception as e:
            self.logger.error(f"❌ Flate Trade API initialization failed: {e}")
            raise
    
    def get_historical_candles(self, exchange: str, segment: str, symbol: str,
                              start: str, end: str, interval: str) -> Dict[str, List]:
        """
        Get historical candles data
        
        Args:
            exchange: Exchange code (e.g., "NSE")
            segment: Segment code (e.g., "CASH", "FNO")
            symbol: Symbol in Groww format (e.g., "NSE-NIFTY")
            start: Start datetime string "YYYY-MM-DD HH:MM:SS"
            end: End datetime string "YYYY-MM-DD HH:MM:SS"
            interval: Timeframe (e.g., "1minute", "5minute")
            
        Returns:
            Dict with 'candles' key containing list of candle dicts
        """
        try:
            return self.api.get_historical_candles(exchange, segment, symbol, start, end, interval)
        except Exception as e:
            self.logger.error(f"❌ get_historical_candles error: {e}")
            return {'candles': []}
    
    def get_option_chain(self, exchange: str, symbol: str, expiry: str) -> Dict[str, Any]:
        """
        Get option chain data
        
        Args:
            exchange: Exchange code (e.g., "NSE")
            symbol: Underlying symbol (e.g., "NIFTY")
            expiry: Expiry date "YYYY-MM-DD"
            
        Returns:
            Dict with option chain data
        """
        try:
            if self.provider == "groww":
                # Groww has get_option_chain method
                return self.api.get_option_chain(exchange, symbol, expiry)
            else:
                # Flate Trade adapter has the method
                return self.api.get_option_chain(exchange, symbol, expiry)
        except Exception as e:
            self.logger.error(f"❌ get_option_chain error: {e}")
            return {'expiry': expiry, 'strikes': [], 'data': {}}
    
    def get_ltp(self, exchange: str, trading_symbol: str, segment: str) -> Dict[str, Any]:
        """
        Get last traded price
        
        Args:
            exchange: Exchange code (e.g., "NSE")
            trading_symbol: Symbol in Groww format
            segment: Segment code (e.g., "CASH", "FNO")
            
        Returns:
            Dict with 'ltp' key containing the last price
        """
        try:
            return self.api.get_ltp(exchange, trading_symbol, segment)
        except Exception as e:
            self.logger.error(f"❌ get_ltp error: {e}")
            return {'ltp': 0.0}
    
    def place_order(self, **kwargs) -> Dict[str, Any]:
        """
        Place order
        
        Note: Order parameters may differ between providers.
        This is a passthrough to the underlying API.
        
        Returns:
            Dict with order response
        """
        try:
            return self.api.place_order(**kwargs)
        except Exception as e:
            self.logger.error(f"❌ place_order error: {e}")
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
            return self.api.get_expiries(exchange, underlying_symbol, year, month)
        except Exception as e:
            self.logger.error(f"❌ get_expiries error: {e}")
            return {'expiries': []}
    
    def get_positions(self) -> List[Dict]:
        """
        Get current positions
        
        Returns:
            List of position dicts
        """
        try:
            if hasattr(self.api, 'get_positions'):
                return self.api.get_positions()
            else:
                self.logger.warning("⚠️ get_positions not implemented for this provider")
                return []
        except Exception as e:
            self.logger.error(f"❌ get_positions error: {e}")
            return []
    
    def get_holdings(self) -> List[Dict]:
        """
        Get current holdings
        
        Returns:
            List of holding dicts
        """
        try:
            if hasattr(self.api, 'get_holdings'):
                return self.api.get_holdings()
            else:
                self.logger.warning("⚠️ get_holdings not implemented for this provider")
                return []
        except Exception as e:
            self.logger.error(f"❌ get_holdings error: {e}")
            return []
    
    def get_provider(self) -> str:
        """Get the current provider name"""
        return self.provider
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get API statistics
        
        Returns:
            Dict with stats (provider-specific)
        """
        stats = {
            'provider': self.provider,
            'connected': self.api is not None
        }
        
        if hasattr(self.api, 'get_stats'):
            stats.update(self.api.get_stats())
        
        return stats
    
    # Compatibility methods - make it work like GrowwAPI class methods
    @staticmethod
    def get_access_token(api_key: str, secret: str) -> str:
        """
        Get Groww access token (for Groww provider only)
        
        Args:
            api_key: Groww API key
            secret: Groww API secret
            
        Returns:
            Access token string
        """
        if not GROWW_AVAILABLE:
            raise ImportError("Groww API not available")
        
        return GrowwAPI.get_access_token(api_key=api_key, secret=secret)


# Convenience function for easy migration
def create_api(provider: str = "groww", **kwargs) -> UnifiedAPI:
    """
    Convenience function to create UnifiedAPI instance
    
    Args:
        provider: "groww" or "flate"
        **kwargs: Provider-specific credentials
        
    Returns:
        UnifiedAPI instance
        
    Example:
        # Groww
        api = create_api("groww", api_key=key, api_secret=secret)
        
        # Flate Trade
        api = create_api("flate", user_id=uid, user_token=token)
    """
    return UnifiedAPI(provider=provider, **kwargs)
