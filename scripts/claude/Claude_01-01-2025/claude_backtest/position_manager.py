"""
POSITION MANAGER - Entry, Exit, Trailing Stop logic
With detailed logging for strike selection
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass


@dataclass
class Position:
    """Represents an open position"""
    option_type: str          # "CE" or "PE"
    strike:  int
    entry_price: float
    entry_time:  datetime
    entry_spot: float
    entry_fut: float
    expiry:  str
    quantity: int = 75
    peak_price: float = 0.0
    trailing_active: bool = False
    
    def __post_init__(self):
        self.peak_price = self.entry_price


class PositionManager:
    """Manages position entry, exit, and trailing stop"""
    
    def __init__(self, config, option_fetcher):
        self.config = config
        self.option_fetcher = option_fetcher
        self.position:  Optional[Position] = None
        
        # Tracking
        self.last_exit_time: Optional[datetime] = None
        self.consecutive_losses: int = 0
        
        # Last strike search details (for logging)
        self.last_strike_search: Dict = {}
    
    def has_position(self) -> bool:
        """Check if we have an open position"""
        return self.position is not None
    
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
    
    def enter_position(self, signal:  str, row: pd.Series) -> Tuple[bool, Dict]:
        """
        Enter a new position
        
        Args:
            signal:  "BUY_CE" or "BUY_PE"
            row: Current data row
        
        Returns: 
            (success, details_dict)
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
                **self.last_strike_search  # Include all search details
            }
        
        # Create position
        self.position = Position(
            option_type=option_type,
            strike=result['strike'],
            entry_price=result['price'],
            entry_time=current_time,
            entry_spot=spot_price,
            entry_fut=fut_price,
            expiry=result['expiry']
        )
        
        return True, {
            "strike": result['strike'],
            "strike_type": result['strike_type'],
            "entry_price": result['price'],
            "entry_cost": result['price'] * self.config.lot_size,
            "expiry": result['expiry'],
            "option_type": option_type,
            **self.last_strike_search  # Include all search details
        }
    
    def _find_strike_detailed(self, atm_strike: int, option_type: str,
                               current_time: datetime, spot_price:  float) -> Optional[Dict]:
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
        
        # Strikes to try:  ATM, then OTM, then more OTM
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
                "strike_type":  strike_type,
                "price": price,
                "expiry": data['expiry']
            }
        
        # No valid strike found
        self.last_strike_search["strikes_tried"] = " | ".join(tried_strikes)
        self.last_strike_search["failure_reason"] = "ALL_STRIKES_FAILED"
        
        return None
    
    def check_exit(self, row: pd.Series) -> Tuple[bool, str, Dict]:
        """
        Check if we should exit current position
        
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
            "entry_price":  entry_price,
            "pnl_points": round(pnl_points, 2),
            "pnl_rupees":  round(pnl_rupees, 2),
            "peak_price": self.position.peak_price,
            "trailing_active": self.position.trailing_active,
            "drop_from_peak": round(self.position.peak_price - current_price, 2)
        }
        
        # EXIT CHECK 1: Stop Loss
        if pnl_points <= -self.config.stop_loss_points: 
            return True, "STOP_LOSS", details
        
        # EXIT CHECK 2: Target
        if pnl_points >= self.config.target_points:
            return True, "TARGET", details
        
        # EXIT CHECK 3: Trailing Stop
        if self.position.trailing_active: 
            drop_from_peak = self.position.peak_price - current_price
            if drop_from_peak >= self.config.trailing_stop_points: 
                details["drop_from_peak"] = round(drop_from_peak, 2)
                return True, "TRAILING_STOP", details
        
        # EXIT CHECK 4: Time Exit
        hold_minutes = (current_time - self.position.entry_time).total_seconds() / 60
        if hold_minutes >= self.config.max_hold_minutes:
            details["hold_minutes"] = round(hold_minutes, 1)
            return True, "TIME_EXIT", details
        
        # EXIT CHECK 5: EOD Exit
        exit_time = datetime.strptime(self.config.force_exit_time, "%H:%M").time()
        if current_time.time() >= exit_time:
            return True, "EOD_EXIT", details
        
        return False, "", details
    
    def exit_position(self, reason: str, exit_price: float, exit_time: datetime) -> Dict:
        """
        Exit current position
        
        Returns:
            Trade summary dict
        """
        if self.position is None:
            return {}
        
        pnl_points = exit_price - self.position.entry_price
        pnl_rupees = pnl_points * self.config.lot_size
        hold_minutes = (exit_time - self.position.entry_time).total_seconds() / 60
        
        # Track consecutive losses
        if pnl_rupees < 0:
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
            "exit_time": exit_time,
            "exit_price": exit_price,
            "exit_reason": reason,
            "pnl_points": round(pnl_points, 2),
            "pnl_rupees": round(pnl_rupees, 2),
            "hold_minutes": round(hold_minutes, 1),
            "is_winner": pnl_rupees > 0,
            "peak_price": self.position.peak_price,
            "expiry": self.position.expiry
        }
        
        # Record exit time for cooldown
        self.last_exit_time = exit_time
        
        # Clear position
        self.position = None
        
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
            "drop_from_peak":  round(self.position.peak_price - current_price, 2),
            "hold_minutes": round(hold_minutes, 1)
        }