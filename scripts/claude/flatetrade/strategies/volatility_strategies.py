"""
VOLATILITY STRATEGIES
Strategies that capitalize on volatility expansion.

Contains:
- VolatilitySpikeStrategy: Enters when IV spikes (big move expected)
- OpeningRangeBreakoutStrategy:  Captures opening session momentum
"""

from typing import Tuple, Optional
from datetime import datetime, time
from collections import deque

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.base_strategy import (
    BaseStrategy, SignalType, MarketData, StrategySignal
)
from market_intelligence.market_context import (
    MarketContext, MarketRegime, MarketBias, TimeWindow, VolatilityState
)


class VolatilitySpikeStrategy(BaseStrategy):
    """
    VOLATILITY SPIKE STRATEGY
    
    Focus: Entering when IV (Implied Volatility) spikes.
    
    Theory:
    - IV spike = Market expects big move
    - If we can determine direction, we profit from the move
    - Use price action + bias to determine direction
    
    Entry Logic:
    1.IV percentile > 70 (volatility expanding)
    2.ATR spiking (confirming volatility)
    3.Clear directional bias (to pick CE or PE)
    4.Volume confirmation (institutional activity)
    
    Works best in: VOLATILE markets, NEWS events
    """
    
    STRATEGY_NAME = "Volatility_Spike"
    STRATEGY_CODE = "VOLATILITY_SPIKE"
    OPTIMAL_REGIMES = ["VOLATILE", "TRENDING"]
    ACTIVE_TIME_WINDOWS = ["OPENING_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe:  str = "1minute"):
        super().__init__(config, timeframe)
        
        # IV tracking
        self.iv_history: deque = deque(maxlen=50)
        
        # ATR tracking
        self.atr_history: deque = deque(maxlen=20)
        
        # Thresholds
        self.iv_spike_percentile = 70  # IV must be in top 30%
        self.atr_spike_multiplier = 1.5  # ATR 1.5x average
        self.min_volume_ratio = 1.5
    
    def _check_entry_conditions(self, data:  MarketData, context: MarketContext) -> Tuple[SignalType, str, int]:
        """
        Detects volatility spikes and enters in direction of bias.
        """
        # Track ATR
        self.atr_history.append(data.atr)
        
        # Need enough history
        if len(self.atr_history) < 10:
            return SignalType.NO_SIGNAL, "", 0
        
        # Check for volatility spike
        if not self._is_volatility_spiking(data, context):
            return SignalType.NO_SIGNAL, "", 0
        
        # Volume confirmation
        if data.volume_relative < self.min_volume_ratio:
            return SignalType.NO_SIGNAL, "", 0
        
        # Determine direction from context
        direction = self._determine_direction(data, context)
        
        if direction == 'BULLISH':
            return self._generate_bullish_signal(data, context)
        elif direction == 'BEARISH':
            return self._generate_bearish_signal(data, context)
        
        return SignalType.NO_SIGNAL, "", 0
    
    def _is_volatility_spiking(self, data: MarketData, context: MarketContext) -> bool:
        """
        Check if volatility is spiking.
        Uses ATR and context IV percentile.
        """
        # Check ATR spike
        avg_atr = sum(self.atr_history) / len(self.atr_history)
        if data.atr < avg_atr * self.atr_spike_multiplier: 
            return False
        
        # Check context volatility state
        if context.volatility_state not in [VolatilityState.HIGH, VolatilityState.EXTREME]:
            # Also check ATR percentile from context
            if context.atr_percentile < self.iv_spike_percentile: 
                return False
        
        return True
    
    def _determine_direction(self, data: MarketData, context: MarketContext) -> str:
        """
        Determine trade direction from multiple factors.
        """
        bullish_score = 0
        bearish_score = 0
        
        # 1.Context bias
        if context.bias in [MarketBias.STRONG_BULLISH, MarketBias.BULLISH]:
            bullish_score += 2
        elif context.bias in [MarketBias.STRONG_BEARISH, MarketBias.BEARISH]: 
            bearish_score += 2
        
        # 2.Price vs VWAP
        if data.price_above_vwap: 
            bullish_score += 1
        else:
            bearish_score += 1
        
        # 3.Candle direction
        if data.is_green_candle and data.strong_candle: 
            bullish_score += 2
        elif not data.is_green_candle and data.strong_candle:
            bearish_score += 2
        
        # 4.EMA alignment
        if data.ema_bullish: 
            bullish_score += 1
        elif data.ema_bearish: 
            bearish_score += 1
        
        # 5.Order flow
        if context.order_flow.smart_money_direction == "BULLISH": 
            bullish_score += 1
        elif context.order_flow.smart_money_direction == "BEARISH":
            bearish_score += 1
        
        # Decide
        if bullish_score >= 4 and bullish_score > bearish_score + 1:
            return 'BULLISH'
        elif bearish_score >= 4 and bearish_score > bullish_score + 1:
            return 'BEARISH'
        
        return 'NEUTRAL'
    
    def _generate_bullish_signal(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]: 
        """Generate bullish signal on volatility spike."""
        score = 4  # Base score for vol spike
        
        if context.regime == MarketRegime.TRENDING_UP:
            score += 1
        if data.volume_relative >= 2.0:
            score += 1
        
        avg_atr = sum(self.atr_history) / len(self.atr_history)
        atr_ratio = data.atr / avg_atr
        
        return (
            SignalType.BUY_CE,
            f"Vol_Spike_Up (ATR:{atr_ratio:.1f}x IV:{context.iv_percentile:.0f}%)",
            min(5, score)
        )
    
    def _generate_bearish_signal(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]: 
        """Generate bearish signal on volatility spike."""
        score = 4
        
        if context.regime == MarketRegime.TRENDING_DOWN:
            score += 1
        if data.volume_relative >= 2.0:
            score += 1
        
        avg_atr = sum(self.atr_history) / len(self.atr_history)
        atr_ratio = data.atr / avg_atr
        
        return (
            SignalType.BUY_PE,
            f"Vol_Spike_Down (ATR:{atr_ratio:.1f}x IV:{context.iv_percentile:.0f}%)",
            min(5, score)
        )


class OpeningRangeBreakoutStrategy(BaseStrategy):
    """
    OPENING RANGE BREAKOUT (ORB) STRATEGY
    
    Focus: Capturing the first major move of the day.
    
    Theory:
    - First 15-30 minutes establish the "opening range"
    - Breakout from this range often leads to sustained move
    - Volume on breakout confirms institutional participation
    
    Entry Logic:
    1.Wait for opening range to form (first 15 candles)
    2.Price breaks above/below range with volume
    3.Enter in breakout direction
    4.Use range as stop loss reference
    
    ONLY active during:  9:30 - 10:30 (after range forms)
    """
    
    STRATEGY_NAME = "Opening_Range_Breakout"
    STRATEGY_CODE = "OPENING_RANGE_BREAKOUT"
    OPTIMAL_REGIMES = ["TRENDING", "VOLATILE"]
    ACTIVE_TIME_WINDOWS = ["OPENING_SESSION", "MORNING_SESSION"]
    
    def __init__(self, config, timeframe: str = "1minute"):
        super().__init__(config, timeframe)
        
        # ORB settings
        self.orb_formation_candles = 15  # First 15 minutes
        self.min_breakout_points = 10  # Minimum breakout distance
        self.min_volume_ratio = 1.5
        
        # State
        self.breakout_traded_today = False
        self.last_trade_date:  Optional[datetime] = None
    
    def _check_entry_conditions(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]:
        """
        Checks for opening range breakout.
        """
        # Reset daily state
        today = datetime.now().date()
        if self.last_trade_date != today:
            self.breakout_traded_today = False
            self.last_trade_date = today
        
        # Only trade one ORB per day
        if self.breakout_traded_today:
            return SignalType.NO_SIGNAL, "", 0
        
        # Need opening range to be set
        if not context.opening_range_set:
            return SignalType.NO_SIGNAL, "", 0
        
        or_high = context.opening_range_high
        or_low = context.opening_range_low
        or_range = or_high - or_low
        
        # Range should be meaningful (not too tight)
        if or_range < 20:
            return SignalType.NO_SIGNAL, "", 0
        
        # Check time window (only after 9:45, before 10:30)
        now = datetime.now().time()
        if now < time(9, 45) or now > time(10, 30):
            return SignalType.NO_SIGNAL, "", 0
        
        # Check for breakout
        breakout_above = data.future_close > or_high + self.min_breakout_points
        breakout_below = data.future_close < or_low - self.min_breakout_points
        
        # Volume confirmation
        if data.volume_relative < self.min_volume_ratio: 
            return SignalType.NO_SIGNAL, "", 0
        
        # Bullish breakout
        if breakout_above: 
            # Confirm with candle
            if not data.is_green_candle: 
                return SignalType.NO_SIGNAL, "", 0
            
            self.breakout_traded_today = True
            
            score = 4
            if data.strong_candle: 
                score += 1
            if context.bias in [MarketBias.BULLISH, MarketBias.STRONG_BULLISH]: 
                score += 1
            
            return (
                SignalType.BUY_CE,
                f"ORB_Up (Range:{or_low:.0f}-{or_high:.0f} Break:{data.future_close:.0f})",
                min(5, score)
            )
        
        # Bearish breakout
        if breakout_below: 
            if data.is_green_candle:
                return SignalType.NO_SIGNAL, "", 0
            
            self.breakout_traded_today = True
            
            score = 4
            if data.strong_candle:
                score += 1
            if context.bias in [MarketBias.BEARISH, MarketBias.STRONG_BEARISH]:
                score += 1
            
            return (
                SignalType.BUY_PE,
                f"ORB_Down (Range:{or_low:.0f}-{or_high:.0f} Break:{data.future_close:.0f})",
                min(5, score)
            )
        
        return SignalType.NO_SIGNAL, "", 0


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__": 
    print("\n🔬 Testing Volatility Strategies...\n")
    
    class MockConfig:
        class Exit:
            COOLDOWN_SECONDS = 60
            EXITS_BY_REGIME = {'VOLATILE': {'target': 20, 'stop':  10}}
    
    from market_intelligence.market_context import MarketContextBuilder, OrderFlowState
    
    # Test Volatility Spike Strategy
    print("=" * 50)
    print("Testing VolatilitySpikeStrategy...")
    
    vol_strategy = VolatilitySpikeStrategy(MockConfig())
    
    # Build up ATR history with normal values
    for i in range(15):
        normal_data = MarketData(
            timestamp=datetime.now(),
            spot_price=24000, future_price=24010,
            future_open=24000, future_high=24020, future_low=23990, future_close=24010,
            vwap=24000, atm_strike=24000,
            rsi=50, ema_5=24000, ema_13=24000, ema_21=24000, ema_50=24000,
            adx=20, atr=40,  # Normal ATR
            candle_body=15, candle_range=30, is_green_candle=True,
            pcr=1.0, ce_oi_change_pct=1.0, pe_oi_change_pct=1.0,
            volume_relative=1.0
        )
        context = MarketContextBuilder()\
            .set_volatility(VolatilityState.NORMAL, 40, 50, 50)\
            .set_time_window(TimeWindow.MORNING_SESSION, 280, False)\
            .build()
        vol_strategy.check_entry(normal_data, context)
    
    # Now simulate volatility spike
    spike_data = MarketData(
        timestamp=datetime.now(),
        spot_price=24100, future_price=24120,
        future_open=24000, future_high=24150, future_low=23980, future_close=24120,
        vwap=24050, atm_strike=24100,
        rsi=65,
        ema_5=24080, ema_13=24060, ema_21=24040, ema_50=24000,
        adx=35, atr=80,  # SPIKE!  2x normal
        candle_body=100, candle_range=170, is_green_candle=True,
        pcr=1.15, ce_oi_change_pct=5.0, pe_oi_change_pct=3.0,
        volume_relative=2.5  # High volume
    )
    
    spike_context = MarketContextBuilder()\
        .set_regime(MarketRegime.VOLATILE, 35, 5)\
        .set_bias(MarketBias.BULLISH, 40)\
        .set_volatility(VolatilityState.HIGH, 80, 85, 80)\
        .set_time_window(TimeWindow.MORNING_SESSION, 280, False)\
        .set_order_flow(OrderFlowState(smart_money_direction="BULLISH"))\
        .build()
    
    signal = vol_strategy.check_entry(spike_data, spike_context)
    
    if signal: 
        print(f"Signal: {signal.signal_type.value}")
        print(f"Reason: {signal.reason}")
        print(f"Strength: {signal.strength.value}")
        print(f"Score: {signal.base_score}")
    else: 
        print("No signal")
    
    # Test Opening Range Breakout
    print("\n" + "=" * 50)
    print("Testing OpeningRangeBreakoutStrategy...")
    
    orb_strategy = OpeningRangeBreakoutStrategy(MockConfig())
    
    # Context with opening range set
    orb_context = MarketContextBuilder()\
        .set_regime(MarketRegime.TRENDING_UP, 28, 10)\
        .set_bias(MarketBias.BULLISH, 35)\
        .set_time_window(TimeWindow.MORNING_SESSION, 280, False)\
        .set_opening_range(24120, 24020, True)\
        .build()
    
    # Simulate breakout above range
    breakout_data = MarketData(
        timestamp=datetime.now(),
        spot_price=24140, future_price=24145,
        future_open=24110, future_high=24160, future_low=24100, future_close=24145,
        vwap=24080, atm_strike=24100,
        rsi=62,
        ema_5=24100, ema_13=24080, ema_21=24060, ema_50=24000,
        adx=30, atr=55,
        candle_body=35, candle_range=60, is_green_candle=True,
        pcr=1.1, ce_oi_change_pct=4.0, pe_oi_change_pct=2.0,
        volume_relative=2.0  # Strong volume on breakout
    )
    
    signal = orb_strategy.check_entry(breakout_data, orb_context)
    
    if signal:
        print(f"Signal:  {signal.signal_type.value}")
        print(f"Reason: {signal.reason}")
        print(f"Strength: {signal.strength.value}")
    else:
        print("No signal (check time window - must be 9:45-10:30)")
    
    print("\n✅ Volatility Strategies Test Complete!")