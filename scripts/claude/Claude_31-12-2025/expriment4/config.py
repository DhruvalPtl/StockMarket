import os
import sys
from datetime import datetime

class BotConfig:
    """
    Central Configuration for the Multi-Timeframe Trading Bot.
    All settings are centralized here to prevent hardcoding in logic files.
    """

    # ============================================================
    # 1. API CREDENTIALS & CONNECTION
    # ============================================================
    # specific credentials provided by user
    API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
    API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
    
    # Rate Limiting (Seconds between calls)
    RATE_LIMIT_SPOT = 0.5
    RATE_LIMIT_FUTURE = 0.5
    RATE_LIMIT_CHAIN = 1.0

    # ============================================================
    # 2. CONTRACT DETAILS
    # ============================================================
    # Format: YYYY-MM-DD
    OPTION_EXPIRY = "2026-01-06"      # Weekly options expiry
    FUTURE_EXPIRY = "2026-01-27"      # Monthly futures expiry
    
    # ============================================================
    # 3. TIMEFRAMES & STRATEGIES
    # ============================================================
    # Supported: "1minute", "2minute", "3minute", "5minute"
    TIMEFRAMES = ["1minute", "2minute", "3minute", "5minute"]
    
    # Strategies to activate
    STRATEGIES_TO_RUN = ["ORIGINAL", "STRATEGY_A", "STRATEGY_B", "STRATEGY_C"]
    
    # ============================================================
    # 4. CAPITAL & RISK MANAGEMENT
    # ============================================================
    CAPITAL_PER_STRATEGY = 10000.0  # INR
    MAX_CAPITAL_USAGE_PCT = 0.90    # Max 90% usage per trade
    LOT_SIZE = 75                   # Nifty Lot Size
    
    # ============================================================
    # 5. STRATEGY PARAMETERS
    # ============================================================
    # RSI Thresholds
    RSI_OVERSOLD = 40
    RSI_OVERBOUGHT = 60
    RSI_PERIOD = 14
    
    # Strategy C (Momentum) Specifics
    RSI_MOMENTUM_LOW = 50
    RSI_MOMENTUM_HIGH = 70
    RSI_MOMENTUM_LOW_BEAR = 30
    RSI_MOMENTUM_HIGH_BEAR = 50
    MIN_CANDLE_BODY = 10  # Points
    
    # Exit Rules
    TARGET_POINTS = 20
    STOP_LOSS_POINTS = 10
    
    # Trailing Stop Logic
    TRAILING_STOP_ACTIVATION = 0.5  # Activate when 50% of target reached
    TRAILING_STOP_DISTANCE = 0.15   # Trail 15% below peak price
    
    # Time-based Exit
    MAX_HOLD_TIME_MINUTES = 30
    
    # Cooldown
    COOLDOWN_SECONDS = 60  # Wait time after a trade before scanning again
    
    # ============================================================
    # 6. MARKET HOURS (24-hour format)
    # ============================================================
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30
    
    # Risk Limits
    NO_NEW_ENTRY_HOUR = 15
    NO_NEW_ENTRY_MINUTE = 20
    
    FORCE_EXIT_HOUR = 15
    FORCE_EXIT_MINUTE = 25
    
    # ============================================================
    # 7. SYSTEM & LOGGING
    # ============================================================
    DEBUG_MODE = False
    VERBOSE_LOGGING = True
    
    # Base paths
    # Using raw strings (r"...") to handle Windows backslashes safely
    BASE_LOG_PATH = r"D:\\StockMarket\\StockMarket\\scripts\\claude\\expriment4\\logs"
    
    @classmethod
    def get_log_paths(cls):
        """
        Returns a dictionary of validated log paths.
        Creates the directories if they do not exist.
        """
        paths = {
            'engine_log': os.path.join(cls.BASE_LOG_PATH, "claude_engine_log"),
            'bot_log': os.path.join(cls.BASE_LOG_PATH, "claude_bot_log"),
            'trade_book': os.path.join(cls.BASE_LOG_PATH, "claude_trade_book"),
            'summary': os.path.join(cls.BASE_LOG_PATH, "claude_summary")
        }
        
        # Ensure all directories exist
        for key, path in paths.items():
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                print(f"❌ CRITICAL ERROR: Could not create log directory: {path}")
                print(f"   Reason: {e}")
                sys.exit(1)
                
        return paths

    @classmethod
    def validate(cls):
        """
        Performs a strict self-check of the configuration.
        Raises ValueError if any setting is invalid.
        """
        errors = []
        
        # 1. Check Credentials
        if not cls.API_KEY or len(cls.API_KEY) < 10:
            errors.append("API_KEY is missing or appears invalid.")
        if not cls.API_SECRET:
            errors.append("API_SECRET is missing.")

        # 2. Check Dates
        try:
            datetime.strptime(cls.OPTION_EXPIRY, "%Y-%m-%d")
        except ValueError:
            errors.append(f"OPTION_EXPIRY '{cls.OPTION_EXPIRY}' is not in YYYY-MM-DD format.")
            
        try:
            datetime.strptime(cls.FUTURE_EXPIRY, "%Y-%m-%d")
        except ValueError:
            errors.append(f"FUTURE_EXPIRY '{cls.FUTURE_EXPIRY}' is not in YYYY-MM-DD format.")

        # 3. Check Logic
        if cls.TARGET_POINTS <= cls.STOP_LOSS_POINTS:
            errors.append("Logic Error: TARGET_POINTS must be greater than STOP_LOSS_POINTS.")
            
        if cls.CAPITAL_PER_STRATEGY < 1000:
            errors.append(f"Capital Rs.{cls.CAPITAL_PER_STRATEGY} is too low for trading.")

        # 4. Check Timeframes
        valid_tfs = ["1minute", "2minute", "3minute", "5minute", "15minute", "30minute", "60minute", "1day"]
        for tf in cls.TIMEFRAMES:
            if tf not in valid_tfs:
                errors.append(f"Invalid Timeframe configured: '{tf}'")

        if errors:
            error_msg = "\n❌ CONFIGURATION VALIDATION FAILED:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)
            
        print("✅ Configuration validated successfully.")
        return True

    @classmethod
    def print_config(cls):
        """Prints a summary of the active configuration."""
        print("\n" + "="*60)
        print("⚙️  ACTIVE BOT CONFIGURATION")
        print("="*60)
        print(f"Timeframes:      {cls.TIMEFRAMES}")
        print(f"Strategies:      {cls.STRATEGIES_TO_RUN}")
        print(f"Capital/Strat:   Rs.{cls.CAPITAL_PER_STRATEGY:,.2f}")
        print(f"Option Expiry:   {cls.OPTION_EXPIRY}")
        print(f"Logging Path:    {cls.BASE_LOG_PATH}")
        print("="*60 + "\n")

# ============================================================
# UTILITY HELPERS
# ============================================================

def get_timeframe_display_name(timeframe: str) -> str:
    """
    Standardizes timeframe display names.
    Ex: '1minute' -> '1min'
    """
    mapping = {
        "1minute": "1min",
        "2minute": "2min",
        "3minute": "3min",
        "5minute": "5min",
        "15minute": "15min"
    }
    return mapping.get(timeframe, timeframe)

def get_future_symbol(expiry_date: str) -> str:
    """
    Generates the NSE Future symbol string.
    Format: NSE-NIFTY-DDMMMYY-FUT (e.g., NSE-NIFTY-27Jan26-FUT)
    """
    try:
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        date_str = dt.strftime("%d%b%y") 
        return f"NSE-NIFTY-{date_str}-FUT"
    except Exception as e:
        print(f"❌ Error generating future symbol from date {expiry_date}: {e}")
        return "ERROR_SYMBOL"