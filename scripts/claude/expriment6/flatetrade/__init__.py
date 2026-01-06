"""
Experiment 6 - Intelligent Multi-Strategy Trading System
With Flate Trade API Integration

This package provides a unified API that works with both Groww and Flate Trade,
allowing seamless switching between providers with zero code changes.

Key Components:
- unified_api: UnifiedAPI class supporting both Groww and Flate Trade
- flate_api_adapter: FlateTradeAdapter for Groww-compatible interface
- data_pipeline: UnifiedDataEngine for real-time data collection
- option_fetcher: UnifiedOptionFetcher for historical option data
- test_comparison: Test and compare both APIs side-by-side

Quick Start:
    from flatetrade import UnifiedAPI
    
    # Use Groww
    api = UnifiedAPI(provider="groww", api_key=key, api_secret=secret)
    
    # OR use Flate Trade (same code!)
    api = UnifiedAPI(provider="flate", user_id=uid, user_token=token)
    
    # All existing code works unchanged
    candles = api.get_historical_candles("NSE", "CASH", "NSE-NIFTY", start, end, "1minute")
"""

__version__ = "6.0.0"
__author__ = "Trading Bot"

# Import main classes for easy access
try:
    from .unified_api import UnifiedAPI, create_api
    from .flate_api_adapter import FlateTradeAdapter
    from .data_pipeline import UnifiedDataEngine
    from .option_fetcher import UnifiedOptionFetcher, GrowwOptionFetcher
    from .config import BotConfig, UnifiedConfig
    
    __all__ = [
        'UnifiedAPI',
        'create_api',
        'FlateTradeAdapter',
        'UnifiedDataEngine',
        'UnifiedOptionFetcher',
        'GrowwOptionFetcher',
        'BotConfig',
        'UnifiedConfig'
    ]
except ImportError:
    # Gracefully handle missing dependencies
    __all__ = []