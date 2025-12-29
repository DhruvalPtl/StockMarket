"""
CONFIGURATION - All parameters in one place
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class Config:
    """All bot configuration parameters"""
    
    # ===========================================
    # CAPITAL & POSITION SIZING
    # ===========================================
    capital: float = 10000.0
    lot_size: int = 75
    
    # ===========================================
    # PROFIT & LOSS LIMITS (per trade)
    # ===========================================
    target_points: float = 10.0          # ₹750 profit
    stop_loss_points: float = 4.0        # ₹300 loss
    
    # ===========================================
    # TRAILING STOP
    # ===========================================
    trailing_trigger_points: float = 4.0  # Activate after +4 pts
    trailing_stop_points: float = 3.0     # Trail 3 pts from peak
    
    # ===========================================
    # DAILY LIMITS
    # ===========================================
    max_daily_loss: float = 900.0        # Stop trading after ₹900 loss
    daily_target: float = 2000.0         # Stop trading after ₹2000 profit
    
    # ===========================================
    # TIME RULES
    # ===========================================
    market_start: str = "09:20"          # Start trading (skip first 5 mins)
    market_end: str = "15:15"            # Stop new entries
    force_exit_time: str = "15:20"       # Force exit all positions
    
    # ===========================================
    # COOLDOWN
    # ===========================================
    cooldown_seconds: int = 120          # 2 minutes after exit
    cooldown_after_loss_seconds: int = 300  # 5 minutes after 2 consecutive losses
    
    # ===========================================
    # OPTION SELECTION
    # ===========================================
    min_option_price: float = 30.0       # Minimum option price
    max_option_price: float = 200.0      # Maximum option price
    
    # ===========================================
    # POSITION MANAGEMENT
    # ===========================================
    max_hold_minutes: int = 30           # Max hold time
    
    # ===========================================
    # STRATEGY A:  VWAP + EMA CROSSOVER
    # ===========================================
    ema_fast: int = 5
    ema_slow: int = 13
    
    # ===========================================
    # STRATEGY B:  VWAP BOUNCE
    # ===========================================
    vwap_lookback: int = 3               # Candles to check for cross
    rsi_oversold: float = 40.0
    rsi_overbought: float = 60.0
    
    # ===========================================
    # STRATEGY C:  MOMENTUM BREAKOUT
    # ===========================================
    min_candle_body: float = 10.0        # Minimum candle body size
    rsi_momentum_low: float = 50.0
    rsi_momentum_high: float = 70.0
    rsi_momentum_low_bear: float = 30.0
    rsi_momentum_high_bear: float = 50.0
    
    # ===========================================
    # RSI
    # ===========================================
    rsi_period: int = 14
    
    # ===========================================
    # PATHS
    # ===========================================
    data_file: str = r"D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\data\\nifty_complete_1min.csv"
    cache_dir: str = r"D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\option_cache"
    output_dir: str = r"D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\results_v4"
    debug_dir: str = r"D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\debug_logs_v4"


# Strategy descriptions for menu
STRATEGY_INFO = {
    "A": {
        "name":  "VWAP + EMA Crossover",
        "type": "Trend Following",
        "description": "Enters when price is trending with EMA confirmation"
    },
    "B": {
        "name": "VWAP Bounce",
        "type": "Mean Reversion",
        "description": "Enters when price crosses VWAP with RSI confirmation"
    },
    "C": {
        "name": "Momentum Breakout",
        "type": "Aggressive",
        "description": "Enters on strong candle moves with momentum"
    }
}

TIMEFRAME_INFO = {
    "1min": {"minutes": 1, "description": "Fast signals, more trades"},
    "3min": {"minutes":  3, "description": "Balanced, less noise"},
    "5min": {"minutes":  5, "description": "Slower, stronger signals"}
}