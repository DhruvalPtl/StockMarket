"""
RISK MANAGER
Unified risk management across all strategies.

Key Functions:
1.Position limits (max concurrent positions)
2.Correlation management (don't overload one direction)
3.Daily loss limits
4.Position sizing based on volatility
5.Drawdown protection
6.Trade frequency limits

This ensures we don't blow up even if strategies go crazy.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime, date
from enum import Enum
import math

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.base_strategy import SignalType
from execution.signal_aggregator import AggregatedSignal, TradeDecision


class RiskAction(Enum):
    """Risk manager decisions."""
    ALLOW = "ALLOW"
    REDUCE_SIZE = "REDUCE_SIZE"
    BLOCK = "BLOCK"


@dataclass
class Position:
    """Represents an active position."""
    position_id: str
    strategy_name:  str
    timeframe: str
    direction: SignalType  # BUY_CE or BUY_PE
    strike: int
    entry_price: float
    entry_time: datetime
    quantity: int
    current_price: float = 0.0
    peak_price: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class RiskDecision:
    """Risk manager's decision on a trade."""
    action: RiskAction
    reason: str
    adjusted_size_multiplier: float  # Final size multiplier
    allowed_capital: float  # Maximum capital for this trade
    warnings: List[str] = field(default_factory=list)


@dataclass
class DailyStats:
    """Tracks daily trading statistics."""
    date: date
    trades_taken: int = 0
    trades_won: int = 0
    trades_lost: int = 0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    max_drawdown: float = 0.0
    peak_pnl: float = 0.0
    current_positions: int = 0
    ce_positions: int = 0
    pe_positions: int = 0


