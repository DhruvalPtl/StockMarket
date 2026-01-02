"""
LIQUIDITY SWEEP STRATEGY
Smart money strategy that hunts stop-loss clusters.

This is a REVERSAL strategy that catches: 
- False breakouts above resistance (short squeeze then reverse)
- False breakdowns below support (long squeeze then reverse)

How it works:
1. Price breaks a key level (swing high/low)
2. Stop-losses get triggered (liquidity grabbed)
3. Price quickly reverses (smart money entering)
4. We enter in the reversal direction

This is how institutional traders and HFTs operate. 
"""

from typing import Tuple, Optional, List
from datetime import datetime
from collections import deque

import sys
import os
sys. path.append(os.path.dirname(os.path.dirname(os.path. abspath(__file__))))

from strategies.base_strategy import (
    BaseStrategy, SignalType, MarketData, StrategySignal
)
from market_intelligence.market_context import (
    MarketContext, MarketRegime, MarketBias, TimeWindow, KeyLevel
)


class LiquiditySweepStrategy(BaseStrategy):
    """
    LIQUIDITY SWEEP (STOP HUNT) STRATEGY
    
    Focus:  Catching reversals after false breakouts. 
    
    The Pattern:
    1. Price approaches key level (swing high/low, round number)
    2. Price BREAKS the level (triggering stop-losses)
    3. Price immediately REVERSES (trap complete)
    4. We enter in the reversal direction
    
    Key Insight: 
    - Retail traders put stops just beyond obvious levels
    - Smart money hunts these stops for liquidity
    - The reversal after the hunt is high-probability
    
    Works best in: RANGING, VOLATILE markets
    Avoid:  Strong TRENDING (breakouts are real, not traps)
    """
    
    STRATEGY_NAME = "Liquidity_Sweep"
    STRATEGY_CODE = "LIQUIDITY_SWEEP"
    OPTIMAL_REGIMES = ["RANGING", "VOLATILE"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe: str = "1minute"):
        super().__init__(config, timeframe)
        
        # Track recent highs/lows for sweep detection
        self.recent_highs: deque = deque(maxlen=20)
        self.recent_lows: deque = deque(maxlen=20)
        
        # Sweep detection settings
        self.sweep_threshold = 5  # Points beyond level to confirm sweep
        self. reversal_threshold = 10  # Points reversal to confirm trap
        
        # Track potential sweeps
        self. potential_sweep_high:  Optional[float] = None
        self. potential_sweep_low: Optional[float] = None
        self.sweep_detected_candle: int = 0
        self.candle_count: int = 0
    
    def _check_entry_conditions(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]:
        """
        Detects liquidity sweeps and generates reversal signals.
        """
        self.candle_count += 1
        
        # Update recent highs/lows
        self. recent_highs. append(data.future_high)
        self.recent_lows.append(data.future_low)
        
        # Need enough data
        if len(self.recent_highs) < 5:
            return SignalType.NO_SIGNAL, "", 0
        
        # Method 1: Use key levels from context
        if context.key_levels:
            signal = self._check_key_level_sweep(data, context)
            if signal[0] != SignalType.NO_SIGNAL: 
                return signal
        
        # Method 2: Use recent swing points
        signal = self._check_swing_sweep(data, context)
        if signal[0] != SignalType.NO_SIGNAL:
            return signal
        
        return SignalType.NO_SIGNAL, "", 0
    
    def _check_key_level_sweep(self, data:  MarketData, context: MarketContext) -> Tuple[SignalType, str, int]:
        """
        Check for sweeps of key levels (from LiquidityMapper).
        """
        for level in context.key_levels:
            # Check for resistance sweep (bullish trap -> go bearish)
            if level.level_type == 'RESISTANCE': 
                if self._is_resistance_sweep(data, level. price):
                    score = 3 + level.strength  # Higher strength = better level
                    return (
                        SignalType.BUY_PE,
                        f"Sweep_Resistance ({level.source}@{level.price:. 0f})",
                        min(5, score)
                    )
            
            # Check for support sweep (bearish trap -> go bullish)
            elif level.level_type == 'SUPPORT':
                if self._is_support_sweep(data, level.price):
                    score = 3 + level.strength
                    return (
                        SignalType.BUY_CE,
                        f"Sweep_Support ({level.source}@{level.price:.0f})",
                        min(5, score)
                    )
        
        return SignalType.NO_SIGNAL, "", 0
    
    def _check_swing_sweep(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]:
        """
        Check for sweeps of recent swing highs/lows. 
        """
        # Find recent swing high (excluding last 2 candles)
        if len(self.recent_highs) >= 5:
            swing_high = max(list(self.recent_highs)[:-2])
            
            if self._is_resistance_sweep(data, swing_high):
                return (
                    SignalType.BUY_PE,
                    f"Sweep_SwingHigh (@{swing_high:. 0f})",
                    3
                )
        
        # Find recent swing low
        if len(self.recent_lows) >= 5:
            swing_low = min(list(self.recent_lows)[:-2])
            
            if self._is_support_sweep(data, swing_low):
                return (
                    SignalType. BUY_CE,
                    f"Sweep_SwingLow (@{swing_low:.0f})",
                    3
                )
        
        return SignalType.NO_SIGNAL, "", 0
    
    def _is_resistance_sweep(self, data: MarketData, resistance:  float) -> bool:
        """
        Detects a resistance sweep (bullish trap).
        
        Pattern:
        - Candle high goes ABOVE resistance (sweep)
        - Candle closes BELOW resistance (rejection)
        - Creates upper wick (selling pressure)
        """
        # Check if high swept resistance
        if data.future_high < resistance:
            return False
        
        # Check if swept by enough (not just a touch)
        sweep_distance = data.future_high - resistance
        if sweep_distance < self.sweep_threshold:
            return False
        
        # Check if closed below resistance (rejection)
        if data.future_close >= resistance:
            return False
        
        # Check for upper wick (rejection confirmation)
        upper_wick = data.future_high - max(data.future_open, data.future_close)
        if upper_wick < self.reversal_threshold:
            return False
        
        # Red candle preferred (confirms rejection)
        # But not required
        
        return True
    
    def _is_support_sweep(self, data: MarketData, support:  float) -> bool:
        """
        Detects a support sweep (bearish trap).
        
        Pattern:
        - Candle low goes BELOW support (sweep)
        - Candle closes ABOVE support (rejection)
        - Creates lower wick (buying pressure)
        """
        # Check if low swept support
        if data.future_low > support:
            return False
        
        # Check if swept by enough
        sweep_distance = support - data.future_low
        if sweep_distance < self. sweep_threshold: 
            return False
        
        # Check if closed above support (rejection)
        if data.future_close <= support:
            return False
        
        # Check for lower wick (rejection confirmation)
        lower_wick = min(data.future_open, data.future_close) - data.future_low
        if lower_wick < self.reversal_threshold: 
            return False
        
        return True


