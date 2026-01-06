"""
UNIFIED API - DROP-IN REPLACEMENT FOR GROWW API
================================================
Supports both Groww and Flate Trade APIs with identical interface.
Switch providers with a single parameter change.

Key Features:
- Same interface as Groww API
- Automatic provider routing
- Zero code changes needed in existing bots
- Transparent switching between Groww and Flate Trade

Usage:
    # Instead of:
    from growwapi import GrowwAPI
    api = GrowwAPI(token)
    
    # Use:
    from unified_api import UnifiedAPI
    api = UnifiedAPI(provider="groww")  # or provider="flate"
    
    # All existing code works unchanged!
    data = api.get_historical_candles(...)

Author: Claude
Date: 2026-01-06
"""

import logging
from typing import Dict, Optional, List, Any

# Import both APIs
try:
    from growwapi import GrowwAPI
    GROWW_AVAILABLE = True
except ImportError:
    GROWW_AVAILABLE = False
    print("⚠️ Warning: Groww API not available")

try:
    from flate_api_adapter import FlateTradeAdapter
    FLATE_AVAILABLE = True
except ImportError:
    try:
        from .flate_api_adapter import FlateTradeAdapter
        FLATE_AVAILABLE = True
    except ImportError:
        FLATE_AVAILABLE = False
        print("⚠️ Warning: Flate Trade API not available")


class UnifiedAPI:
    """
    Unified API that works with both Groww and Flate Trade.
    
    This class provides a single interface that routes calls to the appropriate
    API provider based on configuration. Existing code using Groww API can
    switch to Flate Trade by changing just one parameter.
    
    Example:
        # Groww
        api = UnifiedAPI(provider="groww", api_key=key, api_secret=secret)
        
        # Flate Trade
        api = UnifiedAPI(provider="flate", user_id=uid, user_token=token)
        
        # Both work identically
        candles = api.get_historical_candles("NSE", "CASH", "NSE-NIFTY", start, end, "1minute")
    """
    
    # Class constants for exchange/segment codes (Groww format)
    EXCHANGE_NSE = "NSE"
    EXCHANGE_BSE = "BSE"
    SEGMENT_CASH = "CASH"
    SEGMENT_FNO = "FNO"
    SEGMENT_INDEX = "INDEX"
    
    # Interval constants (Groww format)
    INTERVAL_1MIN = "1minute"
    INTERVAL_2MIN = "2minute"
    INTERVAL_3MIN = "3minute"
    INTERVAL_5MIN = "5minute"
    INTERVAL_15MIN = "15minute"
    INTERVAL_30MIN = "30minute"
    INTERVAL_60MIN = "60minute"
    INTERVAL_1DAY = "1day"
    
    def __init__(self, provider: str = "groww", **kwargs):
        """
        Initialize Unified API
        
        Args:
            provider: "groww" or "flate"
            
            For Groww:
                api_key: Groww API key
                api_secret: Groww API secret
                OR
                token: Pre-generated Groww token
                
            For Flate Trade:
                user_id: Flate Trade user ID
                user_token: Flate Trade authentication token
        """
        self.provider = provider.lower()
        self.api = None
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize the appropriate API
        if self.provider == "groww":
            self._init_groww(**kwargs)
        elif self.provider == "flate":
            self._init_flate(**kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'groww' or 'flate'")
        
        self.logger.info(f"✅ Unified API initialized with provider: {self.provider}")
    
    def _init_groww(self, **kwargs):
        """Initialize Groww API"""
        if not GROWW_AVAILABLE:
            raise ImportError("Groww API not available. Install with: pip install growwapi")
        
        try:
            # Check if token is provided directly
            if 'token' in kwargs:
                self.api = GrowwAPI(kwargs['token'])
            # Or if API key/secret provided
            elif 'api_key' in kwargs and 'api_secret' in kwargs:
                token = GrowwAPI.get_access_token(
                    api_key=kwargs['api_key'],
                    secret=kwargs['api_secret']
                )
                self.api = GrowwAPI(token)
            else:
                raise ValueError("Provide either 'token' or 'api_key' and 'api_secret'")
            
            self.logger.info("✅ Groww API connected")
            
        except Exception as e:
            self.logger.error(f"❌ Groww API initialization failed: {e}")
            raise
    
    def _init_flate(self, **kwargs):
        """Initialize Flate Trade API"""
        if not FLATE_AVAILABLE:
            raise ImportError("Flate Trade API not available")
        
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
