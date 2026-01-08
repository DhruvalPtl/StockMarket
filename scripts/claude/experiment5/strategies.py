"""
STRATEGIES MODULE
Contains the logic for all trading strategies.
Restored full logic for A, B, C and added D (Liquidity Sweep).
"""

import pandas as pd
from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import Optional, Tuple, Dict

# ============================================================
# BASE STRATEGY CLASS
# ============================================================
class BaseStrategy(ABC):
    """
    Abstract Base Class for all strategies.
    Enforces a common interface and handles shared logic like re-entry guarding.
    """
    
    def __init__(self, config):
        self.config = config
        self.name = "BaseStrategy"
        
        # RE-ENTRY GUARD: Tracks the timestamp of the last generated signal.
        # Prevents generating multiple signals for the same candle.
        self.last_signal_timestamp = None 

    @abstractmethod
    def check_entry(self, row: pd.Series, prev_row: pd.Series = None) -> Tuple[Optional[str], str]:
        """
        Analyzes the market data row to generate entry signals.
        Returns: (Signal, Reason)
        """
        pass

    def _is_new_candle(self, current_timestamp) -> bool:
        """
        Critical check to prevent 'Machine Gun' re-entry on the same candle.
        Returns True if this is a new candle since the last signal.
        """
        if self.last_signal_timestamp == current_timestamp:
            return False
        return True

    def _mark_signal_generated(self, current_timestamp):
        """Updates the last signal timestamp."""
        self.last_signal_timestamp = current_timestamp

    def _get_atm_strike(self, spot_price):
        """Helper to find nearest 50 strike."""
        return round(spot_price / 50) * 50


# ============================================================
# STRATEGY A: TREND FOLLOWING
# ============================================================
class StrategyA(BaseStrategy):
    """
    STRATEGY A: VWAP + EMA Crossover (Trend Following)
    Focus: Capturing sustainable trends confirmed by multiple indicators.
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "STRATEGY_A"
    
    def check_entry(self, row: pd.Series, prev_row: pd.Series = None) -> Tuple[Optional[str], str]:
        # 1. Re-entry Guard
        timestamp = row.get('timestamp')
        if not self._is_new_candle(timestamp):
            return None, ""

        # 2. Extract Conditions
        fut_above_vwap = row['fut_above_vwap']
        fut_below_vwap = row['fut_below_vwap']
        ema_bullish = row['ema_bullish']    # EMA5 > EMA13
        ema_bearish = row['ema_bearish']    # EMA5 < EMA13
        spot_above_fast = row['spot_above_ema_fast']
        spot_below_fast = row['spot_below_ema_fast']
        
        signal = None
        reason = ""

        # 3. Logic
        # BUY CE: Price > VWAP + EMA Cross UP + Price > Fast EMA
        if fut_above_vwap and ema_bullish and spot_above_fast:
            signal = "BUY_CE"
            reason = "Trend_Up (Above VWAP + EMA Bullish)"
        
        # BUY PE: Price < VWAP + EMA Cross DOWN + Price < Fast EMA
        elif fut_below_vwap and ema_bearish and spot_below_fast:
            signal = "BUY_PE"
            reason = "Trend_Down (Below VWAP + EMA Bearish)"
            
        if signal:
            self._mark_signal_generated(timestamp)
            return signal, reason

        return None, ""


# ============================================================
# STRATEGY B: VWAP BOUNCE
# ============================================================
class StrategyB(BaseStrategy):
    """
    STRATEGY B: VWAP Bounce (Mean Reversion)
    Focus: Catching price crossing VWAP with RSI support.
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "STRATEGY_B"
    
    def check_entry(self, row: pd.Series, prev_row: pd.Series = None) -> Tuple[Optional[str], str]:
        # Need previous row to detect crossover
        if prev_row is None:
            return None, ""
            
        # 1. Re-entry Guard
        timestamp = row.get('timestamp')
        if not self._is_new_candle(timestamp):
            return None, ""

        # 2. Logic
        fut_above_vwap = row['fut_above_vwap']
        # Check previous state
        prev_fut_above_vwap = prev_row.get('fut_above_vwap', False)
        
        rsi = row['rsi']
        signal = None
        reason = ""
        
        # BUY CE: Crossed from BELOW to ABOVE VWAP
        if fut_above_vwap and not prev_fut_above_vwap:
            if self.config.RSI_OVERSOLD < rsi < 70:
                signal = "BUY_CE"
                reason = f"VWAP_Bounce_Up (Crossed Above + RSI {rsi:.1f})"

        # BUY PE: Crossed from ABOVE to BELOW VWAP
        elif not fut_above_vwap and prev_fut_above_vwap:
            if 30 < rsi < self.config.RSI_OVERBOUGHT:
                signal = "BUY_PE"
                reason = f"VWAP_Bounce_Down (Crossed Below + RSI {rsi:.1f})"

        if signal:
            self._mark_signal_generated(timestamp)
            return signal, reason
            
        return None, ""


