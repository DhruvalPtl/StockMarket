"""
RANGE STRATEGIES
Strategies optimized for ranging/mean-reverting market conditions.

Contains:
- VWAPBounceStrategy: Mean reversion when price crosses VWAP
"""

from typing import Tuple, Optional
from datetime import datetime

import sys
import os
sys.path.append(os.path. dirname(os.path.dirname(os. path.abspath(__file__))))

from strategies.base_strategy import (
    BaseStrategy, SignalType, MarketData, StrategySignal
)
from market_intelligence.market_context import (
    MarketContext, MarketRegime, MarketBias, TimeWindow
)


class VWAPBounceStrategy(BaseStrategy):
    """
    VWAP BOUNCE STRATEGY - Mean Reversion
    
    Focus: Catching price crossing VWAP with RSI support.
    
    Entry Logic:
    - Price CROSSES VWAP (not just above/below)
    - RSI not at extremes (room to move)
    - Expecting continuation after cross
    
    This is a CROSSOVER strategy - needs previous data.
    
    Works best in:  RANGING markets
    Avoid:  Strong TRENDING (will get run over)
    """
    
    STRATEGY_NAME = "VWAP_Bounce"
    STRATEGY_CODE = "VWAP_BOUNCE"
    OPTIMAL_REGIMES = ["RANGING"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "LUNCH_SESSION"]
    
    def __init__(self, config, timeframe:  str = "1minute"):
        super().__init__(config, timeframe)
        self.rsi_oversold = config.RSI. OVERSOLD
        self.rsi_overbought = config. RSI.OVERBOUGHT
    
    def _check_entry_conditions(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]:
        """
        VWAP crossover strategy with RSI filter.
        """
        # Need previous data for crossover detection
        if self.prev_data is None: 
            return SignalType.NO_SIGNAL, "", 0
        
        # Need valid VWAP
        if data.vwap == 0 or self.prev_data. vwap == 0:
            return SignalType.NO_SIGNAL, "", 0
        
        # Detect VWAP crossover
        prev_above_vwap = self.prev_data. future_price > self.prev_data. vwap
        curr_above_vwap = data.future_price > data.vwap
        
        # BUY CE:  Crossed from BELOW to ABOVE VWAP
        if curr_above_vwap and not prev_above_vwap:
            # RSI filter: Not overbought, has room to grow
            if self.rsi_oversold < data.rsi < 70:
                score = 3
                
                # Bonus:  RSI in healthy zone
                if 40 < data.rsi < 60:
                    score += 1
                
                # Bonus: Green candle confirmation
                if data. is_green_candle:
                    score += 1
                
                # Bonus: PCR supportive
                if data.pcr > 1.0:
                    score += 1
                
                return (
                    SignalType.BUY_CE,
                    f"VWAP_Bounce_Up (Cross Above + RSI:{data. rsi:.1f})",
                    min(5, score)
                )
        
        # BUY PE: Crossed from ABOVE to BELOW VWAP
        if not curr_above_vwap and prev_above_vwap:
            # RSI filter: Not oversold, has room to fall
            if 30 < data.rsi < self.rsi_overbought:
                score = 3
                
                # Bonus: RSI in healthy zone
                if 40 < data.rsi < 60:
                    score += 1
                
                # Bonus: Red candle confirmation
                if not data.is_green_candle:
                    score += 1
                
                # Bonus: PCR supportive
                if data. pcr < 1.0:
                    score += 1
                
                return (
                    SignalType.BUY_PE,
                    f"VWAP_Bounce_Down (Cross Below + RSI:{data.rsi:.1f})",
                    min(5, score)
                )
        
        return SignalType.NO_SIGNAL, "", 0


