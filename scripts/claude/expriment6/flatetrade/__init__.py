"""
Experiment 6 - Intelligent Multi-Strategy Trading System
With Flattrade API Integration

This package provides an API integration with Flattrade for trading.

Key Components:
- unified_api: UnifiedAPI class for Flattrade
- flate_api_adapter: FlateTradeAdapter for API interface
- data_pipeline: UnifiedDataEngine for real-time data collection
- option_fetcher: UnifiedOptionFetcher for historical option data

Quick Start:
    from flatetrade import UnifiedAPI
    
    # Initialize Flattrade
    api = UnifiedAPI(user_id="FZ31397", user_token="your_token")
    
    # Fetch data
    candles = api.get_historical_candles("NSE", "CASH", "NSE-NIFTY", start, end, "1minute")
"""

__version__ = "6.0.0"
__author__ = "Trading Bot"

# Import main classes for easy access
try:
    from .unified_api import UnifiedAPI, create_api
    from .flate_api_adapter import FlateTradeAdapter
    from .data_pipeline import UnifiedDataEngine
    from .option_fetcher import UnifiedOptionFetcher
    from .config import BotConfig
    
    __all__ = [
        'UnifiedAPI',
        'create_api',
        'FlateTradeAdapter',
        'UnifiedDataEngine',
        'UnifiedOptionFetcher',
        'BotConfig'
    ]
except ImportError:
    # Gracefully handle missing dependencies
    __all__ = []