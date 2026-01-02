"""
BIAS CALCULATOR
Determines directional bias:  BULLISH, BEARISH, or NEUTRAL.

Uses multiple factors: 
- Futures Premium (Futures - Spot price)
- EMA Alignment (5 > 13 > 21 > 50)
- PCR (Put-Call Ratio)
- Price vs VWAP
- RSI Zone

Combines all factors into a single bias score from -100 to +100.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from collections import deque
from enum import Enum

import sys
import os
sys.path.append(os.path.dirname(os.path. dirname(os.path.abspath(__file__))))

from market_intelligence.market_context import MarketBias


@dataclass
class BiasState:
    """Holds current bias analysis results."""
    bias: MarketBias
    score: float                    # -100 to +100
    
    # Component scores
    premium_score: float            # Futures premium contribution
    ema_score: float                # EMA alignment contribution
    pcr_score: float                # Put-Call ratio contribution
    vwap_score:  float               # Price vs VWAP contribution
    rsi_score: float                # RSI zone contribution
    
    # Raw values
    futures_premium: float
    ema_alignment: str              # 'BULLISH', 'BEARISH', 'MIXED'
    pcr: float
    price_vs_vwap:  str              # 'ABOVE', 'BELOW', 'AT'
    rsi:  float
    
    confidence: float               # 0-100


class BiasCalculator:
    """
    Calculates market directional bias by combining multiple factors. 
    
    Each factor contributes to a total score from -100 to +100:
    - Above +50: STRONG_BULLISH
    - +20 to +50: BULLISH
    - -20 to +20: NEUTRAL
    - -50 to -20: BEARISH
    - Below -50: STRONG_BEARISH
    """
    
    def __init__(self, config):
        self.config = config
        
        # Thresholds from config
        self. premium_strong_bull = config.Bias.PREMIUM_STRONG_BULLISH
        self. premium_bull = config.Bias. PREMIUM_BULLISH
        self.premium_neutral = config. Bias.PREMIUM_NEUTRAL_LOW
        self.premium_bear = config. Bias.PREMIUM_BEARISH
        
        self.pcr_bullish = config. Bias.PCR_BULLISH
        self.pcr_bearish = config. Bias.PCR_BEARISH
        
        # EMA periods to track
        self. ema_periods = config.Bias.EMA_PERIODS  # [5, 13, 21, 50]
        
        # Data storage
        self. closes = deque(maxlen=100)
        self. ema_values:  Dict[int, float] = {}  # period -> current EMA value
        
        # Score history for smoothing
        self. score_history = deque(maxlen=10)
        
        # Weights for each component (total = 100)
        self.weights = {
            'premium': 25,
            'ema':  25,
            'pcr': 20,
            'vwap': 15,
            'rsi': 15
        }
        
        # Current state
        self.current_bias = MarketBias. NEUTRAL
        self. warmup_complete = False

    def update(self, spot:  float, future: float, vwap: float, 
               pcr: float, rsi: float) -> BiasState: 
        """
        Main update method. Call with each data refresh.
        
        Args:
            spot: Current spot price
            future: Current futures price
            vwap: Current VWAP
            pcr: Put-Call Ratio
            rsi: RSI value
            
        Returns:
            BiasState with current analysis
        """
        # Store close for EMA
        self.closes. append(spot)
        
        # Update EMAs
        self._update_emas()
        
        # Calculate futures premium
        premium = future - spot
        
        # Calculate component scores
        premium_score = self._score_premium(premium)
        ema_score, ema_alignment = self._score_ema_alignment(spot)
        pcr_score = self._score_pcr(pcr)
        vwap_score, price_vs_vwap = self._score_vwap(spot, vwap)
        rsi_score = self._score_rsi(rsi)
        
        # Combine into total score
        total_score = (
            premium_score * self. weights['premium'] / 100 +
            ema_score * self.weights['ema'] / 100 +
            pcr_score * self.weights['pcr'] / 100 +
            vwap_score * self.weights['vwap'] / 100 +
            rsi_score * self.weights['rsi'] / 100
        )
        
        # Smooth score using history
        self.score_history. append(total_score)
        smoothed_score = sum(self.score_history) / len(self.score_history)
        
        # Determine bias from score
        bias = self._score_to_bias(smoothed_score)
        self.current_bias = bias
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            premium_score, ema_score, pcr_score, vwap_score, rsi_score
        )
        
        # Warmup check
        if len(self.closes) > max(self.ema_periods):
            self.warmup_complete = True
        
        return BiasState(
            bias=bias,
            score=smoothed_score,
            premium_score=premium_score,
            ema_score=ema_score,
            pcr_score=pcr_score,
            vwap_score=vwap_score,
            rsi_score=rsi_score,
            futures_premium=premium,
            ema_alignment=ema_alignment,
            pcr=pcr,
            price_vs_vwap=price_vs_vwap,
            rsi=rsi,
            confidence=confidence
        )

    def _update_emas(self):
        """Updates all EMA values."""
        if len(self.closes) < 2:
            return
        
        close = self.closes[-1]
        
        for period in self. ema_periods: 
            if len(self.closes) < period:
                continue
            
            if period not in self.ema_values:
                # Initialize with SMA
                self. ema_values[period] = sum(list(self.closes)[-period:]) / period
            else: 
                # EMA formula
                multiplier = 2 / (period + 1)
                self. ema_values[period] = (close * multiplier + 
                                           self.ema_values[period] * (1 - multiplier))

    def _score_premium(self, premium: float) -> float:
        """
        Scores futures premium. 
        
        High premium = Bullish (traders paying more for futures)
        Discount = Bearish (futures cheaper than spot)
        
        Returns:  -100 to +100
        """
        if premium >= self.premium_strong_bull:
            return 100
        elif premium >= self.premium_bull:
            # Scale from 50 to 100
            return 50 + (premium - self.premium_bull) / (self.premium_strong_bull - self. premium_bull) * 50
        elif premium >= self. premium_neutral: 
            # Scale from 0 to 50
            return (premium - self.premium_neutral) / (self.premium_bull - self.premium_neutral) * 50
        elif premium >= self.premium_bear:
            # Scale from -50 to 0
            return (premium - self. premium_bear) / (self.premium_neutral - self.premium_bear) * 50 - 50
        else:
            # Strong bearish
            return max(-100, -50 - abs(premium - self.premium_bear))

    def _score_ema_alignment(self, price: float) -> Tuple[float, str]:
        """
        Scores EMA alignment.
        
        Perfect bullish: 5 > 13 > 21 > 50, price > all
        Perfect bearish:  5 < 13 < 21 < 50, price < all
        
        Returns: (score -100 to +100, alignment string)
        """
        if len(self.ema_values) < len(self.ema_periods):
            return 0, 'MIXED'
        
        # Get EMAs in order
        emas = [self.ema_values. get(p, 0) for p in self. ema_periods]
        
        if 0 in emas: 
            return 0, 'MIXED'
        
        score = 0
        bullish_pairs = 0
        bearish_pairs = 0
        
        # Check EMA order (5 vs 13, 13 vs 21, 21 vs 50)
        for i in range(len(emas) - 1):
            if emas[i] > emas[i + 1]:
                bullish_pairs += 1
                score += 20
            elif emas[i] < emas[i + 1]:
                bearish_pairs += 1
                score -= 20
        
        # Check price vs shortest EMA
        if price > emas[0]:
            score += 20
        elif price < emas[0]: 
            score -= 20
        
        # Check price vs longest EMA
        if price > emas[-1]: 
            score += 20
        elif price < emas[-1]:
            score -= 20
        
        # Determine alignment
        if bullish_pairs >= 2 and price > emas[0]:
            alignment = 'BULLISH'
        elif bearish_pairs >= 2 and price < emas[0]:
            alignment = 'BEARISH'
        else:
            alignment = 'MIXED'
        
        return max(-100, min(100, score)), alignment

    def _score_pcr(self, pcr: float) -> float:
        """
        Scores Put-Call Ratio.
        
        High PCR = Bullish (more puts being written = support)
        Low PCR = Bearish (more calls being written = resistance)
        
        This is CONTRARIAN logic - writers are usually right. 
        
        Returns: -100 to +100
        """
        if pcr <= 0:
            return 0
        
        if pcr >= self.pcr_bullish:
            # High PCR = Bullish
            excess = pcr - self.pcr_bullish
            return min(100, 50 + excess * 100)
        elif pcr >= 1.0:
            # Slightly bullish
            return (pcr - 1.0) / (self.pcr_bullish - 1.0) * 50
        elif pcr >= self.pcr_bearish:
            # Slightly bearish to neutral
            return (pcr - 1.0) / (1.0 - self.pcr_bearish) * 50
        else:
            # Low PCR = Bearish
            deficit = self.pcr_bearish - pcr
            return max(-100, -50 - deficit * 100)

    def _score_vwap(self, price: float, vwap: float) -> Tuple[float, str]:
        """
        Scores price position relative to VWAP.
        
        Above VWAP = Bullish intraday bias
        Below VWAP = Bearish intraday bias
        
        Returns: (score -100 to +100, position string)
        """
        if vwap <= 0:
            return 0, 'AT'
        
        # Calculate distance as percentage
        distance = price - vwap
        distance_pct = (distance / vwap) * 100
        
        # Determine position
        if distance_pct > 0. 2: 
            position = 'ABOVE'
        elif distance_pct < -0.2:
            position = 'BELOW'
        else: 
            position = 'AT'
        
        # Score based on distance
        # ±1% from VWAP = ±100 score
        score = distance_pct * 100
        score = max(-100, min(100, score))
        
        return score, position

    def _score_rsi(self, rsi: float) -> float:
        """
        Scores RSI zone.
        
        Bullish zone: 55-70 (momentum up)
        Bearish zone: 30-45 (momentum down)
        Overbought: >70 (potential reversal down)
        Oversold: <30 (potential reversal up)
        
        Returns: -100 to +100
        """
        if rsi >= 70:
            # Overbought - slightly bearish (expect pullback)
            return -20 - (rsi - 70)
        elif rsi >= 55:
            # Bullish momentum
            return 20 + (rsi - 55) * 2
        elif rsi >= 45:
            # Neutral zone
            return (rsi - 50) * 4
        elif rsi >= 30:
            # Bearish momentum
            return -20 - (45 - rsi) * 2
        else:
            # Oversold - slightly bullish (expect bounce)
            return 20 + (30 - rsi)

    def _score_to_bias(self, score: float) -> MarketBias: 
        """Converts numeric score to MarketBias enum."""
        if score >= 50:
            return MarketBias. STRONG_BULLISH
        elif score >= 20:
            return MarketBias.BULLISH
        elif score >= -20:
            return MarketBias. NEUTRAL
        elif score >= -50:
            return MarketBias.BEARISH
        else: 
            return MarketBias.STRONG_BEARISH

    def _calculate_confidence(self, premium:  float, ema:  float, 
                             pcr: float, vwap: float, rsi: float) -> float:
        """
        Calculates confidence based on agreement between factors.
        
        High confidence = All factors pointing same direction
        Low confidence = Mixed signals
        """
        scores = [premium, ema, pcr, vwap, rsi]
        
        # Count bullish vs bearish factors
        bullish = sum(1 for s in scores if s > 20)
        bearish = sum(1 for s in scores if s < -20)
        neutral = len(scores) - bullish - bearish
        
        # Agreement = confidence
        if bullish >= 4 or bearish >= 4:
            return 90
        elif bullish >= 3 or bearish >= 3:
            return 70
        elif bullish >= 2 and bearish == 0:
            return 60
        elif bearish >= 2 and bullish == 0:
            return 60
        elif neutral >= 3: 
            return 40  # Neutral is low confidence
        else: 
            return 30  # Mixed signals

    def get_ema_values(self) -> Dict[int, float]: 
        """Returns current EMA values."""
        return self. ema_values.copy()

    def is_ready(self) -> bool:
        """Checks if calculator has enough data."""
        return self.warmup_complete

    def get_bias_simple(self) -> str:
        """Returns simplified bias for strategy use."""
        if self.current_bias in [MarketBias.STRONG_BULLISH, MarketBias.BULLISH]:
            return 'BULLISH'
        elif self.current_bias in [MarketBias.STRONG_BEARISH, MarketBias.BEARISH]:
            return 'BEARISH'
        else: 
            return 'NEUTRAL'


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__": 
    print("\n🔬 Testing Bias Calculator.. .\n")
    
    # Mock config
    class MockConfig:
        class Bias:
            PREMIUM_STRONG_BULLISH = 80
            PREMIUM_BULLISH = 50
            PREMIUM_NEUTRAL_LOW = 20
            PREMIUM_BEARISH = -20
            EMA_PERIODS = [5, 13, 21, 50]
            PCR_BULLISH = 1.2
            PCR_BEARISH = 0.8
    
    calc = BiasCalculator(MockConfig())
    
    # Simulate bullish market
    print("Simulating BULLISH market conditions...")
    base_price = 24000
    
    for i in range(60):
        spot = base_price + i * 2
        future = spot + 60  # Strong premium
        vwap = base_price + i  # Price above VWAP
        pcr = 1.3  # High PCR
        rsi = 62  # Bullish momentum
        
        state = calc.update(spot, future, vwap, pcr, rsi)
    
    print(f"\nBias: {state.bias.value}")
    print(f"Score: {state.score:.1f}")
    print(f"\nComponent Scores:")
    print(f"  Premium: {state. premium_score:.1f} (Premium: {state.futures_premium:.1f})")
    print(f"  EMA:      {state.ema_score:.1f} ({state.ema_alignment})")
    print(f"  PCR:     {state.pcr_score:.1f} (PCR: {state.pcr:. 2f})")
    print(f"  VWAP:    {state. vwap_score:.1f} ({state.price_vs_vwap})")
    print(f"  RSI:     {state. rsi_score:. 1f} (RSI: {state. rsi:.1f})")
    print(f"\nConfidence: {state.confidence:.0f}%")
    
    print("\n" + "="*50)
    print("Simulating BEARISH market conditions...")
    
    # Reset
    calc = BiasCalculator(MockConfig())
    
    for i in range(60):
        spot = base_price - i * 2
        future = spot - 30  # Discount
        vwap = base_price - i  # Price below VWAP
        pcr = 0.7  # Low PCR
        rsi = 38  # Bearish momentum
        
        state = calc.update(spot, future, vwap, pcr, rsi)
    
    print(f"\nBias: {state. bias.value}")
    print(f"Score: {state. score:.1f}")
    print(f"Confidence: {state. confidence:.0f}%")
    
    print("\n✅ Bias Calculator Test Complete!")