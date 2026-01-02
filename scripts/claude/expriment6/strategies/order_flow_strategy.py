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
sys.path.append(os.path. dirname(os.path.dirname(os. path.abspath(__file__))))

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
    1. Significant OI change in one direction (>5%)
    2. OI-Price relationship confirms (buildup type)
    3. PCR supports the direction
    4. Price action confirmation
    
    Works in: TRENDING, RANGING (smart money always active)
    """
    
    STRATEGY_NAME = "Order_Flow"
    STRATEGY_CODE = "ORDER_FLOW"
    OPTIMAL_REGIMES = ["TRENDING", "RANGING"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "LUNCH_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe: str = "1minute"):
        super().__init__(config, timeframe)
        
        # OI tracking
        self.ce_oi_history: deque = deque(maxlen=20)
        self.pe_oi_history: deque = deque(maxlen=20)
        self.pcr_history: deque = deque(maxlen=20)
        
        # Thresholds
        self. oi_change_threshold = 5.0  # 5% OI change is significant
        self. pcr_bullish = 1.15  # PCR > 1.15 is bullish
        self.pcr_bearish = 0.85  # PCR < 0.85 is bearish
    
    def _check_entry_conditions(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]:
        """
        Analyzes order flow and generates signals.
        """
        # Track OI
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
        pe_change = of. pe_oi_change_pct
        
        # Calculate imbalance
        imbalance = pe_change - ce_change
        
        # BULLISH:  PE writers much more active (creating support)
        if imbalance > self.oi_change_threshold:
            # Confirm with PCR
            if data.pcr > self.pcr_bullish:
                score = 3
                
                # Price confirmation
                if data. price_above_vwap:
                    score += 1
                if data.is_green_candle:
                    score += 1
                if of.smart_money_direction == "BULLISH": 
                    score += 1
                
                return (
                    SignalType. BUY_CE,
                    f"OI_Bullish (PE+{pe_change:.1f}% CE+{ce_change:.1f}% PCR:{data.pcr:. 2f})",
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
                    f"OI_Bearish (CE+{ce_change:.1f}% PE+{pe_change:. 1f}% PCR:{data.pcr:.2f})",
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
                    SignalType. BUY_CE,
                    f"Long_Buildup (Price↑ OI↑ RSI:{data.rsi:. 1f})",
                    min(5, score)
                )
        
        # SHORT BUILDUP:  Strong bearish continuation
        elif oi_signal == "SHORT_BUILDUP": 
            if context.regime == MarketRegime. TRENDING_DOWN: 
                score = 4
                
                if data.price_below_vwap: 
                    score += 1
                if data.rsi_bearish_momentum: 
                    score += 1
                
                return (
                    SignalType. BUY_PE,
                    f"Short_Buildup (Price↓ OI↑ RSI:{data.rsi:.1f})",
                    min(5, score)
                )
        
        # SHORT COVERING:  Weak bullish (can trade if other confirmations)
        elif oi_signal == "SHORT_COVERING":
            # Shorts exiting = price going up, but weaker signal
            if data.price_above_vwap and data.is_green_candle:
                if context.bias in [MarketBias.BULLISH, MarketBias. STRONG_BULLISH]:
                    return (
                        SignalType.BUY_CE,
                        f"Short_Covering (Price↑ OI↓ Bias:{context.bias. value})",
                        3  # Lower score - weaker signal
                    )
        
        # LONG UNWINDING: Weak bearish
        elif oi_signal == "LONG_UNWINDING": 
            if data.price_below_vwap and not data.is_green_candle: 
                if context.bias in [MarketBias.BEARISH, MarketBias.STRONG_BEARISH]:
                    return (
                        SignalType. BUY_PE,
                        f"Long_Unwinding (Price↓ OI↓ Bias:{context.bias.value})",
                        3
                    )
        
        return SignalType.NO_SIGNAL, "", 0


class PCRExtremeStrategy(BaseStrategy):
    """
    PCR EXTREME STRATEGY
    
    Focus: Trading PCR extremes (contrarian).
    
    Theory:
    - Extreme high PCR (>1.5): Too many puts = Retail bearish = Market will rise
    - Extreme low PCR (<0.5): Too many calls = Retail bullish = Market will fall
    
    This is a CONTRARIAN strategy against retail sentiment.
    """
    
    STRATEGY_NAME = "PCR_Extreme"
    STRATEGY_CODE = "PCR_EXTREME"
    OPTIMAL_REGIMES = ["RANGING"]
    ACTIVE_TIME_WINDOWS = ["MORNING_SESSION", "LUNCH_SESSION", "POWER_HOUR"]
    
    def __init__(self, config, timeframe: str = "1minute"):
        super().__init__(config, timeframe)
        
        # PCR extremes
        self. pcr_extreme_high = 1.4  # Extreme bearish sentiment
        self.pcr_extreme_low = 0.6   # Extreme bullish sentiment
        
        # Track PCR for changes
        self.pcr_history: deque = deque(maxlen=30)
    
    def _check_entry_conditions(self, data: MarketData, context:  MarketContext) -> Tuple[SignalType, str, int]:
        """
        Check for PCR extremes and generate contrarian signals.
        """
        self.pcr_history.append(data. pcr)
        
        # Need history for context
        if len(self.pcr_history) < 10:
            return SignalType.NO_SIGNAL, "", 0
        
        avg_pcr = sum(self.pcr_history) / len(self.pcr_history)
        
        # EXTREME HIGH PCR:  Too bearish -> Go bullish
        if data.pcr > self.pcr_extreme_high:
            # Confirm with price action (looking for reversal)
            if data.is_green_candle:
                score = 3
                
                # Bonus:  RSI oversold or rising
                if data. rsi < 40 or (data.rsi > self.prev_data.rsi if self.prev_data else False):
                    score += 1
                
                # Bonus: Near support
                if context.nearest_support > 0:
                    dist = data.future_price - context.nearest_support
                    if dist < 50:
                        score += 1
                
                return (
                    SignalType.BUY_CE,
                    f"PCR_Extreme_High ({data.pcr:.2f} Avg:{avg_pcr:.2f}) Contrarian_Bullish",
                    min(5, score)
                )
        
        # EXTREME LOW PCR: Too bullish -> Go bearish
        if data.pcr < self.pcr_extreme_low:
            if not data.is_green_candle: 
                score = 3
                
                if data.rsi > 60 or (data.rsi < self.prev_data.rsi if self.prev_data else False):
                    score += 1
                
                if context.nearest_resistance > 0:
                    dist = context.nearest_resistance - data.future_price
                    if dist < 50:
                        score += 1
                
                return (
                    SignalType.BUY_PE,
                    f"PCR_Extreme_Low ({data. pcr:.2f} Avg:{avg_pcr:.2f}) Contrarian_Bearish",
                    min(5, score)
                )
        
        return SignalType.NO_SIGNAL, "", 0


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__": 
    print("\n🔬 Testing Order Flow Strategy.. .\n")
    
    class MockConfig:
        class Exit:
            COOLDOWN_SECONDS = 60
            EXITS