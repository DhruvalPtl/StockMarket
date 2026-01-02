"""
CONFIGURATION FILE - All settings in one place
Easy to modify without touching core logic
"""

from datetime import datetime


class BotConfig:
    """Main bot configuration"""
    
    # ============================================================
    # API CREDENTIALS
    # ============================================================
    API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
    API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
    
    # ============================================================
    # EXPIRY DATES
    # ============================================================
    OPTION_EXPIRY = "2026-01-06"      # Weekly options expiry
    FUTURE_EXPIRY = "2026-01-27"      # Monthly futures expiry
    
    # ============================================================
    # TIMEFRAMES TO TEST
    # ============================================================
    TIMEFRAMES = ["1minute", "2minute", "3minute", "5minute"]
    
    # ============================================================
    # STRATEGY CONFIGURATION
    # ============================================================
    STRATEGIES_TO_RUN = ["ORIGINAL", "STRATEGY_A", "STRATEGY_B", "STRATEGY_C"]
    
    # Capital per strategy per timeframe
    CAPITAL_PER_STRATEGY = 10000
    
    # ============================================================
    # TRADING PARAMETERS
    # ============================================================
    LOT_SIZE = 75
    MAX_CAPITAL_USAGE = 0.9  # Use 90% of capital per trade
    
    # RSI Settings
    RSI_OVERSOLD = 40
    RSI_OVERBOUGHT = 60
    RSI_PERIOD = 14
    
    # Momentum Settings (Strategy C)
    RSI_MOMENTUM_LOW = 50
    RSI_MOMENTUM_HIGH = 70
    RSI_MOMENTUM_LOW_BEAR = 30
    RSI_MOMENTUM_HIGH_BEAR = 50
    MIN_CANDLE_BODY = 10
    
    # Exit Parameters
    TARGET_POINTS = 20
    STOP_LOSS_POINTS = 10
    TRAILING_STOP_ACTIVATION = 0.5  # Activate at 50% of target
    TRAILING_STOP_DISTANCE = 0.15   # Trail at 15% below peak
    
    # Time-based Exit
    MAX_HOLD_TIME_MINUTES = 30
    
    # Cooldown between trades
    COOLDOWN_SECONDS = 60
    
    # ============================================================
    # MARKET HOURS
    # ============================================================
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30
    
    NO_NEW_ENTRY_HOUR = 15
    NO_NEW_ENTRY_MINUTE = 20
    
    FORCE_EXIT_HOUR = 15
    FORCE_EXIT_MINUTE = 25
    
    # ============================================================
    # LOGGING PATHS
    # ============================================================
    BASE_LOG_PATH = "D:\\StockMarket\\StockMarket\\scripts\\claude\\expriment3"
    
    @classmethod
    def get_log_paths(cls):
        """Generate log directory paths"""
        return {
            'engine_log': f"{cls.BASE_LOG_PATH}\\claude_engine_log",
            'bot_log': f"{cls.BASE_LOG_PATH}\\claude_bot_log",
            'trade_book': f"{cls.BASE_LOG_PATH}\\claude_trade_book",
            'summary': f"{cls.BASE_LOG_PATH}\\claude_summary"
        }
    
    # ============================================================
    # DEBUGGING
    # ============================================================
    DEBUG_MODE = False  # Enable detailed RSI/VWAP calculation logs
    VERBOSE_LOGGING = True  # Print status updates
    
    # ============================================================
    # API RATE LIMITING
    # ============================================================
    RATE_LIMIT_SPOT = 0.5      # seconds between spot API calls
    RATE_LIMIT_FUTURE = 0.5    # seconds between future API calls
    RATE_LIMIT_CHAIN = 1.0     # seconds between chain API calls
    
    # ============================================================
    # VALIDATION
    # ============================================================
    @classmethod
    def validate(cls):
        """Validate configuration before running"""
        errors = []
        
        # Check API credentials
        if not cls.API_KEY or not cls.API_SECRET:
            errors.append("API credentials not configured")
        
        # Check dates
        try:
            datetime.strptime(cls.OPTION_EXPIRY, "%Y-%m-%d")
            datetime.strptime(cls.FUTURE_EXPIRY, "%Y-%m-%d")
        except ValueError:
            errors.append("Invalid date format. Use YYYY-MM-DD")
        
        # Check timeframes
        valid_timeframes = ["1minute", "2minute", "3minute", "5minute"]
        for tf in cls.TIMEFRAMES:
            if tf not in valid_timeframes:
                errors.append(f"Invalid timeframe: {tf}")
        
        # Check capital
        if cls.CAPITAL_PER_STRATEGY <= 0:
            errors.append("Capital must be positive")
        
        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
        
        return True
    
    @classmethod
    def print_config(cls):
        """Print current configuration"""
        print("\n" + "="*80)
        print("📋 CONFIGURATION SUMMARY")
        print("="*80)
        print(f"Timeframes: {', '.join(cls.TIMEFRAMES)}")
        print(f"Strategies: {', '.join(cls.STRATEGIES_TO_RUN)}")
        print(f"Capital per Strategy: Rs.{cls.CAPITAL_PER_STRATEGY:,}")
        print(f"Total Test Combinations: {len(cls.TIMEFRAMES)} × {len(cls.STRATEGIES_TO_RUN)} = {len(cls.TIMEFRAMES) * len(cls.STRATEGIES_TO_RUN)}")
        print(f"Option Expiry: {cls.OPTION_EXPIRY}")
        print(f"Future Expiry: {cls.FUTURE_EXPIRY}")
        print("="*80 + "\n")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_timeframe_display_name(timeframe):
    """Convert API timeframe to display name"""
    mapping = {
        "1minute": "1min",
        "2minute": "2min",
        "3minute": "3min",
        "5minute": "5min"
    }
    return mapping.get(timeframe, timeframe)


def get_future_symbol(expiry_date):
    """Generate futures symbol from expiry date"""
    dt = datetime.strptime(expiry_date, "%Y-%m-%d")
    return f"NSE-NIFTY-{dt.strftime('%d%b%y')}-FUT"