class RiskManager: 
    """
    Central Risk Management System.
    
    Enforces: 
    - Max 4 concurrent positions
    - Max 3 positions in same direction (CE or PE)
    - Max 1 position per strike
    - Daily loss limit (optional halt or log)
    - Position sizing based on volatility
    - Trade frequency limits
    """
    
    def __init__(self, config):
        self.config = config
        
        # Limits from config
        self.max_positions = config.Risk.MAX_CONCURRENT_POSITIONS
        self.max_same_direction = config.Risk.MAX_SAME_DIRECTION
        self.max_same_strike = config.Risk.MAX_SAME_STRIKE
        self.max_daily_trades = config.Risk.MAX_DAILY_TRADES
        self.max_daily_loss = config.Risk.MAX_DAILY_LOSS
        self.daily_loss_action = config.Risk.MAX_DAILY_LOSS_ACTION  # "HALT" or "LOG"
        
        # Capital settings
        self.capital_per_strategy = config.Risk.CAPITAL_PER_STRATEGY
        self.max_capital_usage = config.Risk.MAX_CAPITAL_USAGE_PCT
        self.lot_size = config.Risk.LOT_SIZE
        
        # Costs
        self.brokerage = config.Risk.BROKERAGE_PER_ORDER
        self.taxes = config.Risk.TAXES_PER_TRADE
        self.slippage = config.Risk.SLIPPAGE_POINTS
        
        # Active positions
        self.positions: Dict[str, Position] = {}
        self.position_counter = 0
        
        # Strikes in use
        self.active_strikes: Set[int] = set()
        
        # Daily tracking
        self.daily_stats = DailyStats(date=date.today())
        self.last_reset_date = date.today()
        
        # Halt flag
        self.is_halted = False
        self.halt_reason = ""
    
    def check_trade(self, agg_signal: AggregatedSignal, 
                    proposed_strike: int,
                    current_atr: float = 50) -> RiskDecision:
        """
        Main risk check method.
        
        Args:
            agg_signal:  Aggregated signal from SignalAggregator
            proposed_strike: Strike price for the option
            current_atr: Current ATR for volatility-based sizing
            
        Returns:
            RiskDecision with action and adjusted parameters
        """
        # Reset daily stats if new day
        self._check_daily_reset()
        
        warnings = []
        
        # 1.Check if halted
        if self.is_halted:
            return RiskDecision(
                action=RiskAction.BLOCK,
                reason=f"Trading halted:  {self.halt_reason}",
                adjusted_size_multiplier=0,
                allowed_capital=0
            )
        
        # 2.Check signal decision
        if agg_signal.decision != TradeDecision.EXECUTE:
            return RiskDecision(
                action=RiskAction.BLOCK,
                reason="Signal not executable",
                adjusted_size_multiplier=0,
                allowed_capital=0
            )
        
        # 3.Check position limits
        limit_check = self._check_position_limits(agg_signal.direction, proposed_strike)
        if limit_check.action == RiskAction.BLOCK: 
            return limit_check
        if limit_check.warnings:
            warnings.extend(limit_check.warnings)
        
        # 4.Check daily limits
        daily_check = self._check_daily_limits()
        if daily_check.action == RiskAction.BLOCK: 
            return daily_check
        if daily_check.warnings:
            warnings.extend(daily_check.warnings)
        
        # 5.Calculate position size
        size_mult = agg_signal.suggested_size_multiplier
        
        # Adjust for ATR/volatility
        size_mult = self._adjust_for_volatility(size_mult, current_atr)
        
        # Adjust for drawdown
        size_mult = self._adjust_for_drawdown(size_mult)
        
        # 6.Calculate allowed capital
        allowed_capital = self._calculate_allowed_capital(size_mult)
        
        return RiskDecision(
            action=RiskAction.ALLOW,
            reason="All checks passed",
            adjusted_size_multiplier=size_mult,
            allowed_capital=allowed_capital,
            warnings=warnings
        )
    
    def _check_position_limits(self, direction: SignalType, 
                               strike: int) -> RiskDecision: 
        """Checks position-related limits."""
        warnings = []
        
        # Count current positions
        total_positions = len(self.positions)
        ce_positions = sum(1 for p in self.positions.values() 
                          if p.direction == SignalType.BUY_CE)
        pe_positions = total_positions - ce_positions
        
        # Update daily stats
        self.daily_stats.current_positions = total_positions
        self.daily_stats.ce_positions = ce_positions
        self.daily_stats.pe_positions = pe_positions
        
        # Check max total positions
        if total_positions >= self.max_positions: 
            return RiskDecision(
                action=RiskAction.BLOCK,
                reason=f"Max positions reached ({total_positions}/{self.max_positions})",
                adjusted_size_multiplier=0,
                allowed_capital=0
            )
        
        # Check same direction limit
        if direction == SignalType.BUY_CE: 
            if ce_positions >= self.max_same_direction: 
                return RiskDecision(
                    action=RiskAction.BLOCK,
                    reason=f"Max CE positions reached ({ce_positions}/{self.max_same_direction})",
                    adjusted_size_multiplier=0,
                    allowed_capital=0
                )
            if ce_positions >= self.max_same_direction - 1:
                warnings.append("Near CE position limit")
        else:
            if pe_positions >= self.max_same_direction:
                return RiskDecision(
                    action=RiskAction.BLOCK,
                    reason=f"Max PE positions reached ({pe_positions}/{self.max_same_direction})",
                    adjusted_size_multiplier=0,
                    allowed_capital=0
                )
            if pe_positions >= self.max_same_direction - 1:
                warnings.append("Near PE position limit")
        
        # Check strike uniqueness
        if strike in self.active_strikes:
            if self.max_same_strike <= 1:
                return RiskDecision(
                    action=RiskAction.BLOCK,
                    reason=f"Already have position at strike {strike}",
                    adjusted_size_multiplier=0,
                    allowed_capital=0
                )
        
        return RiskDecision(
            action=RiskAction.ALLOW,
            reason="Position limits OK",
            adjusted_size_multiplier=1.0,
            allowed_capital=0,
            warnings=warnings
        )
    
    def _check_daily_limits(self) -> RiskDecision: 
        """Checks daily trading limits."""
        warnings = []
        
        # Check trade count
        if self.daily_stats.trades_taken >= self.max_daily_trades: 
            return RiskDecision(
                action=RiskAction.BLOCK,
                reason=f"Max daily trades reached ({self.daily_stats.trades_taken})",
                adjusted_size_multiplier=0,
                allowed_capital=0
            )
        
        if self.daily_stats.trades_taken >= self.max_daily_trades - 2:
            warnings.append(f"Near daily trade limit ({self.daily_stats.trades_taken}/{self.max_daily_trades})")
        
        # Check daily loss
        if self.daily_stats.net_pnl < -self.max_daily_loss:
            if self.daily_loss_action == "HALT":
                self.is_halted = True
                self.halt_reason = f"Daily loss limit hit (₹{abs(self.daily_stats.net_pnl):.0f})"
                return RiskDecision(
                    action=RiskAction.BLOCK,
                    reason=self.halt_reason,
                    adjusted_size_multiplier=0,
                    allowed_capital=0
                )
            else:
                warnings.append(f"⚠️ Daily loss limit exceeded (₹{abs(self.daily_stats.net_pnl):.0f})")
        
        # Warn if approaching loss limit
        if self.daily_stats.net_pnl < -self.max_daily_loss * 0.7:
            warnings.append(f"Approaching daily loss limit (₹{abs(self.daily_stats.net_pnl):.0f})")
        
        return RiskDecision(
            action=RiskAction.ALLOW,
            reason="Daily limits OK",
            adjusted_size_multiplier=1.0,
            allowed_capital=0,
            warnings=warnings
        )
    
    def _adjust_for_volatility(self, size_mult: float, atr: float) -> float:
        """
        Adjusts position size based on volatility.
        Higher ATR = smaller position.
        """
        # Baseline ATR (normal conditions) 
        baseline_atr = 50
                # Prevent division by zero
        if baseline_atr <= 0 or atr <= 0:
            return size_mult
        if atr > baseline_atr * 1.5:
            # High volatility - reduce size
            reduction = min(0.5, (atr / baseline_atr - 1) * 0.3)
            size_mult *= (1 - reduction)
        elif atr < baseline_atr * 0.7:
            # Low volatility - can increase slightly
            increase = min(0.2, (1 - atr / baseline_atr) * 0.2)
            size_mult *= (1 + increase)
        
        return size_mult
    
    def _adjust_for_drawdown(self, size_mult: float) -> float:
        """
        Reduces size when in drawdown.
        """
        if self.daily_stats.net_pnl < 0:
            # In drawdown
            drawdown_pct = abs(self.daily_stats.net_pnl) / self.capital_per_strategy
            
            if drawdown_pct > 0.1:  # More than 10% drawdown
                reduction = min(0.5, drawdown_pct * 2)
                size_mult *= (1 - reduction)
        
        return max(0.5, size_mult)  # Minimum 0.5x
    
    def _calculate_allowed_capital(self, size_mult: float) -> float:
        """
        Calculates maximum capital for this trade.
        """
        base_capital = self.capital_per_strategy * self.max_capital_usage
        return base_capital * size_mult
    
    def _check_daily_reset(self):
        """Resets daily stats if new trading day."""
        today = date.today()
        if today != self.last_reset_date:
            self.daily_stats = DailyStats(date=today)
            self.last_reset_date = today
            self.is_halted = False
            self.halt_reason = ""
    
    # ==================== POSITION MANAGEMENT ====================
    
    def register_position(self, strategy_name: str, timeframe: str,
                         direction:  SignalType, strike: int,
                         entry_price: float, quantity: int) -> str:
        """
        Registers a new position.
        
        Returns:
            Position ID
        """
        self.position_counter += 1
        pos_id = f"POS_{self.position_counter:04d}"
        
        position = Position(
            position_id=pos_id,
            strategy_name=strategy_name,
            timeframe=timeframe,
            direction=direction,
            strike=strike,
            entry_price=entry_price,
            entry_time=datetime.now(),
            quantity=quantity,
            current_price=entry_price,
            peak_price=entry_price
        )
        
        self.positions[pos_id] = position
        self.active_strikes.add(strike)
        self.daily_stats.trades_taken += 1
        
        return pos_id
    
    def update_position(self, pos_id: str, current_price: float):
        """Updates position with current price."""
        if pos_id not in self.positions:
            return
        
        pos = self.positions[pos_id]
        pos.current_price = current_price
        
        # Update peak
        if current_price > pos.peak_price: 
            pos.peak_price = current_price
        
        # Calculate unrealized PnL
        pos.unrealized_pnl = (current_price - pos.entry_price) * pos.quantity
    
    def close_position(self, pos_id: str, exit_price: float) -> float:
        """
        Closes a position and returns net PnL.
        """
        if pos_id not in self.positions:
            return 0.0
        
        pos = self.positions[pos_id]
        
        # Calculate PnL
        gross_pnl = (exit_price - pos.entry_price) * pos.quantity
        
        # Deduct costs
        total_costs = (self.brokerage * 2) + self.taxes + (self.slippage * pos.quantity)
        net_pnl = gross_pnl - total_costs
        
        # Update daily stats
        self.daily_stats.gross_pnl += gross_pnl
        self.daily_stats.net_pnl += net_pnl
        
        if net_pnl > 0:
            self.daily_stats.trades_won += 1
        else: 
            self.daily_stats.trades_lost += 1
        
        # Update peak/drawdown
        if self.daily_stats.net_pnl > self.daily_stats.peak_pnl:
            self.daily_stats.peak_pnl = self.daily_stats.net_pnl
        
        current_dd = self.daily_stats.peak_pnl - self.daily_stats.net_pnl
        if current_dd > self.daily_stats.max_drawdown: 
            self.daily_stats.max_drawdown = current_dd
        
        # Remove position
        self.active_strikes.discard(pos.strike)
        del self.positions[pos_id]
        
        return net_pnl
    
    def get_active_positions(self) -> List[Position]: 
        """Returns list of active positions."""
        return list(self.positions.values())
    
    def get_position_by_strategy(self, strategy_name: str) -> Optional[Position]: 
        """Gets position for a specific strategy (if any)."""
        for pos in self.positions.values():
            if pos.strategy_name == strategy_name:
                return pos
        return None
    
    # ==================== REPORTING ====================
    
    def get_daily_stats(self) -> DailyStats: 
        """Returns current daily statistics."""
        return self.daily_stats
    
    def print_status(self):
        """Prints current risk status."""
        stats = self.daily_stats
        
        print(f"\n{'='*50}")
        print(f"📊 RISK MANAGER STATUS")
        print(f"{'='*50}")
        print(f"Positions:     {len(self.positions)}/{self.max_positions} "
              f"(CE:{stats.ce_positions} PE:{stats.pe_positions})")
        print(f"Trades Today:  {stats.trades_taken}/{self.max_daily_trades}")
        print(f"Win/Loss:     {stats.trades_won}/{stats.trades_lost}")
        print(f"Net PnL:      ₹{stats.net_pnl:+,.2f}")
        print(f"Max Drawdown: ₹{stats.max_drawdown: ,.2f}")
        print(f"Halted:       {'YES - ' + self.halt_reason if self.is_halted else 'NO'}")
        print(f"{'='*50}\n")
    
    def get_risk_summary(self) -> dict:
        """Returns risk summary as dictionary."""
        return {
            'positions':  len(self.positions),
            'max_positions': self.max_positions,
            'ce_count': self.daily_stats.ce_positions,
            'pe_count': self.daily_stats.pe_positions,
            'trades_today': self.daily_stats.trades_taken,
            'win_rate': (self.daily_stats.trades_won / self.daily_stats.trades_taken * 100
                        if self.daily_stats.trades_taken > 0 else 0),
            'net_pnl': self.daily_stats.net_pnl,
            'max_drawdown': self.daily_stats.max_drawdown,
            'is_halted': self.is_halted
        }
    
    def reset_daily_stats(self):
        """Reset daily statistics for fresh trading session."""
        self.daily_stats = DailyStats(date=date.today())
        self.last_reset_date = date.today()
        self.positions.clear()
        self.active_strikes.clear()
        self.position_counter = 0


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing Risk Manager...\n")
    
    # Mock config
    class MockConfig:
        class Risk:
            CAPITAL_PER_STRATEGY = 10000.0
            MAX_CAPITAL_USAGE_PCT = 0.90
            LOT_SIZE = 75
            MAX_CONCURRENT_POSITIONS = 4
            MAX_SAME_DIRECTION = 3
            MAX_SAME_STRIKE = 1
            MAX_DAILY_TRADES = 20
            MAX_DAILY_LOSS = 5000
            MAX_DAILY_LOSS_ACTION = "LOG"
            BROKERAGE_PER_ORDER = 20.0
            TAXES_PER_TRADE = 15.0
            SLIPPAGE_POINTS = 1
        
        class Confluence:
            MIN_SCORE_HIGH_CONFIDENCE = 5
            MIN_SCORE_MEDIUM_CONFIDENCE = 3
            MIN_SCORE_LOW_CONFIDENCE = 2
    
    from execution.signal_aggregator import AggregatedSignal, TradeDecision
    from market_intelligence.market_context import TimeWindow, VolatilityState
    
    risk_mgr = RiskManager(MockConfig())
    
    # Create a mock aggregated signal
    agg_signal = AggregatedSignal(
        decision=TradeDecision.EXECUTE,
        direction=SignalType.BUY_CE,
        confluence_score=5,
        total_signals=3,
        agreeing_strategies=["Original", "EMA_Crossover", "Order_Flow"],
        best_signal=None,
        suggested_size_multiplier=1.0,
        suggested_target=15,
        suggested_stop=5,
        market_context_summary="TRENDING_UP|BULLISH"
    )
    
    # Test trade check
    print("Testing trade approval...")
    decision = risk_mgr.check_trade(agg_signal, proposed_strike=24000, current_atr=50)
    print(f"Action: {decision.action.value}")
    print(f"Reason: {decision.reason}")
    print(f"Size Multiplier: {decision.adjusted_size_multiplier:.2f}")
    print(f"Allowed Capital: ₹{decision.allowed_capital: ,.2f}")
    if decision.warnings:
        print(f"Warnings:  {decision.warnings}")
    
    # Register some positions
    print("\nRegistering positions...")
    pos1 = risk_mgr.register_position(
        "Original", "1minute", SignalType.BUY_CE, 24000, 150.0, 75
    )
    pos2 = risk_mgr.register_position(
        "EMA_Crossover", "1minute", SignalType.BUY_CE, 24100, 120.0, 75
    )
    print(f"Registered:  {pos1}, {pos2}")
    
    # Print status
    risk_mgr.print_status()
    
    # Try to add same strike (should block)
    print("Testing duplicate strike block...")
    decision2 = risk_mgr.check_trade(agg_signal, proposed_strike=24000, current_atr=50)
    print(f"Action: {decision2.action.value}")
    print(f"Reason: {decision2.reason}")
    
    # Close a position
    print("\nClosing position with profit...")
    pnl = risk_mgr.close_position(pos1, 165.0)  # Exit at profit
    print(f"Net PnL: ₹{pnl:+,.2f}")
    
    # Final status
    risk_mgr.print_status()
    
    print("\n✅ Risk Manager Test Complete!")