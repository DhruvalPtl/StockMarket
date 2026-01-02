"""
POSITION MANAGER - FIXED FOR REALISTIC TRADING
- Entries on NEXT candle after signal
- Exits on NEXT candle after trigger
- Realistic slippage added
- Transaction costs included
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass


@dataclass
class Position:
    """Represents an open position"""
    option_type: str          # "CE" or "PE"
    strike: int
    entry_price: float
    entry_time: datetime
    entry_spot: float
    entry_fut: float
    expiry: str
    quantity: int = 75
    peak_price: float = 0.0
    trailing_active: bool = False
    
    # NEW: Track signal time vs entry time
    signal_time: datetime = None
    
    def __post_init__(self):
        self.peak_price = self.entry_price


class PositionManager:
    """Manages position entry, exit, and trailing stop - REALISTIC VERSION"""
    
    def __init__(self, config, option_fetcher):
        self.config = config
        self.option_fetcher = option_fetcher
        self.position: Optional[Position] = None
        
        # Tracking
        self.last_exit_time: Optional[datetime] = None
        self.consecutive_losses: int = 0
        
        # Last strike search details (for logging)
        self.last_strike_search: Dict = {}
        
        # NEW: Pending entry signal
        self.pending_entry: Optional[Dict] = None
        
        # NEW: Exit triggered flag
        self.exit_triggered: bool = False
        self.exit_trigger_reason: str = ""
        self.exit_trigger_details: Dict = {}
    
    def has_position(self) -> bool:
        """Check if we have an open position"""
        return self.position is not None
    
    def has_pending_entry(self) -> bool:
        """Check if we have a pending entry for next candle"""
        return self.pending_entry is not None
    
    def is_in_cooldown(self, current_time: datetime) -> Tuple[bool, str]:
        """Check if we're in cooldown period"""
        if self.last_exit_time is None:
            return False, ""
        
        # Normal cooldown
        cooldown_seconds = self.config.cooldown_seconds
        
        # Extended cooldown after consecutive losses
        if self.consecutive_losses >= 2:
            cooldown_seconds = self.config.cooldown_after_loss_seconds
        
        elapsed = (current_time - self.last_exit_time).total_seconds()
        
        if elapsed < cooldown_seconds:
            remaining = int(cooldown_seconds - elapsed)
            return True, f"COOLDOWN_{remaining}s_remaining"
        
        return False, ""
    
    def get_last_strike_search(self) -> Dict:
        """Get details of last strike search for logging"""
        return self.last_strike_search
    
    def signal_entry(self, signal: str, row: pd.Series) -> Tuple[bool, Dict]:
        """
        STEP 1: Signal detected - prepare entry for NEXT candle
        
        Returns:
            (success, details)
        """
        option_type = "CE" if signal == "BUY_CE" else "PE"
        atm_strike = int(row['atm_strike'])
        current_time = row['datetime']
        spot_price = row['close']
        fut_price = row['fut_close']
        
        # Find affordable strike (with detailed logging)
        result = self._find_strike_detailed(
            atm_strike=atm_strike,
            option_type=option_type,
            current_time=current_time,
            spot_price=spot_price
        )
        
        if result is None:
            return False, {
                "reason": "NO_AFFORDABLE_STRIKE",
                **self.last_strike_search
            }
        
        # Store pending entry for NEXT candle
        self.pending_entry = {
            "signal": signal,
            "option_type": option_type,
            "strike": result['strike'],
            "strike_type": result['strike_type'],
            "expiry": result['expiry'],
            "signal_time": current_time,
            "signal_spot": spot_price,
            "signal_fut": fut_price,
            "expected_price": result['price']  # For logging
        }
        
        return True, {
            "status": "ENTRY_PENDING",
            "strike": result['strike'],
            "strike_type": result['strike_type'],
            "expected_price": result['price'],
            "expiry": result['expiry'],
            **self.last_strike_search
        }
    
    def execute_pending_entry(self, row: pd.Series) -> Tuple[bool, Dict]:
        """
        STEP 2: Execute entry at CURRENT candle (next after signal)
        
        Returns:
            (success, details)
        """
        if self.pending_entry is None:
            return False, {"reason": "NO_PENDING_ENTRY"}
        
        current_time = row['datetime']
        
        # Get actual entry price at THIS candle
        option_data = self.option_fetcher.get_option_price(
            strike=self.pending_entry['strike'],
            option_type=self.pending_entry['option_type'],
            dt=current_time
        )
        
        if option_data is None:
            self.pending_entry = None
            return False, {"reason": "NO_OPTION_PRICE_AT_ENTRY"}
        
        # REALISTIC: Entry price with slippage
        base_entry_price = option_data['close']
        entry_slippage = 0.5  # 0.5 point slippage on entry
        actual_entry_price = base_entry_price + entry_slippage
        
        # Check if still affordable with actual price
        entry_cost = actual_entry_price * self.config.lot_size
        max_cost = self.config.capital * 0.95
        
        if entry_cost > max_cost:
            self.pending_entry = None
            return False, {"reason": "NOT_AFFORDABLE_AT_ACTUAL_PRICE"}
        
        # Create position
        self.position = Position(
            option_type=self.pending_entry['option_type'],
            strike=self.pending_entry['strike'],
            entry_price=actual_entry_price,
            entry_time=current_time,
            entry_spot=row['close'],
            entry_fut=row['fut_close'],
            expiry=self.pending_entry['expiry'],
            signal_time=self.pending_entry['signal_time']
        )
        
        details = {
            "strike": self.pending_entry['strike'],
            "strike_type": self.pending_entry['strike_type'],
            "entry_price": actual_entry_price,
            "entry_cost": entry_cost,
            "expiry": self.pending_entry['expiry'],
            "option_type": self.pending_entry['option_type'],
            "signal_time": self.pending_entry['signal_time'],
            "entry_time": current_time,
            "entry_delay_seconds": (current_time - self.pending_entry['signal_time']).total_seconds(),
            "expected_price": self.pending_entry['expected_price'],
            "actual_price": actual_entry_price,
            "entry_slippage": entry_slippage
        }
        
        # Clear pending entry
        self.pending_entry = None
        
        return True, details
    
    def _find_strike_detailed(self, atm_strike: int, option_type: str,
                               current_time: datetime, spot_price: float) -> Optional[Dict]:
        """
        Find an affordable strike with detailed logging
        """
        # Reset search details
        self.last_strike_search = {
            "search_atm_strike": atm_strike,
            "search_option_type": option_type,
            "search_spot_price": round(spot_price, 2),
            "search_capital": round(self.config.capital, 2),
            "search_max_cost": round(self.config.capital * 0.95, 2),
            "search_min_price": self.config.min_option_price,
            "search_max_price": self.config.max_option_price,
            "strikes_tried": "",
            "strike_1_price": "",
            "strike_1_cost": "",
            "strike_1_status": "",
            "strike_2_price": "",
            "strike_2_cost": "",
            "strike_2_status": "",
            "strike_3_price": "",
            "strike_3_cost": "",
            "strike_3_status": "",
            "strike_4_price": "",
            "strike_4_cost": "",
            "strike_4_status": "",
            "expiry_used": "",
            "failure_reason": ""
        }
        
        # Strikes to try: ATM, then OTM, then more OTM
        if option_type == "CE":
            strikes_to_try = [
                (atm_strike, "ATM"),
                (atm_strike + 50, "OTM1"),
                (atm_strike + 100, "OTM2"),
                (atm_strike - 50, "ITM")
            ]
        else:  # PE
            strikes_to_try = [
                (atm_strike, "ATM"),
                (atm_strike - 50, "OTM1"),
                (atm_strike - 100, "OTM2"),
                (atm_strike + 50, "ITM")
            ]
        
        tried_strikes = []
        max_cost = self.config.capital * 0.95
        
        for idx, (strike, strike_type) in enumerate(strikes_to_try, 1):
            tried_strikes.append(f"{strike}({strike_type})")
            
            # Get option data
            data = self.option_fetcher.get_option_price(
                strike=strike,
                option_type=option_type,
                dt=current_time
            )
            
            # Log this strike attempt
            strike_key = f"strike_{idx}"
            
            if data is None:
                self.last_strike_search[f"{strike_key}_price"] = "NOT_FOUND"
                self.last_strike_search[f"{strike_key}_cost"] = "N/A"
                self.last_strike_search[f"{strike_key}_status"] = "NO_DATA"
                continue
            
            price = data['close']
            cost = price * self.config.lot_size
            
            self.last_strike_search[f"{strike_key}_price"] = round(price, 2)
            self.last_strike_search[f"{strike_key}_cost"] = round(cost, 2)
            self.last_strike_search["expiry_used"] = data['expiry']
            
            # Check price limits
            if price < self.config.min_option_price:
                self.last_strike_search[f"{strike_key}_status"] = f"TOO_CHEAP(<{self.config.min_option_price})"
                continue
            
            if price > self.config.max_option_price:
                self.last_strike_search[f"{strike_key}_status"] = f"TOO_EXPENSIVE(>{self.config.max_option_price})"
                continue
            
            # Check affordability
            if cost > max_cost:
                self.last_strike_search[f"{strike_key}_status"] = f"UNAFFORDABLE(>{max_cost:.0f})"
                continue
            
            # Found a valid strike!
            self.last_strike_search[f"{strike_key}_status"] = "SELECTED"
            self.last_strike_search["strikes_tried"] = " | ".join(tried_strikes)
            self.last_strike_search["failure_reason"] = ""
            
            return {
                "strike": strike,
                "strike_type": strike_type,
                "price": price,
                "expiry": data['expiry']
            }
        
        # No valid strike found
        self.last_strike_search["strikes_tried"] = " | ".join(tried_strikes)
        self.last_strike_search["failure_reason"] = "ALL_STRIKES_FAILED"
        
        return None
    
    def check_exit(self, row: pd.Series) -> Tuple[bool, str, Dict]:
        """
        STEP 1: Check if exit should be triggered (don't exit yet)
        
        Returns:
            (should_exit, reason, details)
        """
        if self.position is None:
            return False, "", {}
        
        current_time = row['datetime']
        
        # Get current option price
        data = self.option_fetcher.get_option_price(
            strike=self.position.strike,
            option_type=self.position.option_type,
            dt=current_time
        )
        
        if data is None:
            return False, "", {"error": "PRICE_NOT_FOUND"}
        
        current_price = data['close']
        entry_price = self.position.entry_price
        
        # Calculate P&L
        pnl_points = current_price - entry_price
        pnl_rupees = pnl_points * self.config.lot_size
        
        # Update peak price
        if current_price > self.position.peak_price:
            self.position.peak_price = current_price
        
        # Check trailing activation
        if pnl_points >= self.config.trailing_trigger_points:
            self.position.trailing_active = True
        
        details = {
            "current_price": current_price,
            "entry_price": entry_price,
            "pnl_points": round(pnl_points, 2),
            "pnl_rupees": round(pnl_rupees, 2),
            "peak_price": self.position.peak_price,
            "trailing_active": self.position.trailing_active,
            "drop_from_peak": round(self.position.peak_price - current_price, 2)
        }
        
        # EXIT CHECK 1: Stop Loss
        if pnl_points <= -self.config.stop_loss_points:
            self.exit_triggered = True
            self.exit_trigger_reason = "STOP_LOSS"
            self.exit_trigger_details = details
            return True, "STOP_LOSS", details
        
        # EXIT CHECK 2: Target
        if pnl_points >= self.config.target_points:
            self.exit_triggered = True
            self.exit_trigger_reason = "TARGET"
            self.exit_trigger_details = details
            return True, "TARGET", details
        
        # EXIT CHECK 3: Trailing Stop
        if self.position.trailing_active:
            drop_from_peak = self.position.peak_price - current_price
            if drop_from_peak >= self.config.trailing_stop_points:
                details["drop_from_peak"] = round(drop_from_peak, 2)
                self.exit_triggered = True
                self.exit_trigger_reason = "TRAILING_STOP"
                self.exit_trigger_details = details
                return True, "TRAILING_STOP", details
        
        # EXIT CHECK 4: Time Exit
        hold_minutes = (current_time - self.position.entry_time).total_seconds() / 60
        if hold_minutes >= self.config.max_hold_minutes:
            details["hold_minutes"] = round(hold_minutes, 1)
            self.exit_triggered = True
            self.exit_trigger_reason = "TIME_EXIT"
            self.exit_trigger_details = details
            return True, "TIME_EXIT", details
        
        # EXIT CHECK 5: EOD Exit
        exit_time = datetime.strptime(self.config.force_exit_time, "%H:%M").time()
        if current_time.time() >= exit_time:
            self.exit_triggered = True
            self.exit_trigger_reason = "EOD_EXIT"
            self.exit_trigger_details = details
            return True, "EOD_EXIT", details
        
        return False, "", details
    
    def execute_exit(self, row: pd.Series) -> Optional[Dict]:
        """
        STEP 2: Execute exit at NEXT candle after trigger
        
        Returns:
            Trade summary dict
        """
        if not self.exit_triggered or self.position is None:
            return None
        
        current_time = row['datetime']
        
        # Get actual exit price at THIS candle
        data = self.option_fetcher.get_option_price(
            strike=self.position.strike,
            option_type=self.position.option_type,
            dt=current_time
        )
        
        if data is None:
            # Can't exit without price - hold for now
            return None
        
        base_exit_price = data['close']
        
        # REALISTIC: Exit slippage depends on reason
        if self.exit_trigger_reason in ["STOP_LOSS", "EOD_EXIT"]:
            exit_slippage = -1.0  # Negative slippage (worse price)
        elif self.exit_trigger_reason == "TARGET":
            exit_slippage = -0.5  # Less slippage at target
        else:
            exit_slippage = -0.75  # Trailing stop
        
        actual_exit_price = base_exit_price + exit_slippage
        
        # Calculate final P&L
        pnl_points = actual_exit_price - self.position.entry_price
        pnl_rupees = pnl_points * self.config.lot_size
        
        # REALISTIC: Transaction costs
        transaction_cost = 40  # ₹20 entry + ₹20 exit brokerage
        stt = abs(actual_exit_price * self.config.lot_size) * 0.0005  # STT on sell
        total_cost = transaction_cost + stt
        
        pnl_rupees_net = pnl_rupees - total_cost
        
        hold_minutes = (current_time - self.position.entry_time).total_seconds() / 60
        
        # Track consecutive losses
        if pnl_rupees_net < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        trade_summary = {
            "option_type": self.position.option_type,
            "strike": self.position.strike,
            "entry_time": self.position.entry_time,
            "entry_price": self.position.entry_price,
            "entry_spot": self.position.entry_spot,
            "entry_fut": self.position.entry_fut,
            "exit_time": current_time,
            "exit_price": actual_exit_price,
            "exit_reason": self.exit_trigger_reason,
            "pnl_points": round(pnl_points, 2),
            "pnl_rupees_gross": round(pnl_rupees, 2),
            "transaction_cost": round(total_cost, 2),
            "pnl_rupees": round(pnl_rupees_net, 2),
            "hold_minutes": round(hold_minutes, 1),
            "is_winner": pnl_rupees_net > 0,
            "peak_price": self.position.peak_price,
            "expiry": self.position.expiry,
            "exit_slippage": exit_slippage,
            "signal_time": self.position.signal_time,
            "entry_delay": round((self.position.entry_time - self.position.signal_time).total_seconds(), 1) if self.position.signal_time else 0
        }
        
        # Record exit time for cooldown
        self.last_exit_time = current_time
        
        # Clear position and exit trigger
        self.position = None
        self.exit_triggered = False
        self.exit_trigger_reason = ""
        self.exit_trigger_details = {}
        
        return trade_summary
    
    def get_position_status(self, row: pd.Series) -> Dict:
        """Get current position status for logging"""
        if self.position is None:
            return {"has_position": False}
        
        # Get current price
        data = self.option_fetcher.get_option_price(
            strike=self.position.strike,
            option_type=self.position.option_type,
            dt=row['datetime']
        )
        
        current_price = data['close'] if data else 0
        pnl_points = current_price - self.position.entry_price
        pnl_rupees = pnl_points * self.config.lot_size
        hold_minutes = (row['datetime'] - self.position.entry_time).total_seconds() / 60
        
        return {
            "has_position": True,
            "option_type": self.position.option_type,
            "strike": self.position.strike,
            "entry_price": self.position.entry_price,
            "current_price": current_price,
            "pnl_points": round(pnl_points, 2),
            "pnl_rupees": round(pnl_rupees, 2),
            "peak_price": self.position.peak_price,
            "trailing_active": self.position.trailing_active,
            "drop_from_peak": round(self.position.peak_price - current_price, 2),
            "hold_minutes": round(hold_minutes, 1),
            "exit_triggered": self.exit_triggered,
            "exit_trigger_reason": self.exit_trigger_reason if self.exit_triggered else ""
        }
