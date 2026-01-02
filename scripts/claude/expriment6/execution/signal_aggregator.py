"""
SIGNAL AGGREGATOR
Combines signals from multiple strategies into actionable trades. 

Key Functions:
1. Collects signals from all active strategies
2. Calculates confluence score (how many strategies agree)
3. Filters weak signals
4. Prevents conflicting trades (CE and PE at same time)
5. Prioritizes best signals when multiple exist

This is the "voting system" where strategies vote on direction.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict
from enum import Enum

import sys
import os
sys.path.append(os.path.dirname(os.path. dirname(os.path.abspath(__file__))))

from strategies.base_strategy import StrategySignal, SignalType, SignalStrength
from market_intelligence. market_context import MarketContext, MarketBias, MarketRegime


class TradeDecision(Enum):
    """Final trade decision."""
    EXECUTE = "EXECUTE"
    SKIP = "SKIP"
    WAIT = "WAIT"


@dataclass
class AggregatedSignal:
    """
    Combined signal from multiple strategies. 
    This is what gets passed to the execution layer.
    """
    # Decision
    decision: TradeDecision
    direction: Optional[SignalType]  # BUY_CE or BUY_PE
    
    # Confluence
    confluence_score:  int
    total_signals:  int
    agreeing_strategies: List[str]
    
    # Best signal details
    best_signal: Optional[StrategySignal]
    
    # Execution parameters
    suggested_size_multiplier: float  # 0.5 to 1.5
    suggested_target:  Optional[float]
    suggested_stop: Optional[float]
    
    # Context
    market_context_summary: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Reasons
    skip_reason: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            'decision': self.decision.value,
            'direction': self. direction.value if self.direction else None,
            'confluence':  self.confluence_score,
            'strategies': self.agreeing_strategies,
            'size_mult': self.suggested_size_multiplier,
            'skip_reason': self. skip_reason,
            'timestamp': self.timestamp. strftime("%H:%M:%S")
        }


class SignalAggregator:
    """
    Aggregates and prioritizes signals from multiple strategies.
    
    Confluence Logic:
    - Multiple strategies signaling same direction = STRONG
    - Only one strategy = MODERATE
    - Conflicting signals = SKIP
    
    Scoring:
    - Each strategy signal:  +1 base
    - Strong signal: +1 bonus
    - Regime alignment: +2 bonus
    - Bias alignment: +1 bonus
    - Order flow confirmation: +2 bonus
    """
    
    def __init__(self, config):
        self.config = config
        
        # Confluence thresholds
        self.min_score_high = config. Confluence.MIN_SCORE_HIGH_CONFIDENCE
        self.min_score_medium = config.Confluence.MIN_SCORE_MEDIUM_CONFIDENCE
        self. min_score_low = config.Confluence.MIN_SCORE_LOW_CONFIDENCE
        
        # Weights
        self.weights = config.Confluence. WEIGHTS
        
        # Signal history for analysis
        self.signal_history: List[AggregatedSignal] = []
        
        # Stats
        self.signals_processed = 0
        self.signals_executed = 0
        self.signals_skipped = 0
    
    def aggregate(self, signals: List[StrategySignal], 
                  context: MarketContext) -> AggregatedSignal:
        """
        Main aggregation method.
        
        Args:
            signals: List of signals from all strategies
            context: Current market context
            
        Returns:
            AggregatedSignal with final decision
        """
        self.signals_processed += 1
        
        # Filter out NO_SIGNAL
        active_signals = [s for s in signals if s.signal_type != SignalType. NO_SIGNAL]
        
        # No signals case
        if not active_signals:
            return self._create_skip_signal("No active signals", context)
        
        # Separate by direction
        ce_signals = [s for s in active_signals if s.signal_type == SignalType.BUY_CE]
        pe_signals = [s for s in active_signals if s.signal_type == SignalType. BUY_PE]
        
        # Check for conflict
        if ce_signals and pe_signals:
            # Conflicting signals - need to resolve
            return self._resolve_conflict(ce_signals, pe_signals, context)
        
        # Single direction
        if ce_signals:
            return self._aggregate_direction(ce_signals, SignalType.BUY_CE, context)
        else:
            return self._aggregate_direction(pe_signals, SignalType.BUY_PE, context)
    
    def _aggregate_direction(self, signals: List[StrategySignal], 
                             direction: SignalType,
                             context:  MarketContext) -> AggregatedSignal:
        """
        Aggregates signals for a single direction.
        """
        # Calculate base confluence score
        confluence_score = 0
        
        # 1. Strategy count (each strategy = 1 point)
        confluence_score += len(signals) * self.weights['strategy_signal']
        
        # 2. Sum of individual signal scores
        for signal in signals: 
            if signal.strength == SignalStrength. STRONG:
                confluence_score += 1
        
        # 3. Context alignment bonuses
        # Regime alignment
        is_bullish = direction == SignalType. BUY_CE
        regime_aligned = (
            (is_bullish and context.regime == MarketRegime. TRENDING_UP) or
            (not is_bullish and context.regime == MarketRegime. TRENDING_DOWN)
        )
        if regime_aligned: 
            confluence_score += self.weights['regime_alignment']
        
        # Bias alignment
        bias_aligned = (
            (is_bullish and context.bias in [MarketBias.BULLISH, MarketBias. STRONG_BULLISH]) or
            (not is_bullish and context.bias in [MarketBias. BEARISH, MarketBias.STRONG_BEARISH])
        )
        if bias_aligned: 
            confluence_score += self.weights['bias_alignment']
        
        # Order flow confirmation
        order_flow_aligned = (
            (is_bullish and context.order_flow. smart_money_direction == "BULLISH") or
            (not is_bullish and context.order_flow. smart_money_direction == "BEARISH")
        )
        if order_flow_aligned:
            confluence_score += self.weights['order_flow_confirmation']
        
        # Volume confirmation
        if context.order_flow.volume_state in ["SPIKE", "HIGH"]:
            confluence_score += self.weights['volume_confirmation']
        
        # 4. Determine decision
        decision, skip_reason = self._determine_decision(confluence_score, signals, context)
        
        # 5. Get best signal (highest individual score)
        best_signal = max(signals, key=lambda s: s. base_score)
        
        # 6. Calculate size multiplier
        size_mult = self._calculate_size_multiplier(confluence_score, context)
        
        # 7. Get exit parameters
        target, stop = self._get_exit_params(signals, context)
        
        # 8. Create aggregated signal
        result = AggregatedSignal(
            decision=decision,
            direction=direction if decision == TradeDecision.EXECUTE else None,
            confluence_score=confluence_score,
            total_signals=len(signals),
            agreeing_strategies=[s.strategy_name for s in signals],
            best_signal=best_signal,
            suggested_size_multiplier=size_mult,
            suggested_target=target,
            suggested_stop=stop,
            market_context_summary=self._summarize_context(context),
            skip_reason=skip_reason
        )
        
        # Update stats
        if decision == TradeDecision.EXECUTE: 
            self.signals_executed += 1
        else: 
            self.signals_skipped += 1
        
        self.signal_history. append(result)
        
        return result
    
    def _resolve_conflict(self, ce_signals: List[StrategySignal],
                         pe_signals: List[StrategySignal],
                         context:  MarketContext) -> AggregatedSignal:
        """
        Resolves conflicting CE and PE signals. 
        
        Resolution methods:
        1. Count:  More signals win
        2. Quality: Higher total score wins
        3. Context: Bias breaks the tie
        4. Skip: If still unclear
        """
        # Method 1: Count
        if len(ce_signals) > len(pe_signals) + 1:
            return self._aggregate_direction(ce_signals, SignalType.BUY_CE, context)
        if len(pe_signals) > len(ce_signals) + 1:
            return self._aggregate_direction(pe_signals, SignalType.BUY_PE, context)
        
        # Method 2: Total score
        ce_score = sum(s.base_score for s in ce_signals)
        pe_score = sum(s.base_score for s in pe_signals)
        
        if ce_score > pe_score + 2:
            return self._aggregate_direction(ce_signals, SignalType.BUY_CE, context)
        if pe_score > ce_score + 2:
            return self._aggregate_direction(pe_signals, SignalType.BUY_PE, context)
        
        # Method 3: Context bias
        if context.bias in [MarketBias. STRONG_BULLISH, MarketBias. BULLISH]:
            return self._aggregate_direction(ce_signals, SignalType.BUY_CE, context)
        if context.bias in [MarketBias. STRONG_BEARISH, MarketBias.BEARISH]:
            return self._aggregate_direction(pe_signals, SignalType.BUY_PE, context)
        
        # Method 4: Skip - too unclear
        return self._create_skip_signal(
            f"Conflicting signals: {len(ce_signals)} CE vs {len(pe_signals)} PE",
            context
        )
    
    def _determine_decision(self, score: int, signals:  List[StrategySignal],
                           context:  MarketContext) -> Tuple[TradeDecision, str]: 
        """
        Determines whether to execute based on confluence score. 
        """
        # Check minimum threshold
        if score < self.min_score_low:
            return TradeDecision. SKIP, f"Low confluence ({score} < {self.min_score_low})"
        
        # Check market conditions
        if not context.is_tradeable():
            return TradeDecision.SKIP, "Market not tradeable"
        
        # High volatility caution
        if context.volatility_state. value == "EXTREME":
            if score < self.min_score_high:
                return TradeDecision. SKIP, "Extreme volatility requires high confluence"
        
        # Lunch session caution
        if context.time_window.value == "LUNCH_SESSION":
            if score < self.min_score_medium: 
                return TradeDecision.SKIP, "Lunch session requires medium confluence"
        
        # All checks passed
        return TradeDecision. EXECUTE, ""
    
    def _calculate_size_multiplier(self, score: int, context: MarketContext) -> float:
        """
        Calculates position size multiplier based on confidence.
        """
        # Base on score
        if score >= self.min_score_high:
            mult = 1.2  # Increase size for high confidence
        elif score >= self.min_score_medium: 
            mult = 1.0  # Normal size
        else: 
            mult = 0.7  # Reduce size for low confidence
        
        # Adjust for context
        mult *= context.get_position_size_multiplier()
        
        # Clamp
        return max(0.5, min(1.5, mult))
    
    def _get_exit_params(self, signals: List[StrategySignal],
                        context:  MarketContext) -> Tuple[Optional[float], Optional[float]]:
        """
        Gets exit parameters from signals or context.
        """
        # Check if any signal has suggested params
        for signal in signals:
            if signal.suggested_target and signal.suggested_stop:
                return signal.suggested_target, signal.suggested_stop
        
        # Use context-based (regime adaptive)
        exits = context.get_exit_params(self.config)
        return exits.get('target'), exits.get('stop')
    
    def _summarize_context(self, context: MarketContext) -> str:
        """Creates a brief context summary string."""
        return (f"{context.regime.value}|{context.bias. value}|"
                f"{context. time_window.value}|ADX:{context.regime_strength:. 0f}")
    
    def _create_skip_signal(self, reason: str, context:  MarketContext) -> AggregatedSignal:
        """Creates a SKIP decision signal."""
        self.signals_skipped += 1
        
        return AggregatedSignal(
            decision=TradeDecision.SKIP,
            direction=None,
            confluence_score=0,
            total_signals=0,
            agreeing_strategies=[],
            best_signal=None,
            suggested_size_multiplier=0,
            suggested_target=None,
            suggested_stop=None,
            market_context_summary=self._summarize_context(context),
            skip_reason=reason
        )
    
    def get_stats(self) -> dict:
        """Returns aggregation statistics."""
        total = self.signals_executed + self.signals_skipped
        return {
            'processed':  self.signals_processed,
            'executed': self.signals_executed,
            'skipped': self. signals_skipped,
            'execution_rate': (self.signals_executed / total * 100) if total > 0 else 0
        }
    
    def print_decision(self, agg_signal: AggregatedSignal):
        """Prints a formatted decision summary."""
        if agg_signal. decision == TradeDecision.EXECUTE: 
            icon = "🟢"
            direction = agg_signal.direction.value
        else:
            icon = "🔴"
            direction = "SKIP"
        
        print(f"\n{icon} SIGNAL AGGREGATOR DECISION")
        print(f"{'─'*40}")
        print(f"Direction:     {direction}")
        print(f"Confluence:   {agg_signal. confluence_score}")
        print(f"Strategies:   {', '.join(agg_signal.agreeing_strategies) or 'None'}")
        print(f"Size Mult:    {agg_signal.suggested_size_multiplier:. 2f}x")
        print(f"Context:      {agg_signal.market_context_summary}")
        if agg_signal. skip_reason:
            print(f"Skip Reason:  {agg_signal.skip_reason}")
        print(f"{'─'*40}\n")


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing Signal Aggregator.. .\n")
    
    # Mock config
    class MockConfig:
        class Confluence:
            MIN_SCORE_HIGH_CONFIDENCE = 5
            MIN_SCORE_MEDIUM_CONFIDENCE = 3
            MIN_SCORE_LOW_CONFIDENCE = 2
            WEIGHTS = {
                'strategy_signal': 1,
                'regime_alignment': 2,
                'bias_alignment': 1,
                'order_flow_confirmation':  2,
                'volume_confirmation': 1,
                'key_level_proximity': 1,
                'time_window_optimal': 1
            }
        class Exit:
            EXITS_BY_REGIME = {
                'TRENDING':  {'target': 15, 'stop':  5}
            }
    
    from market_intelligence.market_context import (
        MarketContextBuilder, OrderFlowState, VolatilityState, TimeWindow
    )
    
    aggregator = SignalAggregator(MockConfig())
    
    # Create mock signals
    signal1 = StrategySignal(
        signal_type=SignalType.BUY_CE,
        strength=SignalStrength. STRONG,
        reason="Test signal 1",
        strategy_name="Original",
        timeframe="1minute",
        regime="TRENDING_UP",
        bias="BULLISH",
        base_score=4,
        confluence_factors=["REGIME_ALIGNED", "BIAS_ALIGNED"]
    )
    
    signal2 = StrategySignal(
        signal_type=SignalType.BUY_CE,
        strength=SignalStrength. MODERATE,
        reason="Test signal 2",
        strategy_name="EMA_Crossover",
        timeframe="1minute",
        regime="TRENDING_UP",
        bias="BULLISH",
        base_score=3,
        confluence_factors=["ABOVE_VWAP"]
    )
    
    signal3 = StrategySignal(
        signal_type=SignalType.BUY_CE,
        strength=SignalStrength. MODERATE,
        reason="Test signal 3",
        strategy_name="Order_Flow",
        timeframe="1minute",
        regime="TRENDING_UP",
        bias="BULLISH",
        base_score=3,
        confluence_factors=["ORDER_FLOW"]
    )
    
    # Create context
    context = MarketContextBuilder()\
        .set_regime(MarketRegime. TRENDING_UP, 32, 15)\
        .set_bias(MarketBias.BULLISH, 45)\
        .set_time_window(TimeWindow.MORNING_SESSION, 280, False)\
        .set_volatility(VolatilityState.NORMAL, 45, 50, 50)\
        .set_order_flow(OrderFlowState(
            smart_money_direction="BULLISH",
            volume_state="HIGH"
        ))\
        .build()
    
    # Test aggregation
    print("Testing with 3 agreeing BUY_CE signals...")
    result = aggregator.aggregate([signal1, signal2, signal3], context)
    aggregator.print_decision(result)
    
    # Test conflict
    print("\nTesting with conflicting signals...")
    signal_pe = StrategySignal(
        signal_type=SignalType.BUY_PE,
        strength=SignalStrength.WEAK,
        reason="Bearish signal",
        strategy_name="VWAP_Bounce",
        timeframe="1minute",
        regime="RANGING",
        bias="NEUTRAL",
        base_score=2,
        confluence_factors=[]
    )
    
    result2 = aggregator.aggregate([signal1, signal2, signal_pe], context)
    aggregator.print_decision(result2)
    
    print(f"\nStats: {aggregator. get_stats()}")
    print("\n✅ Signal Aggregator Test Complete!")