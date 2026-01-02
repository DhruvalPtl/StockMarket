"""
EMA CROSSOVER STRATEGY
Pure EMA crossover with multiple confirmations. 

Different from VWAP_EMA_Trend: 
- Focuses specifically on the CROSSOVER event (not just alignment)
- Uses volume confirmation
- Tracks crossover recency

Entry Logic:
- EMA 5 crosses above/below EMA 13 (recent crossover)
- Volume confirms the move
- Price respects the new trend direction
"""

from typing import Tuple, Optional
from datetime import datetime
from collections import deque

import sys
import os
sys.path.append(os.path.dirname(os.path. dirname(os.path.abspath(__file__))))

from strategies.base_strategy import (
    BaseStrategy, SignalType, MarketData, StrategySignal
)
from market_intelligence.market_context import (
    MarketContext, MarketRegime, MarketBias, TimeWindow
)


class EMACrossoverStrategy(BaseStrategy):
    """
    EMA CROSSOVER STRATEGY
    
    Focus:  Catching the exact moment EMAs cross, with confirmation. 
    
    Key Difference from other EMA strategies:
    - Detects the CROSSOVER event (not just alignment)
    - Requires volume confirmation
    - Has cooldown after crossover to avoid whipsaws
    
    Entry Logic: 
    1. EMA 5 crosses EMA 13 (detected via previous data)
    2.  Crossover happened within last 3 candles (fresh)
    3. Volume is above average (confirmation)
    4. Price is on the right side of both EMAs
    
    Works best in:  TRENDING markets (early trend detection)
    """
    
    STRATEGY_NAME = "EMA_Crossover"
    STRATEGY_CODE = "EMA_CROSSOVER"
    OPTIMAL_REGIMES = ["TRENDING"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe: str = "1minute"):
        super().__init__(config, timeframe)
        
        # Track EMA relationship history
        self. ema_history:  deque = deque(maxlen=10)  # (ema5, ema13, timestamp)
        
        # Crossover tracking
        self.last_crossover_type: Optional[str] = None  # 'BULLISH' or 'BEARISH'
        self.last_crossover_index: int = 0
        self. candles_since_crossover: int = 999  # Large number initially
        
        # Settings
        self.crossover_freshness = 3  # Must trade within 3 candles of crossover
        self.min_volume_ratio = 1.3   # Volume must be 1.3x average
    
    def _check_entry_conditions(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]:
        """
        Detects EMA crossover and generates signal if fresh.
        """
        # Store current EMA state
        self.ema_history.append({
            'ema5': data. ema_5,
            'ema13': data.ema_13,
            'timestamp': data. timestamp
        })
        
        # Need at least 2 data points to detect crossover
        if len(self.ema_history) < 2:
            return SignalType.NO_SIGNAL, "", 0
        
        # Get previous state
        prev_state = self.ema_history[-2]
        curr_state = self. ema_history[-1]
        
        # Detect crossover
        prev_bullish = prev_state['ema5'] > prev_state['ema13']
        curr_bullish = curr_state['ema5'] > curr_state['ema13']
        
        # Check for new crossover
        if curr_bullish and not prev_bullish: 
            # BULLISH CROSSOVER:  EMA5 crossed above EMA13
            self.last_crossover_type = 'BULLISH'
            self.candles_since_crossover = 0
        elif not curr_bullish and prev_bullish:
            # BEARISH CROSSOVER: EMA5 crossed below EMA13
            self. last_crossover_type = 'BEARISH'
            self.candles_since_crossover = 0
        else:
            # No new crossover, increment counter
            self. candles_since_crossover += 1
        
        # Check if we should trade this crossover
        if self.candles_since_crossover > self.crossover_freshness:
            return SignalType.NO_SIGNAL, "", 0
        
        # Volume confirmation
        if data.volume_relative < self.min_volume_ratio: 
            return SignalType.NO_SIGNAL, "", 0
        
        # Generate signal based on crossover type
        if self.last_crossover_type == 'BULLISH':
            return self._generate_bullish_signal(data, context)
        elif self.last_crossover_type == 'BEARISH': 
            return self._generate_bearish_signal(data, context)
        
        return SignalType.NO_SIGNAL, "", 0
    
    def _generate_bullish_signal(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]: 
        """
        Generate BUY_CE signal after bullish crossover. 
        """
        score = 3  # Base score for fresh crossover
        
        # Confirmation: Price above both EMAs
        if data.spot_price > data. ema_5 and data.spot_price > data. ema_13:
            score += 1
        
        # Confirmation: Green candle
        if data.is_green_candle:
            score += 1
        
        # Confirmation:  RSI supportive (not overbought)
        if 45 < data.rsi < 70:
            score += 1
        
        # Confirmation:  VWAP alignment
        if data. price_above_vwap: 
            score += 1
        
        # Confirmation:  Trend regime
        if context. regime == MarketRegime. TRENDING_UP:
            score += 1
        
        # Strong volume bonus
        if data. volume_relative >= 2. 0:
            score += 1
        
        return (
            SignalType. BUY_CE,
            f"EMA_Cross_Up (5>{13} Vol:{data.volume_relative:.1f}x Candles:{self.candles_since_crossover})",
            min(5, score)
        )
    
    def _generate_bearish_signal(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]: 
        """
        Generate BUY_PE signal after bearish crossover.
        """
        score = 3
        
        # Confirmation: Price below both EMAs
        if data.spot_price < data.ema_5 and data.spot_price < data.ema_13:
            score += 1
        
        # Confirmation: Red candle
        if not data.is_green_candle: 
            score += 1
        
        # Confirmation: RSI supportive (not oversold)
        if 30 < data.rsi < 55:
            score += 1
        
        # Confirmation:  VWAP alignment
        if data. price_below_vwap:
            score += 1
        
        # Confirmation: Trend regime
        if context. regime == MarketRegime.TRENDING_DOWN:
            score += 1
        
        # Strong volume bonus
        if data.volume_relative >= 2.0:
            score += 1
        
        return (
            SignalType.BUY_PE,
            f"EMA_Cross_Down (5<13 Vol:{data. volume_relative:.1f}x Candles:{self.candles_since_crossover})",
            min(5, score)
        )
    
    def get_crossover_state(self) -> dict:
        """Returns current crossover tracking state."""
        return {
            'last_type': self.last_crossover_type,
            'candles_since':  self.candles_since_crossover,
            'is_fresh': self. candles_since_crossover <= self. crossover_freshness
        }


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing EMA Crossover Strategy.. .\n")
    
    class MockConfig:
        class Exit:
            COOLDOWN_SECONDS = 60
            EXITS_BY_REGIME = {'TRENDING': {'target': 15, 'stop': 5}}
    
    from market_intelligence.market_context import MarketContextBuilder, OrderFlowState
    
    strategy = EMACrossoverStrategy(MockConfig())
    
    # Simulate bearish then bullish crossover
    print("Simulating EMA Crossover sequence...")
    
    # Candle 1: EMA5 < EMA13 (bearish alignment)
    data1 = MarketData(
        timestamp=datetime.now(),
        spot_price=24000, future_price=24010,
        future_open=24020, future_high=24030, future_low=23990, future_close=24010,
        vwap=24050, atm_strike=24000,
        rsi=48,
        ema_5=24020,  # Below EMA13
        ema_13=24040,
        ema_21=24060, ema_50=24100,
        adx=28, atr=45,
        candle_body=20, candle_range=40, is_green_candle=False,
        pcr=1.0, ce_oi_change_pct=2.0, pe_oi_change_pct=2.0,
        volume_relative=1.5
    )
    
    context = MarketContextBuilder()\
        .set_regime(MarketRegime.TRENDING_UP, 28, 10)\
        .set_bias(MarketBias.NEUTRAL, 0)\
        .set_time_window(TimeWindow. MORNING_SESSION, 280, False)\
        .build()
    
    signal = strategy.check_entry(data1, context)
    print(f"Candle 1 (EMA5 < EMA13): {signal}")
    print(f"  Crossover State: {strategy.get_crossover_state()}")
    
    # Candle 2: EMA5 > EMA13 (BULLISH CROSSOVER!)
    import time
    time. sleep(0.1)
    
    data2 = MarketData(
        timestamp=datetime.now(),
        spot_price=24080, future_price=24090,
        future_open=24020, future_high=24100, future_low=24010, future_close=24090,
        vwap=24050, atm_strike=24100,
        rsi=58,
        ema_5=24060,  # NOW ABOVE EMA13! 
        ema_13=24050,
        ema_21=24040, ema_50=24000,
        adx=30, atr=50,
        candle_body=60, candle_range=90, is_green_candle=True,
        pcr=1.1, ce_oi_change_pct=3.0, pe_oi_change_pct=2.0,
        volume_relative=1.8  # Good volume
    )
    
    signal = strategy.check_entry(data2, context)
    print(f"\nCandle 2 (EMA5 > EMA13 - CROSSOVER!):")
    print(f"  Crossover State: {strategy.get_crossover_state()}")
    if signal:
        print(f"  Signal: {signal.signal_type.value}")
        print(f"  Reason:  {signal.reason}")
        print(f"  Strength: {signal.strength.value}")
        print(f"  Score: {signal.base_score}")
    
    print("\n✅ EMA Crossover Strategy Test Complete!")