# ============================================================
# STRATEGY C: MOMENTUM
# ============================================================
class StrategyC(BaseStrategy):
    """
    STRATEGY C: Momentum Breakout (Aggressive)
    Focus: Large candle bodies moving away from VWAP with strong momentum.
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "STRATEGY_C"
    
    def check_entry(self, row: pd.Series, prev_row: pd.Series = None) -> Tuple[Optional[str], str]:
        # 1. Re-entry Guard
        timestamp = row.get('timestamp')
        if not self._is_new_candle(timestamp):
            return None, ""

        # 2. Extract
        fut_above_vwap = row['fut_above_vwap']
        fut_below_vwap = row['fut_below_vwap']
        candle_green = row['candle_green']
        candle_body = row['candle_body']
        rsi = row['rsi']
        
        signal = None
        reason = ""
        
        # 3. Logic
        # BUY CE: Above VWAP + Green Candle + Big Body + Momentum RSI
        if fut_above_vwap and candle_green:
            if candle_body >= self.config.MIN_CANDLE_BODY:
                if self.config.RSI_MOMENTUM_LOW <= rsi <= self.config.RSI_MOMENTUM_HIGH:
                    signal = "BUY_CE"
                    reason = f"Momentum_Up (Body {candle_body:.1f} + RSI {rsi:.1f})"

        # BUY PE: Below VWAP + Red Candle + Big Body + Momentum RSI (Bearish Zone)
        elif fut_below_vwap and not candle_green:
            if candle_body >= self.config.MIN_CANDLE_BODY:
                if self.config.RSI_MOMENTUM_LOW_BEAR <= rsi <= self.config.RSI_MOMENTUM_HIGH_BEAR:
                    signal = "BUY_PE"
                    reason = f"Momentum_Down (Body {candle_body:.1f} + RSI {rsi:.1f})"
        
        if signal:
            self._mark_signal_generated(timestamp)
            return signal, reason

        return None, ""


# ============================================================
# STRATEGY D: LIQUIDITY SWEEP (TRAP)
# ============================================================
class LiquiditySweepStrategy(BaseStrategy):
    """
    STRATEGY D: Institutional Liquidity Sweep (SFP).
    Logic: Fades the breakout of Previous Day High/Low if it fails to sustain.
    """
    def __init__(self, config):
        super().__init__(config)
        self.name = "STRATEGY_D"
        
        # Config values
        self.pdh = config.PREV_DAY_HIGH
        self.pdl = config.PREV_DAY_LOW
        self.min_sweep = config.SWEEP_MIN_POINTS
        self.max_sweep = config.SWEEP_MAX_POINTS

    def check_entry(self, row: pd.Series, prev_row: pd.Series = None) -> Tuple[Optional[str], str]:
        # 1. Re-entry Guard
        timestamp = row.get('timestamp')
        if not self._is_new_candle(timestamp):
            return None, ""

        # 2. Time Filter (Avoid first 15 mins)
        try:
            # Timestamp is datetime object
            current_time_str = timestamp.strftime("%H:%M")
            if current_time_str < "09:30":
                return None, ""
        except:
            return None, ""

        # Unpack Data
        # Ensure your Data Engine provides High/Low/Close in 'row'
        high = row.get('fut_high', 0)
        low = row.get('fut_low', 0)
        close = row.get('fut_close', 0)
        
        if high == 0: return None, "" # Safety

        signal = None
        reason = ""

        # --- SCENARIO 1: BEARISH TRAP (Fake Breakout of Day High) ---
        if high > self.pdh:
            sweep_depth = high - self.pdh
            if (self.min_sweep <= sweep_depth <= self.max_sweep) and (close < self.pdh):
                print(f"🪤 BEARISH TRAP: Swept High {high} but closed {close} (< {self.pdh})")
                signal = "BUY_PE"
                reason = f"PDH_SWEEP_REJECTION (High {high} > {self.pdh})"

        # --- SCENARIO 2: BULLISH TRAP (Fake Breakdown of Day Low) ---
        if low < self.pdl:
            sweep_depth = self.pdl - low
            if (self.min_sweep <= sweep_depth <= self.max_sweep) and (close > self.pdl):
                print(f"🪤 BULLISH TRAP: Swept Low {low} but closed {close} (> {self.pdl})")
                signal = "BUY_CE"
                reason = f"PDL_SWEEP_REJECTION (Low {low} < {self.pdl})"

        if signal:
            self._mark_signal_generated(timestamp)
            return signal, reason

        return None, ""


# ============================================================
# FACTORY FUNCTION (The Fix)
# ============================================================
def get_strategy(strategy_name: str, config) -> BaseStrategy:
    """
    Factory to return the correct strategy instance.
    Handles 'ORIGINAL' by importing from multi_strategy_bot safely.
    """
    
    if strategy_name == "ORIGINAL":
        # Local import to prevent circular dependency
        try:
            from multi_strategy_bot import OriginalStrategy
            return OriginalStrategy(config)
        except ImportError:
            print("⚠️ Could not import OriginalStrategy. Check multi_strategy_bot.py")
            return None

    elif strategy_name == "STRATEGY_A":
        return StrategyA(config)
        
    elif strategy_name == "STRATEGY_B":
        return StrategyB(config)
        
    elif strategy_name == "STRATEGY_C":
        return StrategyC(config)
        
    elif strategy_name == "STRATEGY_D":
        return LiquiditySweepStrategy(config)
        
    else:
        print(f"❌ Unknown Strategy Code: {strategy_name}")
        return None