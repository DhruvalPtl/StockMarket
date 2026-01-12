"""
TREND STRATEGIES
Strategies optimized for trending market conditions.

Contains:
- OriginalStrategy:  Hybrid early/full market approach
- VWAPEMATrendStrategy: Trend following with VWAP + EMA
- MomentumBreakoutStrategy:  Catches strong momentum moves
"""

from typing import Tuple, Optional
from datetime import datetime, time

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.base_strategy import (
    BaseStrategy, SignalType, MarketData, StrategySignal
)
from market_intelligence.market_context import (
    MarketContext, MarketRegime, MarketBias, TimeWindow
)


class OriginalStrategy(BaseStrategy):
    """
    ORIGINAL STRATEGY - Hybrid Approach
    
    Early Market (< 10: 00 AM):
    - Uses Market Bias (Price vs VWAP + PCR)
    - Simpler logic for volatile opening
    
    Full Market (> 10:00 AM):
    - Uses EMA Crossover + RSI + VWAP
    - More confirmations required
    
    Works in:  TRENDING, RANGING (adapts based on time)
    """
    
    STRATEGY_NAME = "Original"
    STRATEGY_CODE = "ORIGINAL"
    OPTIMAL_REGIMES = ["TRENDING", "RANGING"]
    ACTIVE_TIME_WINDOWS = ["OPENING_SESSION", "MORNING_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe:  str = "1minute"):
        super().__init__(config, timeframe)
        self.early_mode_cutoff = time(10, 0)  # Switch at 10:00 AM
    
    def _check_entry_conditions(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]:
        """
        Original strategy logic with early/full market modes.
        """
        current_time = datetime.now().time()
        
        # Determine mode
        if current_time < self.early_mode_cutoff:
            return self._early_market_logic(data, context)
        else: 
            return self._full_market_logic(data, context)
    
    def _early_market_logic(self, data:  MarketData, context: MarketContext) -> Tuple[SignalType, str, int]: 
        """
        Early market (9:15 - 10:00): Simplified bias-based approach.
        Uses VWAP + PCR + Candle pattern.
        """
        # Safety check
        if data.vwap == 0 or data.future_price == 0:
            return SignalType.NO_SIGNAL, "", 0
        
        # Calculate bullish score
        bullish_score = 0
        bearish_score = 0
        
        # Factor 1: Price vs VWAP (weight:  2)
        if data.price_above_vwap: 
            bullish_score += 2
        else:
            bearish_score += 2
        
        # Factor 2: PCR (weight: 1)
        if data.pcr > 1.1:
            bullish_score += 1  # High put writing = support
        elif data.pcr < 0.9:
            bearish_score += 1  # High call writing = resistance
        
        # Factor 3: Candle color (weight: 1)
        if data.is_green_candle:
            bullish_score += 1
        else:
            bearish_score += 1
        
        # Factor 4: Bias alignment (weight: 1)
        if context.bias in [MarketBias.BULLISH, MarketBias.STRONG_BULLISH]: 
            bullish_score += 1
        elif context.bias in [MarketBias.BEARISH, MarketBias.STRONG_BEARISH]:
            bearish_score += 1
        
        # Generate signal if score >= 3
        if bullish_score >= 3 and bullish_score > bearish_score: 
            return (
                SignalType.BUY_CE,
                f"Early_Bullish (Score:{bullish_score} VWAP+PCR:{data.pcr:.2f})",
                min(5, bullish_score)
            )
        elif bearish_score >= 3 and bearish_score > bullish_score: 
            return (
                SignalType.BUY_PE,
                f"Early_Bearish (Score:{bearish_score} VWAP+PCR:{data.pcr:.2f})",
                min(5, bearish_score)
            )
        
        return SignalType.NO_SIGNAL, "", 0
    
    def _full_market_logic(self, data:  MarketData, context: MarketContext) -> Tuple[SignalType, str, int]:
        """
        Full market (10:00+): EMA Crossover + RSI + VWAP confirmation.
        More confirmations required for higher accuracy.
        """
        # Need valid VWAP
        if data.vwap == 0:
            return SignalType.NO_SIGNAL, "", 0
        
        # BUY CE conditions: 
        # 1.Futures > VWAP
        # 2.EMA bullish (5 > 13)
        # 3.RSI in bullish momentum zone (55-75)
        # 4.Price above EMA5
        if (data.price_above_vwap and 
            data.ema_5 > data.ema_13 and 
            data.rsi_bullish_momentum and
            data.price_above_ema5):
            
            score = 3
            if data.ema_bullish:  # Full EMA alignment
                score += 1
            if data.strong_candle and data.is_green_candle: 
                score += 1
            
            return (
                SignalType.BUY_CE,
                f"Full_Bullish (EMA Cross + RSI:{data.rsi:.1f} + VWAP)",
                score
            )
        
        # BUY PE conditions:
        # 1.Futures < VWAP
        # 2.EMA bearish (5 < 13)
        # 3.RSI in bearish momentum zone (25-45)
        # 4.Price below EMA5
        if (data.price_below_vwap and 
            data.ema_5 < data.ema_13 and 
            data.rsi_bearish_momentum and
            data.price_below_ema5):
            
            score = 3
            if data.ema_bearish:  # Full EMA alignment
                score += 1
            if data.strong_candle and not data.is_green_candle: 
                score += 1
            
            return (
                SignalType.BUY_PE,
                f"Full_Bearish (EMA Cross + RSI:{data.rsi:.1f} + VWAP)",
                score
            )
        
        return SignalType.NO_SIGNAL, "", 0


class VWAPEMATrendStrategy(BaseStrategy):
    """
    VWAP + EMA TREND STRATEGY
    
    Focus:  Capturing sustainable trends confirmed by multiple indicators.
    
    Entry Logic:
    - Price above/below VWAP (institutional bias)
    - EMA alignment confirms trend (5 > 13 > 21 for bullish)
    - Price respecting fast EMA (bouncing off it)
    
    Works best in: TRENDING markets
    Avoid:  RANGING, VOLATILE
    """
    
    STRATEGY_NAME = "VWAP_EMA_Trend"
    STRATEGY_CODE = "VWAP_EMA_TREND"
    OPTIMAL_REGIMES = ["TRENDING"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "POWER_HOUR"]
    
    def _check_entry_conditions(self, data:  MarketData, context: MarketContext) -> Tuple[SignalType, str, int]:
        """
        Trend following with VWAP + EMA alignment.
        """
        # Need valid data
        if data.vwap == 0 or data.ema_5 == 0:
            return SignalType.NO_SIGNAL, "", 0
        
        # Additional regime check (be strict about trending)
        if context.regime not in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            return SignalType.NO_SIGNAL, "", 0
        
        # BUY CE:  Uptrend confirmation
        # 1.Price > VWAP (above institutional average)
        # 2.EMA 5 > EMA 13 (short-term uptrend)
        # 3.Price > EMA 5 (momentum intact)
        # 4.ADX > 25 (trend strength)
        if (data.price_above_vwap and 
            data.ema_5 > data.ema_13 and 
            data.price_above_ema5 and
            data.adx > 25):
            
            score = 3
            
            # Bonus: Full EMA alignment
            if data.ema_bullish: 
                score += 1
            
            # Bonus: Strong trend
            if data.adx > 35:
                score += 1
            
            # Bonus: RSI confirmation
            if data.rsi_bullish_momentum:
                score += 1
            
            return (
                SignalType.BUY_CE,
                f"Trend_Up (VWAP+ EMA+ ADX:{data.adx:.1f})",
                min(5, score)
            )
        
        # BUY PE: Downtrend confirmation
        if (data.price_below_vwap and 
            data.ema_5 < data.ema_13 and 
            data.price_below_ema5 and
            data.adx > 25):
            
            score = 3
            
            if data.ema_bearish:
                score += 1
            if data.adx > 35:
                score += 1
            if data.rsi_bearish_momentum:
                score += 1
            
            return (
                SignalType.BUY_PE,
                f"Trend_Down (VWAP+ EMA+ ADX:{data.adx:.1f})",
                min(5, score)
            )
        
        return SignalType.NO_SIGNAL, "", 0


class MomentumBreakoutStrategy(BaseStrategy):
    """
    MOMENTUM BREAKOUT STRATEGY
    
    Focus: Catching strong momentum moves with large candle bodies.
    
    Entry Logic:
    - Price away from VWAP (directional conviction)
    - Large candle body (strong move, not indecision)
    - RSI in momentum zone (not oversold/overbought)
    - Volume confirmation (institutional participation)
    
    Works best in:  TRENDING, VOLATILE
    Avoid:  RANGING (will get chopped)
    """
    
    STRATEGY_NAME = "Momentum_Breakout"
    STRATEGY_CODE = "MOMENTUM_BREAKOUT"
    OPTIMAL_REGIMES = ["TRENDING", "VOLATILE"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe: str = "1minute"):
        super().__init__(config, timeframe)
        self.min_candle_body = config.Patterns.MIN_CANDLE_BODY
    
    def _check_entry_conditions(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]:
        """
        Momentum-based entries with candle pattern confirmation.
        """
        # BUY CE:  Bullish momentum
        # 1.Price > VWAP (bullish bias)
        # 2.Green candle with large body
        # 3.RSI in bullish momentum zone (55-75)
        # 4.Volume confirmation (relative volume > 1.5)
        if (data.price_above_vwap and 
            data.is_green_candle and
            data.candle_body >= self.min_candle_body):
            
            # RSI check
            if not (55 <= data.rsi <= 75):
                return SignalType.NO_SIGNAL, "", 0
            
            score = 3
            
            # Bonus: Strong candle
            if data.strong_candle: 
                score += 1
            
            # Bonus: Volume spike
            if data.volume_relative >= 1.5:
                score += 1
            
            # Bonus: Regime alignment
            if context.regime == MarketRegime.TRENDING_UP: 
                score += 1
            
            return (
                SignalType.BUY_CE,
                f"Momentum_Up (Body:{data.candle_body:.1f} RSI:{data.rsi:.1f} Vol:{data.volume_relative:.1f}x)",
                min(5, score)
            )
        
        # BUY PE: Bearish momentum
        if (data.price_below_vwap and 
            not data.is_green_candle and
            data.candle_body >= self.min_candle_body):
            
            # RSI check
            if not (25 <= data.rsi <= 45):
                return SignalType.NO_SIGNAL, "", 0
            
            score = 3
            
            if data.strong_candle:
                score += 1
            if data.volume_relative >= 1.5:
                score += 1
            if context.regime == MarketRegime.TRENDING_DOWN:
                score += 1
            
            return (
                SignalType.BUY_PE,
                f"Momentum_Down (Body:{data.candle_body:.1f} RSI:{data.rsi:.1f} Vol:{data.volume_relative:.1f}x)",
                min(5, score)
            )
        
        return SignalType.NO_SIGNAL, "", 0


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing Trend Strategies...\n")
    
    # Mock config
    class MockConfig:
        class Exit:
            COOLDOWN_SECONDS = 60
            EXITS_BY_REGIME = {
                'TRENDING': {'target': 15, 'stop': 5},
                'RANGING': {'target':  8, 'stop': 8},
            }
        class Patterns:
            MIN_CANDLE_BODY = 10
    
    from market_intelligence.market_context import MarketContextBuilder, OrderFlowState
    
    # Create bullish market data
    data = MarketData(
        timestamp=datetime.now(),
        spot_price=24100,
        future_price=24150,
        future_open=24050,
        future_high=24180,
        future_low=24040,
        future_close=24150,
        vwap=24050,
        atm_strike=24100,
        rsi=62,
        ema_5=24080,
        ema_13=24050,
        ema_21=24020,
        ema_50=23950,
        adx=32,
        atr=50,
        candle_body=80,
        candle_range=120,
        is_green_candle=True,
        pcr=1.15,
        ce_oi_change_pct=3.0,
        pe_oi_change_pct=5.0,
        volume_relative=1.8
    )
    
    context = MarketContextBuilder()\
        .set_regime(MarketRegime.TRENDING_UP, 32, 15)\
        .set_bias(MarketBias.BULLISH, 50)\
        .set_time_window(TimeWindow.MORNING_SESSION, 280, False)\
        .set_order_flow(OrderFlowState(smart_money_direction="BULLISH"))\
        .build()
    
    # Test Original Strategy
    print("=" * 50)
    print("Testing OriginalStrategy...")
    original = OriginalStrategy(MockConfig())
    signal = original.check_entry(data, context)
    if signal:
        print(f"Signal: {signal.signal_type.value}")
        print(f"Reason: {signal.reason}")
        print(f"Strength: {signal.strength.value}")
        print(f"Score: {signal.base_score}")
        print(f"Confluence: {signal.confluence_factors}")
    else:
        print("No signal generated")
    
    # Test VWAP EMA Trend Strategy
    print("\n" + "=" * 50)
    print("Testing VWAPEMATrendStrategy...")
    vwap_ema = VWAPEMATrendStrategy(MockConfig())
    signal = vwap_ema.check_entry(data, context)
    if signal:
        print(f"Signal: {signal.signal_type.value}")
        print(f"Reason: {signal.reason}")
        print(f"Strength: {signal.strength.value}")
    else:
        print("No signal generated")
    
    # Test Momentum Breakout Strategy
    print("\n" + "=" * 50)
    print("Testing MomentumBreakoutStrategy...")
    momentum = MomentumBreakoutStrategy(MockConfig())
    signal = momentum.check_entry(data, context)
    if signal:
        print(f"Signal: {signal.signal_type.value}")
        print(f"Reason: {signal.reason}")
        print(f"Strength: {signal.strength.value}")
    else:
        print("No signal generated")
    
    print("\n✅ Trend Strategies Test Complete!")