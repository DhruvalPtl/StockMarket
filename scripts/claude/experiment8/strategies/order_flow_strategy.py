"""
ORDER FLOW STRATEGY
Trades based on OI changes and institutional positioning.

Key Insight: 
- Option WRITERS (market makers) are usually right
- If CE OI is increasing rapidly -> Resistance forming -> BEARISH
- If PE OI is increasing rapidly -> Support forming -> BULLISH
- We trade WITH the writers (contrarian to retail buyers)

This strategy uses:
- OI delta (change in OI)
- PCR changes
- OI-Price relationship (buildup analysis)
"""

from typing import Tuple, Optional
from datetime import datetime
from collections import deque

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.base_strategy import (
    BaseStrategy, SignalType, MarketData, StrategySignal
)
from market_intelligence.market_context import (
    MarketContext, MarketRegime, MarketBias, TimeWindow
)


class OrderFlowStrategy(BaseStrategy):
    """
    ORDER FLOW STRATEGY
    
    Focus: Trading based on OI changes and smart money positioning.
    
    Theory:
    - Option writers (institutions) create support/resistance with OI
    - Rapid CE OI increase = Resistance = BEARISH signal
    - Rapid PE OI increase = Support = BULLISH signal
    - We're trading WITH the writers, not against them
    
    Entry Logic:
    1.Significant OI change in one direction (>5%)
    2.OI-Price relationship confirms (buildup type)
    3.PCR supports the direction
    4.Price action confirmation
    
    Works in:  TRENDING, RANGING (smart money always active)
    """
    
    STRATEGY_NAME = "Order_Flow"
    STRATEGY_CODE = "ORDER_FLOW"
    OPTIMAL_REGIMES = ["TRENDING", "RANGING"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "LUNCH_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe: str = "1minute"):
        super().__init__(config, timeframe)
        
        # OI tracking
        self.ce_oi_history:  deque = deque(maxlen=20)
        self.pe_oi_history:  deque = deque(maxlen=20)
        self.pcr_history: deque = deque(maxlen=20)
        
        # Thresholds
        self.oi_change_threshold = 5.0  # 5% OI change is significant
        self.pcr_bullish = 1.15  # PCR > 1.15 is bullish
        self.pcr_bearish = 0.85  # PCR < 0.85 is bearish
    
    def _check_entry_conditions(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]:
        """
        Analyzes order flow and generates signals.
        """
        # Track PCR
        self.pcr_history.append(data.pcr)
        
        # Get order flow state from context
        of = context.order_flow
        
        # Check for significant OI imbalance
        signal = self._check_oi_imbalance(data, context, of)
        if signal[0] != SignalType.NO_SIGNAL: 
            return signal
        
        # Check OI-Price relationship (buildup analysis)
        signal = self._check_buildup_signal(data, context, of)
        if signal[0] != SignalType.NO_SIGNAL: 
            return signal
        
        return SignalType.NO_SIGNAL, "", 0
    
    def _check_oi_imbalance(self, data: MarketData, context: MarketContext, of) -> Tuple[SignalType, str, int]:
        """
        Check for significant OI imbalance between CE and PE.
        
        Logic:
        - If PE OI increasing much faster than CE OI -> Support building -> BULLISH
        - If CE OI increasing much faster than PE OI -> Resistance building -> BEARISH
        """
        ce_change = of.ce_oi_change_pct
        pe_change = of.pe_oi_change_pct
        
        # Calculate imbalance
        imbalance = pe_change - ce_change
        
        # BULLISH:  PE writers much more active (creating support)
        if imbalance > self.oi_change_threshold:
            # Confirm with PCR
            if data.pcr > self.pcr_bullish:
                score = 3
                
                # Price confirmation
                if data.price_above_vwap: 
                    score += 1
                if data.is_green_candle: 
                    score += 1
                if of.smart_money_direction == "BULLISH":
                    score += 1
                
                return (
                    SignalType.BUY_CE,
                    f"OI_Bullish (PE+{pe_change:.1f}% CE+{ce_change:.1f}% PCR:{data.pcr:.2f})",
                    min(5, score)
                )
        
        # BEARISH: CE writers much more active (creating resistance)
        if imbalance < -self.oi_change_threshold: 
            if data.pcr < self.pcr_bearish:
                score = 3
                
                if data.price_below_vwap: 
                    score += 1
                if not data.is_green_candle: 
                    score += 1
                if of.smart_money_direction == "BEARISH":
                    score += 1
                
                return (
                    SignalType.BUY_PE,
                    f"OI_Bearish (CE+{ce_change:.1f}% PE+{pe_change:.1f}% PCR:{data.pcr:.2f})",
                    min(5, score)
                )
        
        return SignalType.NO_SIGNAL, "", 0
    
    def _check_buildup_signal(self, data: MarketData, context: MarketContext, of) -> Tuple[SignalType, str, int]:
        """
        Check OI-Price relationship for buildup signals.
        
        Buildup Types:
        - LONG_BUILDUP: Price ↑ + OI ↑ -> Strong bullish (continue)
        - SHORT_BUILDUP:  Price ↓ + OI ↑ -> Strong bearish (continue)
        - SHORT_COVERING: Price ↑ + OI ↓ -> Weak bullish (shorts exiting)
        - LONG_UNWINDING: Price ↓ + OI ↓ -> Weak bearish (longs exiting)
        """
        oi_signal = of.oi_signal
        
        # LONG BUILDUP:  Strong bullish continuation
        if oi_signal == "LONG_BUILDUP":
            # This is a strong trend signal
            if context.regime == MarketRegime.TRENDING_UP:
                score = 4
                
                if data.price_above_vwap:
                    score += 1
                if data.rsi_bullish_momentum: 
                    score += 1
                
                return (
                    SignalType.BUY_CE,
                    f"Long_Buildup (Price↑ OI↑ RSI:{data.rsi:.1f})",
                    min(5, score)
                )
        
        # SHORT BUILDUP:  Strong bearish continuation
        elif oi_signal == "SHORT_BUILDUP": 
            if context.regime == MarketRegime.TRENDING_DOWN: 
                score = 4
                
                if data.price_below_vwap: 
                    score += 1
                if data.rsi_bearish_momentum: 
                    score += 1
                
                return (
                    SignalType.BUY_PE,
                    f"Short_Buildup (Price↓ OI↑ RSI:{data.rsi:.1f})",
                    min(5, score)
                )
        
        # SHORT COVERING: Weak bullish (can trade if other confirmations)
        elif oi_signal == "SHORT_COVERING":
            # Shorts exiting = price going up, but weaker signal
            if data.price_above_vwap and data.is_green_candle:
                if context.bias in [MarketBias.BULLISH, MarketBias.STRONG_BULLISH]: 
                    return (
                        SignalType.BUY_CE,
                        f"Short_Covering (Price↑ OI↓ Bias:{context.bias.value})",
                        3  # Lower score - weaker signal
                    )
        
        # LONG UNWINDING: Weak bearish
        elif oi_signal == "LONG_UNWINDING": 
            if data.price_below_vwap and not data.is_green_candle: 
                if context.bias in [MarketBias.BEARISH, MarketBias.STRONG_BEARISH]:
                    return (
                        SignalType.BUY_PE,
                        f"Long_Unwinding (Price↓ OI↓ Bias:{context.bias.value})",
                        3
                    )
        
        return SignalType.NO_SIGNAL, "", 0
    
    def get_oi_analysis(self) -> dict:
        """Returns current OI analysis state."""
        avg_pcr = sum(self.pcr_history) / len(self.pcr_history) if self.pcr_history else 1.0
        return {
            'avg_pcr': avg_pcr,
            'pcr_trend': 'RISING' if len(self.pcr_history) > 2 and self.pcr_history[-1] > self.pcr_history[-2] else 'FALLING'
        }


class PCRExtremeStrategy(BaseStrategy):
    """
    PCR EXTREME STRATEGY
    
    Focus: Trading PCR extremes (contrarian).
    
    Theory:
    - Extreme high PCR (>1.5): Too many puts = Retail bearish = Market will rise
    - Extreme low PCR (<0.5): Too many calls = Retail bullish = Market will fall
    
    This is a CONTRARIAN strategy against retail sentiment.
    
    Works best in:  RANGING markets (mean reversion)
    """
    
    STRATEGY_NAME = "PCR_Extreme"
    STRATEGY_CODE = "PCR_EXTREME"
    OPTIMAL_REGIMES = ["RANGING"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "LUNCH_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe: str = "1minute"):
        super().__init__(config, timeframe)
        
        # PCR extremes
        self.pcr_extreme_high = 1.4  # Extreme bearish sentiment
        self.pcr_extreme_low = 0.6   # Extreme bullish sentiment
        
        # Track PCR for changes
        self.pcr_history: deque = deque(maxlen=30)
    
    def _check_entry_conditions(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]:
        """
        Check for PCR extremes and generate contrarian signals.
        """
        self.pcr_history.append(data.pcr)
        
        # Need history for context
        if len(self.pcr_history) < 10:
            return SignalType.NO_SIGNAL, "", 0
        
        avg_pcr = sum(self.pcr_history) / len(self.pcr_history)
        
        # EXTREME HIGH PCR:  Too bearish -> Go bullish (contrarian)
        if data.pcr > self.pcr_extreme_high:
            # Confirm with price action (looking for reversal)
            if data.is_green_candle:
                score = 3
                
                # Bonus:  RSI oversold or rising
                if data.rsi < 40:
                    score += 1
                
                # Bonus: Previous data showing reversal
                if self.prev_data and data.rsi > self.prev_data.rsi:
                    score += 1
                
                # Bonus: Near support
                if context.nearest_support > 0:
                    dist = data.future_price - context.nearest_support
                    if dist < 50:
                        score += 1
                
                # Bonus: Volume confirmation
                if data.volume_relative > 1.5:
                    score += 1
                
                return (
                    SignalType.BUY_CE,
                    f"PCR_Extreme_High ({data.pcr:.2f} Avg:{avg_pcr:.2f}) Contrarian_Bullish",
                    min(5, score)
                )
        
        # EXTREME LOW PCR: Too bullish -> Go bearish (contrarian)
        if data.pcr < self.pcr_extreme_low: 
            if not data.is_green_candle: 
                score = 3
                
                # Bonus: RSI overbought or falling
                if data.rsi > 60:
                    score += 1
                
                if self.prev_data and data.rsi < self.prev_data.rsi:
                    score += 1
                
                # Bonus: Near resistance
                if context.nearest_resistance > 0:
                    dist = context.nearest_resistance - data.future_price
                    if dist < 50:
                        score += 1
                
                # Bonus: Volume confirmation
                if data.volume_relative > 1.5:
                    score += 1
                
                return (
                    SignalType.BUY_PE,
                    f"PCR_Extreme_Low ({data.pcr:.2f} Avg:{avg_pcr:.2f}) Contrarian_Bearish",
                    min(5, score)
                )
        
        return SignalType.NO_SIGNAL, "", 0
    
    def get_pcr_state(self) -> dict:
        """Returns current PCR analysis."""
        if not self.pcr_history:
            return {'current':  0, 'avg': 0, 'extreme':  'NONE'}
        
        current = self.pcr_history[-1]
        avg = sum(self.pcr_history) / len(self.pcr_history)
        
        if current > self.pcr_extreme_high:
            extreme = 'HIGH'
        elif current < self.pcr_extreme_low: 
            extreme = 'LOW'
        else:
            extreme = 'NONE'
        
        return {
            'current': current,
            'avg': avg,
            'extreme': extreme
        }


class OIDivergenceStrategy(BaseStrategy):
    """
    OI DIVERGENCE STRATEGY
    
    Focus: Trading divergences between price and OI.
    
    Theory: 
    - Price making new highs but OI declining = Weak rally (divergence)
    - Price making new lows but OI declining = Weak selloff (divergence)
    - Divergence often precedes reversal
    
    This catches the end of moves before reversal.
    """
    
    STRATEGY_NAME = "OI_Divergence"
    STRATEGY_CODE = "OI_DIVERGENCE"
    OPTIMAL_REGIMES = ["TRENDING", "RANGING"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe: str = "1minute"):
        super().__init__(config, timeframe)
        
        # Price and OI tracking
        self.price_history: deque = deque(maxlen=20)
        self.oi_history: deque = deque(maxlen=20)
        
        # Divergence detection settings
        self.lookback = 10
        self.min_price_move_pct = 0.3  # 0.3% price move
        self.min_oi_divergence_pct = 3  # 3% OI divergence
    
    def _check_entry_conditions(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]:
        """
        Check for OI-Price divergences.
        """
        # Track data
        self.price_history.append(data.future_price)
        total_oi = context.order_flow.total_ce_oi + context.order_flow.total_pe_oi
        self.oi_history.append(total_oi)
        
        # Need enough history
        if len(self.price_history) < self.lookback:
            return SignalType.NO_SIGNAL, "", 0
        
        # Check for divergence
        signal = self._detect_divergence(data, context)
        
        return signal
    
    def _detect_divergence(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]: 
        """
        Detects bearish and bullish divergences.
        """
        prices = list(self.price_history)
        ois = list(self.oi_history)
        
        # Get lookback values
        price_start = prices[-self.lookback]
        price_end = prices[-1]
        oi_start = ois[-self.lookback]
        oi_end = ois[-1]
        
        # Calculate changes
        price_change_pct = ((price_end - price_start) / price_start) * 100
        oi_change_pct = ((oi_end - oi_start) / oi_start) * 100 if oi_start > 0 else 0
        
        # BEARISH DIVERGENCE: Price up, OI down
        if price_change_pct > self.min_price_move_pct and oi_change_pct < -self.min_oi_divergence_pct:
            # Price rising but participation declining = weak rally
            if data.rsi > 60:   # Overbought adds confidence
                score = 3
                
                if data.rsi > 70:
                    score += 1
                if not data.is_green_candle:  # Reversal candle
                    score += 1
                if context.nearest_resistance > 0 and data.future_price > context.nearest_resistance - 20:
                    score += 1
                
                return (
                    SignalType.BUY_PE,
                    f"Bearish_Divergence (Price+{price_change_pct:.1f}% OI{oi_change_pct:.1f}%)",
                    min(5, score)
                )
        
        # BULLISH DIVERGENCE: Price down, OI down
        if price_change_pct < -self.min_price_move_pct and oi_change_pct < -self.min_oi_divergence_pct:
            # Price falling but participation declining = weak selloff
            if data.rsi < 40:  # Oversold adds confidence
                score = 3
                
                if data.rsi < 30:
                    score += 1
                if data.is_green_candle:  # Reversal candle
                    score += 1
                if context.nearest_support > 0 and data.future_price < context.nearest_support + 20:
                    score += 1
                
                return (
                    SignalType.BUY_CE,
                    f"Bullish_Divergence (Price{price_change_pct:.1f}% OI{oi_change_pct:.1f}%)",
                    min(5, score)
                )
        
        return SignalType.NO_SIGNAL, "", 0


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing Order Flow Strategies...\n")
    
    # Mock config
    class MockConfig:
        class Exit:
            COOLDOWN_SECONDS = 60
            EXITS_BY_REGIME = {
                'TRENDING': {'target': 15, 'stop': 5},
                'RANGING': {'target':  8, 'stop':  8}
            }
        class RSI:
            OVERSOLD = 35
            OVERBOUGHT = 65
    
    from market_intelligence.market_context import (
        MarketContextBuilder, MarketRegime, MarketBias, TimeWindow,
        VolatilityState, OrderFlowState
    )
    
    # Test OrderFlowStrategy
    print("=" * 50)
    print("Testing OrderFlowStrategy...")
    
    of_strategy = OrderFlowStrategy(MockConfig())
    
    # Create bullish order flow scenario
    data = MarketData(
        timestamp=datetime.now(),
        spot_price=24050,
        future_price=24080,
        future_open=24000,
        future_high=24100,
        future_low=23980,
        future_close=24080,
        vwap=24030,
        atm_strike=24100,
        rsi=58,
        ema_5=24060,
        ema_13=24040,
        ema_21=24020,
        ema_50=23980,
        adx=28,
        atr=50,
        candle_body=60,
        candle_range=120,
        is_green_candle=True,
        pcr=1.25,  # High PCR = bullish
        ce_oi_change_pct=2.0,
        pe_oi_change_pct=8.0,  # PE OI increasing faster = support building
        volume_relative=1.5
    )
    
    # Context with bullish order flow
    order_flow = OrderFlowState(
        total_ce_oi=1000000,
        total_pe_oi=1200000,
        pcr=1.25,
        ce_oi_change=20000,
        pe_oi_change=80000,
        ce_oi_change_pct=2.0,
        pe_oi_change_pct=8.0,
        oi_signal="LONG_BUILDUP",
        smart_money_direction="BULLISH",
        volume_state="HIGH",
        relative_volume=1.5
    )
    
    context = MarketContextBuilder()\
        .set_regime(MarketRegime.TRENDING_UP, 28, 10)\
        .set_bias(MarketBias.BULLISH, 40)\
        .set_time_window(TimeWindow.MORNING_SESSION, 280, False)\
        .set_volatility(VolatilityState.NORMAL, 50, 50, 50)\
        .set_order_flow(order_flow)\
        .build()
    
    signal = of_strategy.check_entry(data, context)
    
    if signal: 
        print(f"Signal: {signal.signal_type.value}")
        print(f"Reason: {signal.reason}")
        print(f"Strength: {signal.strength.value}")
        print(f"Score: {signal.base_score}")
    else: 
        print("No signal generated")
    
    # Test PCRExtremeStrategy
    print("\n" + "=" * 50)
    print("Testing PCRExtremeStrategy...")
    
    pcr_strategy = PCRExtremeStrategy(MockConfig())
    
    # Build up PCR history
    for i in range(15):
        test_data = MarketData(
            timestamp=datetime.now(),
            spot_price=24000,
            future_price=24000,
            future_open=24000,
            future_high=24010,
            future_low=23990,
            future_close=24000,
            vwap=24000,
            atm_strike=24000,
            rsi=50,
            ema_5=24000,
            ema_13=24000,
            ema_21=24000,
            ema_50=24000,
            adx=20,
            atr=40,
            candle_body=10,
            candle_range=20,
            is_green_candle=True,
            pcr=1.0 + i * 0.03,  # PCR gradually increasing
            ce_oi_change_pct=1.0,
            pe_oi_change_pct=1.0,
            volume_relative=1.0
        )
        pcr_strategy.check_entry(test_data, context)
    
    # Now test with extreme high PCR
    extreme_data = MarketData(
        timestamp=datetime.now(),
        spot_price=23950,
        future_price=23960,
        future_open=23900,
        future_high=23970,
        future_low=23890,
        future_close=23960,
        vwap=23950,
        atm_strike=24000,
        rsi=35,  # Oversold
        ema_5=23960,
        ema_13=23970,
        ema_21=23980,
        ema_50=24000,
        adx=18,
        atr=45,
        candle_body=50,
        candle_range=80,
        is_green_candle=True,  # Reversal candle
        pcr=1.55,  # EXTREME HIGH PCR
        ce_oi_change_pct=1.0,
        pe_oi_change_pct=5.0,
        volume_relative=1.8
    )
    
    # Context with support nearby
    context_with_support = MarketContextBuilder()\
        .set_regime(MarketRegime.RANGING, 18, 20)\
        .set_bias(MarketBias.NEUTRAL, 0)\
        .set_time_window(TimeWindow.MORNING_SESSION, 280, False)\
        .set_key_levels([], 23920, 24100, 24000, 24000)\
        .build()
    
    signal = pcr_strategy.check_entry(extreme_data, context_with_support)
    
    print(f"\nPCR State: {pcr_strategy.get_pcr_state()}")
    
    if signal: 
        print(f"Signal: {signal.signal_type.value}")
        print(f"Reason:  {signal.reason}")
        print(f"Strength: {signal.strength.value}")
    else:
        print("No signal generated")
    
    # Test OIDivergenceStrategy
    print("\n" + "=" * 50)
    print("Testing OIDivergenceStrategy...")
    
    div_strategy = OIDivergenceStrategy(MockConfig())
    
    # Build history with divergence (price up, OI down)
    for i in range(12):
        price = 24000 + i * 10  # Price going UP
        oi_total = 2000000 - i * 50000  # OI going DOWN
        
        test_data = MarketData(
            timestamp=datetime.now(),
            spot_price=price,
            future_price=price + 20,
            future_open=price,
            future_high=price + 25,
            future_low=price - 5,
            future_close=price + 15,
            vwap=price,
            atm_strike=24000,
            rsi=60 + i,  # RSI rising toward overbought
            ema_5=price,
            ema_13=price - 10,
            ema_21=price - 20,
            ema_50=price - 50,
            adx=25,
            atr=40,
            candle_body=15,
            candle_range=30,
            is_green_candle=True,
            pcr=1.0,
            ce_oi_change_pct=-2.0,
            pe_oi_change_pct=-3.0,
            volume_relative=0.8  # Declining volume
        )
        
        test_context = MarketContextBuilder()\
            .set_regime(MarketRegime.TRENDING_UP, 25, 10)\
            .set_order_flow(OrderFlowState(
                total_ce_oi=oi_total // 2,
                total_pe_oi=oi_total // 2,
                pcr=1.0
            ))\
            .set_key_levels([], 23900, 24150, 24000, 24000)\
            .build()
        
        signal = div_strategy.check_entry(test_data, test_context)
    
    if signal:
        print(f"Signal:  {signal.signal_type.value}")
        print(f"Reason: {signal.reason}")
        print(f"Strength: {signal.strength.value}")
    else:
        print("No signal (divergence may not be significant enough)")
    
    print("\n✅ Order Flow Strategies Test Complete!")