class FalseBreakoutStrategy(BaseStrategy):
    """
    FALSE BREAKOUT STRATEGY
    
    Similar to Liquidity Sweep but focuses on: 
    - Opening range breakouts that fail
    - Round number breakouts that fail
    
    Entry after price returns inside the range. 
    """
    
    STRATEGY_NAME = "False_Breakout"
    STRATEGY_CODE = "FALSE_BREAKOUT"
    OPTIMAL_REGIMES = ["RANGING", "VOLATILE"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "LUNCH_SESSION"]
    
    def __init__(self, config, timeframe:  str = "1minute"):
        super().__init__(config, timeframe)
        self.round_number_interval = 100  # 24000, 24100, etc.
    
    def _check_entry_conditions(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]: 
        """
        Detects false breakouts of opening range and round numbers.
        """
        # Check opening range false breakout
        if context.opening_range_set:
            signal = self._check_opening_range_false_breakout(data, context)
            if signal[0] != SignalType. NO_SIGNAL: 
                return signal
        
        # Check round number false breakout
        signal = self._check_round_number_false_breakout(data, context)
        if signal[0] != SignalType. NO_SIGNAL: 
            return signal
        
        return SignalType.NO_SIGNAL, "", 0
    
    def _check_opening_range_false_breakout(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]: 
        """
        False breakout of opening range.
        """
        or_high = context.opening_range_high
        or_low = context.opening_range_low
        
        # Need previous data
        if self.prev_data is None: 
            return SignalType.NO_SIGNAL, "", 0
        
        # False breakout above OR high
        # Previous candle:  closed above OR high (breakout)
        # Current candle: closed back inside range (failure)
        if (self.prev_data. future_close > or_high and 
            data.future_close < or_high and
            data.future_close > or_low):
            
            return (
                SignalType.BUY_PE,
                f"False_BO_ORH (Range:{or_low:.0f}-{or_high:. 0f})",
                4
            )
        
        # False breakout below OR low
        if (self.prev_data.future_close < or_low and 
            data. future_close > or_low and
            data.future_close < or_high):
            
            return (
                SignalType.BUY_CE,
                f"False_BO_ORL (Range:{or_low:.0f}-{or_high:. 0f})",
                4
            )
        
        return SignalType.NO_SIGNAL, "", 0
    
    def _check_round_number_false_breakout(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]: 
        """
        False breakout of round numbers.
        """
        if self.prev_data is None:
            return SignalType. NO_SIGNAL, "", 0
        
        # Find nearest round number
        round_num = round(data.future_close / self.round_number_interval) * self.round_number_interval
        
        # Check if previous candle broke above round number
        # and current candle fell back below
        if (self. prev_data.future_close > round_num and 
            self.prev_data. future_high > round_num + 10 and
            data. future_close < round_num):
            
            return (
                SignalType.BUY_PE,
                f"False_BO_Round ({round_num})",
                3
            )
        
        # Check break below round number
        if (self.prev_data.future_close < round_num and 
            self.prev_data. future_low < round_num - 10 and
            data.future_close > round_num):
            
            return (
                SignalType.BUY_CE,
                f"False_BO_Round ({round_num})",
                3
            )
        
        return SignalType.NO_SIGNAL, "", 0


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__": 
    print("\n🔬 Testing Liquidity Sweep Strategy.. .\n")
    
    class MockConfig:
        class Exit:
            COOLDOWN_SECONDS = 60
            EXITS_BY_REGIME = {'RANGING': {'target': 8, 'stop':  8}}
    
    from market_intelligence.market_context import MarketContextBuilder, KeyLevel
    
    strategy = LiquiditySweepStrategy(MockConfig())
    
    # Build context with key levels
    key_levels = [
        KeyLevel(price=24100, level_type='RESISTANCE', strength=3, source='SWING'),
        KeyLevel(price=23900, level_type='SUPPORT', strength=3, source='SWING'),
    ]
    
    context = MarketContextBuilder()\
        .set_regime(MarketRegime.RANGING, 18, 20)\
        .set_bias(MarketBias.NEUTRAL, 0)\
        .set_time_window(TimeWindow.MORNING_SESSION, 280, False)\
        .set_key_levels(key_levels, 23900, 24100, 24000, 24000)\
        .build()
    
    # Feed some candles to build history
    print("Building price history...")
    for i in range(5):
        data = MarketData(
            timestamp=datetime. now(),
            spot_price=24000 + i * 5,
            future_price=24010 + i * 5,
            future_open=24000 + i * 5,
            future_high=24020 + i * 5,
            future_low=23990 + i * 5,
            future_close=24010 + i * 5,
            vwap=24000, atm_strike=24000,
            rsi=50, ema_5=24000, ema_13=24000, ema_21=24000, ema_50=24000,
            adx=18, atr=40,
            candle_body=15, candle_range=30, is_green_candle=True,
            pcr=1.0, ce_oi_change_pct=1.0, pe_oi_change_pct=1.0,
            volume_relative=1.0
        )
        strategy.check_entry(data, context)
    
    # Simulate RESISTANCE SWEEP
    print("\nSimulating Resistance Sweep @ 24100...")
    
    sweep_data = MarketData(
        timestamp=datetime.now(),
        spot_price=24090,
        future_price=24085,
        future_open=24070,
        future_high=24115,  # Swept above 24100! 
        future_low=24060,
        future_close=24080,  # Closed back below 24100
        vwap=24050, atm_strike=24100,
        rsi=62,
        ema_5=24070, ema_13=24060, ema_21=24050, ema_50=24000,
        adx=20, atr=45,
        candle_body=10,  # Small body
        candle_range=55,  # Big range
        is_green_candle=True,
        pcr=1.05, ce_oi_change_pct=2.0, pe_oi_change_pct=1.5,
        volume_relative=1.6
    )
    
    signal = strategy. check_entry(sweep_data, context)
    
    if signal:
        print(f"Signal: {signal.signal_type.value}")
        print(f"Reason: {signal.reason}")
        print(f"Strength: {signal.strength.value}")
        print(f"Score: {signal.base_score}")
    else:
        print("No signal (sweep conditions not fully met)")
    
    # Simulate SUPPORT SWEEP
    print("\nSimulating Support Sweep @ 23900...")
    
    sweep_data_low = MarketData(
        timestamp=datetime.now(),
        spot_price=23920,
        future_price=23925,
        future_open=23940,
        future_high=23950,
        future_low=23885,  # Swept below 23900! 
        future_close=23930,  # Closed back above 23900
        vwap=23950, atm_strike=23900,
        rsi=38,
        ema_5=23930, ema_13=23940, ema_21=23950, ema_50=24000,
        adx=18, atr=50,
        candle_body=10,
        candle_range=65,
        is_green_candle=False,
        pcr=1.2, ce_oi_change_pct=1.5, pe_oi_change_pct=3.0,
        volume_relative=1.8
    )
    
    signal = strategy.check_entry(sweep_data_low, context)
    
    if signal:
        print(f"Signal: {signal. signal_type.value}")
        print(f"Reason:  {signal.reason}")
        print(f"Strength: {signal.strength.value}")
    else:
        print("No signal")
    
    print("\n✅ Liquidity Sweep Strategy Test Complete!")