class RangeMeanReversionStrategy(BaseStrategy):
    """
    RANGE MEAN REVERSION STRATEGY
    
    Focus: Trading extremes in ranging markets.
    
    Entry Logic: 
    - Price at range extremes (near support/resistance)
    - RSI at extremes (oversold/overbought)
    - Low ADX (confirming range-bound)
    - Fade the move, expect reversion to mean
    
    Works best in: RANGING markets with clear boundaries
    """
    
    STRATEGY_NAME = "Range_Mean_Reversion"
    STRATEGY_CODE = "RANGE_MEAN_REVERSION"
    OPTIMAL_REGIMES = ["RANGING"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "LUNCH_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe: str = "1minute"):
        super().__init__(config, timeframe)
        self.rsi_oversold = config.RSI. OVERSOLD
        self.rsi_overbought = config.RSI. OVERBOUGHT
    
    def _check_entry_conditions(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]:
        """
        Mean reversion at range extremes. 
        """
        # Must be in ranging regime
        if context.regime != MarketRegime. RANGING:
            return SignalType. NO_SIGNAL, "", 0
        
        # ADX should be low (confirming range)
        if data. adx > 25:
            return SignalType.NO_SIGNAL, "", 0
        
        # BUY CE:  Oversold in range (expect bounce)
        if data.rsi < self.rsi_oversold:
            # Additional confirmations
            score = 2
            
            # Near VWAP or below (room to bounce)
            if data.future_price <= data. vwap * 1.002:
                score += 1
            
            # Near support level
            if context.nearest_support > 0:
                dist_to_support = data.future_price - context.nearest_support
                if dist_to_support < 30:  # Within 30 points of support
                    score += 2
            
            # Bullish divergence hint:  Price making lows but RSI stable
            if data. is_green_candle:   # Reversal candle
                score += 1
            
            if score >= 3:
                return (
                    SignalType. BUY_CE,
                    f"Range_Reversal_Up (RSI:{data.rsi:.1f} ADX:{data.adx:.1f})",
                    min(5, score)
                )
        
        # BUY PE: Overbought in range (expect pullback)
        if data.rsi > self.rsi_overbought: 
            score = 2
            
            # Near VWAP or above
            if data.future_price >= data. vwap * 0.998:
                score += 1
            
            # Near resistance level
            if context. nearest_resistance > 0:
                dist_to_resistance = context.nearest_resistance - data.future_price
                if dist_to_resistance < 30:
                    score += 2
            
            # Reversal candle
            if not data.is_green_candle: 
                score += 1
            
            if score >= 3:
                return (
                    SignalType.BUY_PE,
                    f"Range_Reversal_Down (RSI:{data. rsi:.1f} ADX:{data.adx:.1f})",
                    min(5, score)
                )
        
        return SignalType.NO_SIGNAL, "", 0


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__": 
    print("\n🔬 Testing Range Strategies...\n")
    
    # Mock config
    class MockConfig:
        class Exit:
            COOLDOWN_SECONDS = 60
            EXITS_BY_REGIME = {
                'TRENDING': {'target': 15, 'stop': 5},
                'RANGING':  {'target': 8, 'stop':  8},
            }
        class RSI:
            OVERSOLD = 35
            OVERBOUGHT = 65
    
    from market_intelligence.market_context import MarketContextBuilder, OrderFlowState
    
    # Test VWAP Bounce - simulate crossover
    print("=" * 50)
    print("Testing VWAPBounceStrategy (VWAP Crossover)...")
    
    vwap_bounce = VWAPBounceStrategy(MockConfig())
    
    # First data point:  Below VWAP
    data1 = MarketData(
        timestamp=datetime. now(),
        spot_price=24000,
        future_price=24010,  # Below VWAP
        future_open=24000,
        future_high=24020,
        future_low=23990,
        future_close=24010,
        vwap=24050,  # VWAP above price
        atm_strike=24000,
        rsi=48,
        ema_5=24020,
        ema_13=24030,
        ema_21=24040,
        ema_50=24000,
        adx=18,
        atr=40,
        candle_body=15,
        candle_range=30,
        is_green_candle=True,
        pcr=1.1,
        ce_oi_change_pct=2.0,
        pe_oi_change_pct=3.0,
        volume_relative=1.2
    )
    
    context = MarketContextBuilder()\
        .set_regime(MarketRegime.RANGING, 18, 20)\
        .set_bias(MarketBias.NEUTRAL, 5)\
        .set_time_window(TimeWindow.MORNING_SESSION, 280, False)\
        .build()
    
    # First call (no previous data, no signal)
    signal = vwap_bounce.check_entry(data1, context)
    print(f"First candle (below VWAP): {signal}")
    
    # Second data point:  Crossed above VWAP
    data2 = MarketData(
        timestamp=datetime.now(),
        spot_price=24070,
        future_price=24080,  # Now ABOVE VWAP
        future_open=24020,
        future_high=24090,
        future_low=24010,
        future_close=24080,
        vwap=24050,
        atm_strike=24100,
        rsi=52,
        ema_5=24050,
        ema_13=24040,
        ema_21=24030,
        ema_50=24000,
        adx=18,
        atr=40,
        candle_body=50,
        candle_range=80,
        is_green_candle=True,
        pcr=1.15,
        ce_oi_change_pct=2.5,
        pe_oi_change_pct=3.5,
        volume_relative=1.5
    )
    
    # Need to update timestamp to pass re-entry guard
    import time
    time. sleep(0.1)
    data2.timestamp = datetime.now()
    
    signal = vwap_bounce. check_entry(data2, context)
    if signal:
        print(f"\nSecond candle (crossed above VWAP):")
        print(f"  Signal:  {signal.signal_type.value}")
        print(f"  Reason: {signal.reason}")
        print(f"  Strength: {signal.strength.value}")
        print(f"  Score: {signal. base_score}")
    else:
        print("No signal (check re-entry guard)")
    
    # Test Range Mean Reversion
    print("\n" + "=" * 50)
    print("Testing RangeMeanReversionStrategy (Oversold bounce)...")
    
    mean_reversion = RangeMeanReversionStrategy(MockConfig())
    
    # Oversold data
    data_oversold = MarketData(
        timestamp=datetime.now(),
        spot_price=23950,
        future_price=23960,
        future_open=24000,
        future_high=24010,
        future_low=23940,
        future_close=23960,
        vwap=24050,
        atm_strike=24000,
        rsi=28,  # Oversold! 
        ema_5=23980,
        ema_13=24000,
        ema_21=24020,
        ema_50=24050,
        adx=15,  # Low ADX = ranging
        atr=45,
        candle_body=30,
        candle_range=70,
        is_green_candle=True,  # Reversal candle
        pcr=1.2,
        ce_oi_change_pct=1.0,
        pe_oi_change_pct=4.0,
        volume_relative=1.3
    )
    
    context_range = MarketContextBuilder()\
        .set_regime(MarketRegime. RANGING, 15, 25)\
        .set_bias(MarketBias.NEUTRAL, -10)\
        .set_time_window(TimeWindow.LUNCH_SESSION, 200, False)\
        .set_key_levels([], 23900, 24200, 24000, 24000)\
        .build()
    
    signal = mean_reversion. check_entry(data_oversold, context_range)
    if signal:
        print(f"Signal: {signal.signal_type.value}")
        print(f"Reason: {signal.reason}")
        print(f"Strength: {signal.strength.value}")
    else: 
        print("No signal generated")
    
    print("\n✅ Range Strategies Test Complete!")