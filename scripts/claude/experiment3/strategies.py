"""
STRATEGIES - A, B, C implementations
"""

import pandas as pd
from typing import Optional, Dict
from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """Base class for all strategies"""
    
    def __init__(self, config):
        self.config = config
        self.name = "Base"
    
    @abstractmethod
    def check_entry(self, row: pd.Series, prev_row: pd.Series = None) -> Optional[str]:
        """
        Check if entry conditions are met
        
        Returns:
            "BUY_CE" for call entry
            "BUY_PE" for put entry
            None if no entry
        """
        pass
    
    def get_entry_reason(self, row:  pd.Series) -> Dict: 
        """Get detailed reason for entry/skip"""
        return {}


class StrategyA(BaseStrategy):
    """
    STRATEGY A: VWAP + EMA Crossover (Trend Following)
    
    BUY CE: 
        - FUTURES > VWAP
        - EMA5 > EMA13 (bullish crossover)
        - SPOT > EMA5 (price above fast EMA)
    
    BUY PE:
        - FUTURES < VWAP
        - EMA5 < EMA13 (bearish crossover)
        - SPOT < EMA5 (price below fast EMA)
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "A - VWAP + EMA Crossover"
    
    def check_entry(self, row: pd.Series, prev_row: pd.Series = None) -> Optional[str]: 
        # Extract values
        fut_above_vwap = row['fut_above_vwap']
        fut_below_vwap = row['fut_below_vwap']
        ema_bullish = row['ema_bullish']
        ema_bearish = row['ema_bearish']
        spot_above_ema = row['spot_above_ema_fast']
        spot_below_ema = row['spot_below_ema_fast']
        
        # BUY CE conditions
        if fut_above_vwap and ema_bullish and spot_above_ema:
            return "BUY_CE"
        
        # BUY PE conditions
        if fut_below_vwap and ema_bearish and spot_below_ema: 
            return "BUY_PE"
        
        return None
    
    def get_entry_reason(self, row:  pd.Series) -> Dict:
        return {
            "fut_close": row['fut_close'],
            "vwap": row['vwap'],
            "fut_vs_vwap":  "ABOVE" if row['fut_above_vwap'] else "BELOW",
            "ema_fast": round(row['ema_fast'], 2),
            "ema_slow": round(row['ema_slow'], 2),
            "ema_crossover": "BULLISH" if row['ema_bullish'] else ("BEARISH" if row['ema_bearish'] else "NEUTRAL"),
            "spot_close": row['close'],
            "spot_vs_ema": "ABOVE" if row['spot_above_ema_fast'] else "BELOW"
        }


class StrategyB(BaseStrategy):
    """
    STRATEGY B: VWAP Bounce (Mean Reversion)
    
    BUY CE:
        - FUTURES just crossed ABOVE VWAP (was below, now above)
        - RSI > 40 (not deeply oversold)
        - RSI < 70 (not overbought)
    
    BUY PE:
        - FUTURES just crossed BELOW VWAP (was above, now below)
        - RSI < 60 (not deeply overbought)
        - RSI > 30 (not oversold)
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "B - VWAP Bounce"
    
    def check_entry(self, row: pd.Series, prev_row: pd.Series = None) -> Optional[str]:
        if prev_row is None:
            return None
        
        # Current state
        fut_above_vwap = row['fut_above_vwap']
        fut_below_vwap = row['fut_below_vwap']
        rsi = row['rsi']
        
        # Previous state
        prev_fut_above_vwap = prev_row['fut_above_vwap']
        
        # BUY CE:  VWAP cross from below to above
        if fut_above_vwap and not prev_fut_above_vwap: 
            if rsi > self.config.rsi_oversold and rsi < 70:
                return "BUY_CE"
        
        # BUY PE: VWAP cross from above to below
        if fut_below_vwap and prev_fut_above_vwap: 
            if rsi < self.config.rsi_overbought and rsi > 30:
                return "BUY_PE"
        
        return None
    
    def get_entry_reason(self, row: pd.Series) -> Dict:
        return {
            "fut_close": row['fut_close'],
            "vwap": row['vwap'],
            "fut_vs_vwap": "ABOVE" if row['fut_above_vwap'] else "BELOW",
            "prev_fut_vs_vwap":  "ABOVE" if row.get('prev_fut_above_vwap', False) else "BELOW",
            "vwap_cross": "CROSSED_ABOVE" if (row['fut_above_vwap'] and not row.get('prev_fut_above_vwap', True)) else 
                         ("CROSSED_BELOW" if (row['fut_below_vwap'] and row.get('prev_fut_above_vwap', False)) else "NO_CROSS"),
            "rsi":  round(row['rsi'], 2)
        }


class StrategyC(BaseStrategy):
    """
    STRATEGY C: Momentum Breakout (Aggressive)
    
    BUY CE:
        - FUTURES > VWAP
        - Current candle is GREEN (close > open)
        - Candle body > 10 points (strong move)
        - RSI between 50-70 (momentum zone)
    
    BUY PE: 
        - FUTURES < VWAP
        - Current candle is RED (close < open)
        - Candle body > 10 points (strong move)
        - RSI between 30-50 (momentum zone)
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.name = "C - Momentum Breakout"
    
    def check_entry(self, row: pd.Series, prev_row: pd.Series = None) -> Optional[str]:
        # Extract values
        fut_above_vwap = row['fut_above_vwap']
        fut_below_vwap = row['fut_below_vwap']
        candle_green = row['candle_green']
        candle_body = row['candle_body']
        rsi = row['rsi']
        
        # BUY CE conditions
        if fut_above_vwap and candle_green: 
            if candle_body >= self.config.min_candle_body: 
                if self.config.rsi_momentum_low <= rsi <= self.config.rsi_momentum_high: 
                    return "BUY_CE"
        
        # BUY PE conditions
        if fut_below_vwap and not candle_green: 
            if candle_body >= self.config.min_candle_body:
                if self.config.rsi_momentum_low_bear <= rsi <= self.config.rsi_momentum_high_bear:
                    return "BUY_PE"
        
        return None
    
    def get_entry_reason(self, row:  pd.Series) -> Dict:
        return {
            "fut_close": row['fut_close'],
            "vwap": row['vwap'],
            "fut_vs_vwap": "ABOVE" if row['fut_above_vwap'] else "BELOW",
            "candle_color": "GREEN" if row['candle_green'] else "RED",
            "candle_body": round(row['candle_body'], 2),
            "min_body_required": self.config.min_candle_body,
            "rsi":  round(row['rsi'], 2)
        }


def get_strategy(strategy_code: str, config) -> BaseStrategy: 
    """Factory function to get strategy by code"""
    strategies = {
        "A": StrategyA,
        "B":  StrategyB,
        "C":  StrategyC
    }
    
    if strategy_code.upper() not in strategies:
        raise ValueError(f"Unknown strategy:  {strategy_code}")
    
    return strategies[strategy_code.upper()](config)