"""
STRATEGIES MODULE
Contains the logic for all trading strategies.
Refactored for modularity, safety, and strict re-entry prevention.
"""

import pandas as pd
from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import Optional, Tuple, Dict

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
        
        Args:
            row: Current candle data (pandas Series) containing price/indicators.
            prev_row: Previous candle data (optional, for crossover logic).
            
        Returns:
            Tuple (Signal, Reason)
            Signal: "BUY_CE", "BUY_PE", or None
            Reason: Description of why the signal was generated (for logging).
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


class StrategyOriginal(BaseStrategy):
    """
    ORIGINAL STRATEGY: Hybrid Approach
    - Early Market (< 10:00 AM): Uses Market Bias (Price vs VWAP + PCR).
    - Full Market (> 10:00 AM): Uses EMA Crossover + RSI + VWAP.
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "ORIGINAL"
        self.early_trading_mode = True
    
    def check_entry(self, row: pd.Series, prev_row: pd.Series = None) -> Tuple[Optional[str], str]:
        # 1. Re-entry Guard
        timestamp = row.get('timestamp') # Ensure timestamp is passed in row data
        if not self._is_new_candle(timestamp):
            return None, ""

        # 2. Auto-switch from Early to Full mode
        # Logic Fix: Actually turn off early mode after 10:00 AM
        current_time_obj = datetime.now().time()
        if self.early_trading_mode and current_time_obj > time(10, 0):
            self.early_trading_mode = False
            # We don't print here to avoid flooding logs, handled in runner/logger
        
        # 3. Data Extraction
        futures = row['fut_close']
        spot = row['close']
        vwap = row['vwap']
        rsi = row['rsi']
        pcr = row.get('pcr', 0)
        
        # Safety Check
        if vwap == 0 or futures == 0:
            return None, "Data Invalid"

        signal = None
        reason = ""

        # 4. Strategy Logic
        if self.early_trading_mode:
            # === EARLY MODE ===
            # Bullish Bias: Futures > VWAP + (PCR Bullish OR Strong Candle)
            bullish_score = 0
            if futures > vwap: bullish_score += 2
            if pcr > 1.1: bullish_score += 1
            if row.get('candle_green', False): bullish_score += 1
            
            # Bearish Bias
            bearish_score = 0
            if futures < vwap: bearish_score += 2
            if pcr < 0.9: bearish_score += 1
            if not row.get('candle_green', False): bearish_score += 1
            
            if bullish_score >= 3:
                signal = "BUY_CE"
                reason = f"Early_Bullish (Score {bullish_score})"
            elif bearish_score >= 3:
                signal = "BUY_PE"
                reason = f"Early_Bearish (Score {bearish_score})"

        else:
            # === FULL MODE ===
            # Uses EMA Crossover + RSI Confirmation
            ema_fast = row['ema_fast']
            ema_slow = row['ema_slow']
            
            # Buy CE: Fut > VWAP + Bullish Crossover + RSI Bullish
            if futures > vwap and ema_fast > ema_slow and 55 <= rsi <= 75:
                signal = "BUY_CE"
                reason = f"Full_Bullish (EMA Cross + RSI {rsi:.1f})"
            
            # Buy PE: Fut < VWAP + Bearish Crossover + RSI Bearish
            elif futures < vwap and ema_fast < ema_slow and 25 <= rsi <= 45:
                signal = "BUY_PE"
                reason = f"Full_Bearish (EMA Cross + RSI {rsi:.1f})"

        # 5. Finalize
        if signal:
            self._mark_signal_generated(timestamp)
            return signal, reason
        
        return None, ""


class StrategyA(BaseStrategy):
    """
    STRATEGY A: VWAP + EMA Crossover (Trend Following)
    Focus: Capturing sustainable trends confirmed by multiple indicators.
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "A - VWAP + EMA Trend"
    
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


class StrategyB(BaseStrategy):
    """
    STRATEGY B: VWAP Bounce (Mean Reversion)
    Focus: Catching price crossing VWAP with RSI support (not oversold/overbought).
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "B - VWAP Bounce"
    
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
        # Check previous state manually if not in row, or use logic passed from runner
        prev_fut_above_vwap = prev_row.get('fut_above_vwap', False)
        
        rsi = row['rsi']
        signal = None
        reason = ""
        
        # BUY CE: Crossed from BELOW to ABOVE VWAP
        if fut_above_vwap and not prev_fut_above_vwap:
            # Filter: Ensure RSI has room to grow (not > 70) and isn't dead (< 40)
            if self.config.RSI_OVERSOLD < rsi < 70:
                signal = "BUY_CE"
                reason = f"VWAP_Bounce_Up (Crossed Above + RSI {rsi:.1f})"

        # BUY PE: Crossed from ABOVE to BELOW VWAP
        elif not fut_above_vwap and prev_fut_above_vwap:
            # Filter: Ensure RSI has room to drop (not < 30) and isn't peaked (> 60)
            if 30 < rsi < self.config.RSI_OVERBOUGHT:
                signal = "BUY_PE"
                reason = f"VWAP_Bounce_Down (Crossed Below + RSI {rsi:.1f})"

        if signal:
            self._mark_signal_generated(timestamp)
            return signal, reason
            
        return None, ""


class StrategyC(BaseStrategy):
    """
    STRATEGY C: Momentum Breakout (Aggressive)
    Focus: Large candle bodies moving away from VWAP with strong momentum.
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "C - Momentum Breakout"
    
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

def get_strategy(strategy_code: str, config) -> BaseStrategy:
    """Factory to instantiate strategies by name."""
    mapping = {
        "ORIGINAL": StrategyOriginal,
        "STRATEGY_A": StrategyA,
        "STRATEGY_B": StrategyB,
        "STRATEGY_C": StrategyC
    }
    
    strat_class = mapping.get(strategy_code.upper())
    if not strat_class:
        raise ValueError(f"Unknown strategy code: {strategy_code}")
        
    return strat_class(config)