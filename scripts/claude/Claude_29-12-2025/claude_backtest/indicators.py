"""
INDICATORS - RSI, EMA calculations on SPOT data
Fixed RSI using Wilder's Smoothing
"""

import pandas as pd
import numpy as np
from typing import Tuple


class Indicators: 
    """Calculate technical indicators on SPOT data"""
    
    def __init__(self, config):
        self.config = config
    
    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all indicators
        
        Uses: 
        - SPOT (close) for RSI, EMA
        - FUTURES (fut_close) only for VWAP comparison
        """
        df = df.copy()
        
        # Ensure datetime
        if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
            df['datetime'] = pd.to_datetime(df['datetime'])
        
        # RSI on SPOT
        # Use continuous calculation (across days) for better backtest accuracy
        # Daily reset would match TradingView but is less accurate for backtesting
        df['rsi'] = self._calculate_rsi_wilders(df['close'], self.config.rsi_period)
        
        # EMAs on SPOT
        df['ema_fast'] = df['close'].ewm(span=self.config.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.config.ema_slow, adjust=False).mean()
        
        # Candle color on SPOT
        df['candle_green'] = df['close'] > df['open']
        df['candle_body'] = abs(df['close'] - df['open'])
        
        # FUTURES vs VWAP
        df['fut_above_vwap'] = df['fut_close'] > df['vwap']
        df['fut_below_vwap'] = df['fut_close'] < df['vwap']
        
        # Previous values for VWAP cross detection
        df['prev_fut_above_vwap'] = df['fut_above_vwap'].shift(1)
        
        # EMA crossover
        df['ema_bullish'] = df['ema_fast'] > df['ema_slow']
        df['ema_bearish'] = df['ema_fast'] < df['ema_slow']
        
        # SPOT vs EMA
        df['spot_above_ema_fast'] = df['close'] > df['ema_fast']
        df['spot_below_ema_fast'] = df['close'] < df['ema_fast']
        
        # ATM strike based on SPOT
        df['atm_strike'] = (df['close'] / 50).round() * 50
        df['atm_strike'] = df['atm_strike'].astype(int)
        
        # RSI warmup flag (need 14+ candles)
        df['indicators_ready'] = df.index >= self.config.rsi_period
        
        return df
    
    def _calculate_rsi_wilders(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate RSI using Wilder's Smoothing - Manual Implementation
        
        This matches TradingView exactly:
        1. Calculate price changes (delta)
        2. Separate gains and losses
        3. First avg = Simple average of first 'period' gains/losses
        4. After that: avg = (prev_avg * (period-1) + current_value) / period
        """
        # Calculate price changes
        delta = prices.diff()
        
        # Separate gains and losses
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        # Initialize result array
        rsi = pd.Series(index=prices.index, dtype=float)
        rsi[:] = 50.0  # Default to neutral
        
        # Need at least period+1 values (period for SMA + 1 for diff)
        if len(prices) < period + 1:
            return rsi
        
        # Calculate first average (simple average of first 'period' values)
        first_avg_gain = gain.iloc[1:period+1].mean()  # Skip first NaN from diff
        first_avg_loss = loss.iloc[1:period+1].mean()
        
        # Initialize running averages
        avg_gain = first_avg_gain
        avg_loss = first_avg_loss
        
        # Calculate RSI for first valid point
        if avg_loss == 0:
            rsi.iloc[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi.iloc[period] = 100 - (100 / (1 + rs))
        
        # Calculate RSI for remaining points using Wilder's smoothing
        for i in range(period + 1, len(prices)):
            # Wilder's smoothing: new_avg = (prev_avg * (period-1) + current_value) / period
            avg_gain = (avg_gain * (period - 1) + gain.iloc[i]) / period
            avg_loss = (avg_loss * (period - 1) + loss.iloc[i]) / period
            
            if avg_loss == 0:
                rsi.iloc[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi.iloc[i] = 100 - (100 / (1 + rs))
        
        return rsi
    
    def resample_to_timeframe(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Resample 1-min data to higher timeframe
        
        Args:
            df: DataFrame with 1-min data
            timeframe: "1min", "3min", or "5min"
        """
        if timeframe == "1min":
            return df
        
        minutes = int(timeframe.replace("min", ""))
        
        df = df.copy()
        df = df.set_index('datetime')
        
        # Resample OHLC
        resampled = df.resample(f'{minutes}T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'fut_open': 'first',
            'fut_high': 'max',
            'fut_low': 'min',
            'fut_close': 'last',
            'volume': 'sum',
            'oi': 'last',
            'vwap': 'last'  # Use last VWAP value
        }).dropna()
        
        resampled = resampled.reset_index()
        
        return resampled