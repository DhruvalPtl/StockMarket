"""
EXPERIMENT 6 - CONFIGURATION
Enhanced configuration with Market Intelligence parameters.
All settings centralized here.
"""

import os
import sys
from datetime import datetime
from typing import List, Dict


class BotConfig:
    """
    Central Configuration for Experiment 6 - Intelligent Trading Bot.
    """

    # ============================================================
    # 1.API CREDENTIALS & CONNECTION
    # ============================================================
    API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTYyNTI4NzUsImlhdCI6MTc2Nzg1Mjg3NSwibmJmIjoxNzY3ODUyODc1LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCI2N2U2MGI0Yy0wZjRjLTQ3YTItYWYzZi02ZTJhMzRkN2RiZWNcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiYWM2YTBhMDUtMjg5MS01ZjgyLWI5ZjgtOTEyODViOGZlZmZiXCIsXCJzZXNzaW9uSWRcIjpcImViMjEzMGVkLWE4YzktNDQ3My05M2M5LTllNjViZGFiZWJkMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwYzE6MWU6ZjZmOmU4MWU6NzEzZTplNTQwOmIxZjYsMTcyLjcwLjE5Mi4xODEsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTYyNTI4NzU5NjF9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.Hfu_-59FrzFLxVlkWzZDvRCOeuESpYNMkfCTneqdFMFsXLWIXBx9NIPkBTLeesRys8VpgSl7NOxGa4J2JIR4iw"
    API_SECRET = "JLs8dG45z-E8N@W$3)9iH!U0w&z@uoW)"
    
    # Rate Limiting (Seconds between calls)
    RATE_LIMIT_SPOT = 0.5
    RATE_LIMIT_FUTURE = 0.5
    RATE_LIMIT_CHAIN = 1.0

    # ============================================================
    # 2.CONTRACT DETAILS
    # ============================================================
    OPTION_EXPIRY = "2026-01-13"      # Weekly options expiry
    FUTURE_EXPIRY = "2026-01-27"      # Monthly futures expiry
    
    # ============================================================
    # 3.TIMEFRAMES & STRATEGIES
    # ============================================================
    TIMEFRAMES = ["1minute", "2minute", "3minute", "5minute"]
    
    # All available strategies
    ALL_STRATEGIES = [
        "ORIGINAL",
        "VWAP_EMA_TREND",
        "VWAP_BOUNCE", 
        "MOMENTUM_BREAKOUT",
        "EMA_CROSSOVER",
        "LIQUIDITY_SWEEP",
        "VOLATILITY_SPIKE",
        "ORDER_FLOW",
        "OPENING_RANGE_BREAKOUT"
    ]
    
    # Strategies to activate (can be subset of ALL_STRATEGIES)
    STRATEGIES_TO_RUN = ALL_STRATEGIES
    
    # ============================================================
    # 4.MARKET REGIME SETTINGS (NEW)
    # ============================================================
    class Regime:
        # ADX thresholds for trend detection
        ADX_TRENDING_THRESHOLD = 20      # Above = trending
        ADX_STRONG_TREND_THRESHOLD = 35  # Above = strong trend
        ADX_RANGING_THRESHOLD = 20       # Below = ranging
        
        # ATR thresholds for volatility
        ATR_PERIOD = 14
        ATR_VOLATILE_MULTIPLIER = 1.3    # ATR > 1.5x avg = volatile
        ATR_LOW_VOL_MULTIPLIER = 0.8     # ATR < 0.7x avg = low vol
        
        # Regime confirmation candles
        REGIME_CONFIRMATION_CANDLES = 3
        
    # ============================================================
    # 5.BIAS DETECTION SETTINGS (NEW)
    # ============================================================
    class Bias: 
        # Futures Premium
        PREMIUM_STRONG_BULLISH = 175      # Points above spot
        PREMIUM_BULLISH = 155
        PREMIUM_NEUTRAL_LOW = 120
        PREMIUM_BEARISH = 80            # Discount
        
        # EMA Alignment
        EMA_PERIODS = [5, 13, 21, 50]    # Multi-EMA check
        
        # PCR Thresholds
        PCR_BULLISH = 1.15                # High put writing = bullish
        PCR_BEARISH = 0.85                # High call writing = bearish
        
    # ============================================================
    # 6.ORDER FLOW SETTINGS (NEW)
    # ============================================================
    class OrderFlow: 
        # OI Change thresholds
        OI_SIGNIFICANT_CHANGE_PCT = 0.5    # 5% change = significant
        OI_BUILDUP_THRESHOLD = 2        # 10% increase = buildup
        
        # Volume thresholds
        VOLUME_SPIKE_MULTIPLIER = 2.0    # 2x avg = spike
        VOLUME_DRY_MULTIPLIER = 0.5      # 0.5x avg = dry
        
        # Tracking periods
        OI_LOOKBACK_PERIODS = 5          # Compare with 5 periods ago
        
    # ============================================================
    # 7.LIQUIDITY MAPPING SETTINGS (NEW)
    # ============================================================
    class Liquidity:
        # Key level detection
        SWING_LOOKBACK = 10              # Candles to find swing H/L
        ROUND_NUMBER_INTERVAL = 100      # 24000, 24100, 24200...
        
        # Max Pain calculation
        MAX_PAIN_STRIKE_RANGE = 500      # ±500 points from ATM
        
        # Support/Resistance strength
        LEVEL_TOUCH_THRESHOLD = 3        # 3 touches = strong level
        
    # ============================================================
    # 8.SIGNAL CONFLUENCE SETTINGS (NEW)
    # ============================================================
    class Confluence:
        # Minimum score to take trade
        MIN_SCORE_HIGH_CONFIDENCE = 4
        MIN_SCORE_MEDIUM_CONFIDENCE = 3
        MIN_SCORE_LOW_CONFIDENCE = 2     # Maybe skip or reduce size
        
        # Weights for different confirmations
        WEIGHTS = {
            'strategy_signal': 1,
            'regime_alignment': 2,
            'bias_alignment': 1,
            'order_flow_confirmation': 2,
            'volume_confirmation': 1,
            'key_level_proximity': 1,
            'time_window_optimal': 1
        }
        
    # ============================================================
    # 9.RISK MANAGEMENT (ENHANCED)
    # ============================================================
    class Risk:
        # Capital
        CAPITAL_PER_STRATEGY = 10000.0
        MAX_CAPITAL_USAGE_PCT = 0.90
        LOT_SIZE = 75                    # Updated Nifty lot size
        
        # Position Limits (NEW)
        MAX_CONCURRENT_POSITIONS = 100     # Across ALL strategies
        MAX_SAME_DIRECTION = 100           # Max 3 CE or 3 PE at same time
        MAX_SAME_STRIKE = 100              # Only 1 position per strike
        
        # Daily Limits
        MAX_DAILY_TRADES = 1000            # Circuit breaker
        MAX_DAILY_LOSS = 5000            # Stop trading if hit (optional)
        MAX_DAILY_LOSS_ACTION = "LOG"    # "HALT" or "LOG"
        
        # Costs
        BROKERAGE_PER_ORDER = 20.0
        TAXES_PER_TRADE = 15.0
        SLIPPAGE_POINTS = 1
        
    # ============================================================
    # 10.EXIT RULES (ENHANCED)
    # ============================================================
    class Exit:
        # Default Fixed Exits
        DEFAULT_TARGET_POINTS = 12
        DEFAULT_STOP_LOSS_POINTS = 6
        
        # Regime-Adaptive Exits (NEW)
        EXITS_BY_REGIME = {
            'TRENDING': {'target': 15, 'stop':  5},
            'RANGING': {'target': 8, 'stop':  8},
            'VOLATILE': {'target': 20, 'stop':  10}
        }
        
        # Trailing Stop
        TRAILING_ACTIVATION_PCT = 0.4    # Activate at 40% of target
        TRAILING_DISTANCE_PCT = 0.04     # Trail 4% below peak
        
        # Time-based
        MAX_HOLD_TIME_MINUTES = 30
        
        # Cooldown
        COOLDOWN_SECONDS = 60
        
    # ============================================================
    # 11.TIME WINDOWS (NEW)
    # ============================================================
    class TimeWindows:
        # Market Hours
        MARKET_OPEN = (9, 15)            # 9:15 AM
        MARKET_CLOSE = (15, 30)          # 3:30 PM
        
        # Trading Windows
        OPENING_SESSION = (9, 15, 9, 45)    # start_h, start_m, end_h, end_m
        MORNING_SESSION = (9, 45, 11, 0)
        LUNCH_SESSION = (11, 0, 14, 0)
        POWER_HOUR = (14, 0, 15, 20)
        
        # Restrictions
        NO_NEW_ENTRY = (15, 20)          # 3:20 PM
        FORCE_EXIT = (15, 25)            # 3:25 PM
        
        # Strategy-Time Mapping (NEW)
        STRATEGY_TIME_RULES = {
            'OPENING_RANGE_BREAKOUT': ['OPENING_SESSION'],
            'VOLATILITY_SPIKE':  ['OPENING_SESSION', 'POWER_HOUR'],
            'VWAP_BOUNCE': ['MORNING_SESSION', 'LUNCH_SESSION'],
            'MOMENTUM_BREAKOUT': ['MORNING_SESSION', 'POWER_HOUR'],
            'EMA_CROSSOVER': ['MORNING_SESSION', 'POWER_HOUR'],
            'LIQUIDITY_SWEEP': ['MORNING_SESSION', 'POWER_HOUR'],
            'ORDER_FLOW': ['MORNING_SESSION', 'LUNCH_SESSION', 'POWER_HOUR'],
            'VWAP_EMA_TREND':  ['MORNING_SESSION', 'POWER_HOUR'],
            'ORIGINAL':  ['OPENING_SESSION', 'MORNING_SESSION', 'POWER_HOUR']
        }
        
    # ============================================================
    # 12.STRATEGY-REGIME MAPPING (NEW)
    # ============================================================
    STRATEGY_REGIME_RULES = {
        'TRENDING': [
            'EMA_CROSSOVER',
            'MOMENTUM_BREAKOUT', 
            'ORDER_FLOW',
            'VWAP_EMA_TREND',
            'ORIGINAL'
        ],
        'RANGING':  [
            'VWAP_BOUNCE',
            'LIQUIDITY_SWEEP',
            'ORIGINAL'
        ],
        'VOLATILE':  [
            'VOLATILITY_SPIKE',
            'OPENING_RANGE_BREAKOUT',
            'LIQUIDITY_SWEEP'
        ]
    }
    
    # ============================================================
    # 13.RSI SETTINGS
    # ============================================================
    class RSI:
        PERIOD = 14
        OVERSOLD = 35
        OVERBOUGHT = 65
        MOMENTUM_BULL_LOW = 55
        MOMENTUM_BULL_HIGH = 75
        MOMENTUM_BEAR_LOW = 25
        MOMENTUM_BEAR_HIGH = 45
        
    # ============================================================
    # 14.PATTERN SETTINGS
    # ============================================================
    class Patterns:
        MIN_CANDLE_BODY = 8             # Points
        ENGULFING_RATIO = 1.2            # Body 1.5x previous
        DOJI_BODY_PCT = 0.1              # Body < 10% of range
        
    # ============================================================
    # 15.LOGGING & SYSTEM
    # ============================================================
    DEBUG_MODE = False
    VERBOSE_LOGGING = True
    
    BASE_LOG_PATH = r"D:\\StockMarket\\StockMarket\\scripts\\claude\\expriment6\\log"
    
    @classmethod
    def get_log_paths(cls) -> Dict[str, str]: 
        """Returns validated log paths."""
        paths = {
            'engine_log': os.path.join(cls.BASE_LOG_PATH, "engine_logs"),
            'bot_log': os.path.join(cls.BASE_LOG_PATH, "bot_logs"),
            'trade_book':  os.path.join(cls.BASE_LOG_PATH, "trade_books"),
            'summary':  os.path.join(cls.BASE_LOG_PATH, "summaries"),
            'market_context': os.path.join(cls.BASE_LOG_PATH, "market_context"),
            'signals': os.path.join(cls.BASE_LOG_PATH, "signals")
        }
        
        for key, path in paths.items():
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                print(f"❌ CRITICAL: Could not create {path}:  {e}")
                sys.exit(1)
                
        return paths

    @classmethod
    def validate(cls) -> bool:
        """Validates configuration."""
        errors = []
        
        # Credentials
        if not cls.API_KEY or len(cls.API_KEY) < 10:
            errors.append("API_KEY is missing or invalid.")
        if not cls.API_SECRET:
            errors.append("API_SECRET is missing.")

        # Dates
        try:
            datetime.strptime(cls.OPTION_EXPIRY, "%Y-%m-%d")
            datetime.strptime(cls.FUTURE_EXPIRY, "%Y-%m-%d")
        except ValueError as e:
            errors.append(f"Date format error: {e}")

        # Logic
        if cls.Exit.DEFAULT_TARGET_POINTS <= cls.Exit.DEFAULT_STOP_LOSS_POINTS:
            errors.append("TARGET must be > STOP_LOSS")
            
        # Strategies
        for strat in cls.STRATEGIES_TO_RUN:
            if strat not in cls.ALL_STRATEGIES:
                errors.append(f"Unknown strategy: {strat}")

        if errors:
            print("\n❌ CONFIG VALIDATION FAILED:")
            for e in errors:
                print(f"  - {e}")
            raise ValueError("Configuration invalid")
            
        print("✅ Configuration validated.")
        return True

    @classmethod
    def print_config(cls):
        """Prints active configuration."""
        print("\n" + "="*60)
        print("⚙️  EXPERIMENT 6 CONFIGURATION")
        print("="*60)
        print(f"Timeframes:      {cls.TIMEFRAMES}")
        print(f"Strategies:     {len(cls.STRATEGIES_TO_RUN)} active")
        print(f"Capital/Strat:  ₹{cls.Risk.CAPITAL_PER_STRATEGY: ,.0f}")
        print(f"Max Positions:  {cls.Risk.MAX_CONCURRENT_POSITIONS}")
        print(f"Option Expiry:  {cls.OPTION_EXPIRY}")
        print("="*60 + "\n")


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_timeframe_display_name(timeframe:  str) -> str:
    """Converts timeframe to display name."""
    mapping = {
        "1minute": "1min",
        "2minute": "2min", 
        "3minute": "3min",
        "5minute": "5min",
        "15minute": "15min"
    }
    return mapping.get(timeframe, timeframe)


def get_future_symbol(expiry_date: str) -> str:
    """Generates NSE Future symbol."""
    try:
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        date_str = dt.strftime("%d%b%y")
        return f"NSE-NIFTY-{date_str}-FUT"
    except Exception as e:
        print(f"❌ Error generating future symbol: {e}")
        return "ERROR_SYMBOL"


def get_option_symbol(strike:  int, option_type: str, expiry_date: str) -> str:
    """Generates NSE Option symbol."""
    try:
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        date_str = dt.strftime("%d%b%y")
        return f"NSE-NIFTY-{date_str}-{strike}-{option_type}"
    except Exception as e:
        print(f"❌ Error generating option symbol: {e}")
        return "ERROR_SYMBOL"