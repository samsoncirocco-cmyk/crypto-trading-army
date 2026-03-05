#!/usr/bin/env python3
"""
Liquidity Sweep Engine - Core strategy logic for Crypto God John style trading

Detects liquidity sweeps on lower timeframes with higher timeframe confluence.
Implements asymmetric risk/reward with strict risk management.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class SignalStrength(Enum):
    WEAK = 1
    MODERATE = 2
    STRONG = 3

@dataclass
class SweepSignal:
    """Represents a detected liquidity sweep signal"""
    timestamp: datetime
    direction: TradeDirection
    pair: str
    entry_price: float
    stop_loss: float
    take_profit: float
    strength: SignalStrength
    sweep_low: float
    sweep_high: float
    volume_ratio: float
    htf_aligned: bool
    
    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk/reward ratio"""
        if self.direction == TradeDirection.LONG:
            risk = self.entry_price - self.stop_loss
            reward = self.take_profit - self.entry_price
        else:
            risk = self.stop_loss - self.entry_price
            reward = self.entry_price - self.take_profit
        
        if risk == 0:
            return 0
        return reward / risk

class LiquiditySweepEngine:
    """
    Detects liquidity sweeps for high-probability scalping entries
    
    Strategy Rules:
    - 1m/5m timeframe for sweep detection
    - 15m/1h trend alignment required
    - Stop loss: 1.2% from entry
    - Take profit: 2.4% from entry (2:1 RR)
    - Max 2-3 trades/day
    """
    
    def __init__(self, 
                 sweep_lookback: int = 20,
                 min_sweep_wick_ratio: float = 2.0,
                 volume_threshold: float = 1.5,
                 sl_percent: float = 0.012,
                 tp_percent: float = 0.024):
        """
        Args:
            sweep_lookback: Bars to look back for liquidity levels
            min_sweep_wick_ratio: Min wick/body ratio for sweep detection
            volume_threshold: Min volume ratio vs average
            sl_percent: Stop loss percentage (1.2%)
            tp_percent: Take profit percentage (2.4%)
        """
        self.sweep_lookback = sweep_lookback
        self.min_sweep_wick_ratio = min_sweep_wick_ratio
        self.volume_threshold = volume_threshold
        self.sl_percent = sl_percent
        self.tp_percent = tp_percent
    
    def detect_sweeps(self, 
                      df_1m: pd.DataFrame, 
                      df_5m: pd.DataFrame,
                      df_15m: pd.DataFrame,
                      pair: str) -> List[SweepSignal]:
        """
        Detect liquidity sweeps across multiple timeframes
        
        Args:
            df_1m: 1-minute OHLCV data
            df_5m: 5-minute OHLCV data  
            df_15m: 15-minute OHLCV data
            pair: Trading pair (e.g., 'BTC-USD')
        
        Returns:
            List of SweepSignal objects
        """
        signals = []
        
        # Calculate higher timeframe trend
        htf_trend = self._calculate_htf_trend(df_15m)
        
        # Calculate volume average for 1m
        df_1m['volume_sma'] = df_1m['volume'].rolling(20).mean()
        
        # Find liquidity zones from recent swing highs/lows
        liquidity_levels = self._find_liquidity_levels(df_5m)
        
        # Scan for sweeps on 1m data
        for i in range(self.sweep_lookback, len(df_1m)):
            candle = df_1m.iloc[i]
            
            # Check volume
            if candle['volume'] < candle['volume_sma'] * self.volume_threshold:
                continue
            
            # Check for sweep pattern
            sweep_long = self._is_sweep_long(candle, liquidity_levels)
            sweep_short = self._is_sweep_short(candle, liquidity_levels)
            
            if sweep_long and htf_trend in ['up', 'neutral']:
                signal = self._create_signal(
                    df_1m.index[i], 
                    TradeDirection.LONG,
                    pair,
                    candle,
                    htf_trend == 'up'
                )
                if signal:
                    signals.append(signal)
            
            elif sweep_short and htf_trend in ['down', 'neutral']:
                signal = self._create_signal(
                    df_1m.index[i],
                    TradeDirection.SHORT,
                    pair,
                    candle,
                    htf_trend == 'down'
                )
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _calculate_htf_trend(self, df: pd.DataFrame) -> str:
        """Calculate higher timeframe trend using EMA alignment"""
        if len(df) < 50:
            return 'neutral'
        
        df = df.copy()
        df['ema_9'] = df['close'].ewm(span=9).mean()
        df['ema_21'] = df['close'].ewm(span=21).mean()
        df['ema_50'] = df['close'].ewm(span=50).mean()
        
        last = df.iloc[-1]
        
        if last['ema_9'] > last['ema_21'] > last['ema_50']:
            return 'up'
        elif last['ema_9'] < last['ema_21'] < last['ema_50']:
            return 'down'
        return 'neutral'
    
    def _find_liquidity_levels(self, df: pd.DataFrame) -> dict:
        """Find recent swing highs and lows as liquidity levels"""
        if len(df) < self.sweep_lookback:
            return {'swing_highs': [], 'swing_lows': []}
        
        swing_highs = []
        swing_lows = []
        
        # Simple swing detection
        for i in range(2, len(df) - 2):
            # Swing high
            if (df.iloc[i]['high'] > df.iloc[i-1]['high'] and 
                df.iloc[i]['high'] > df.iloc[i-2]['high'] and
                df.iloc[i]['high'] > df.iloc[i+1]['high'] and
                df.iloc[i]['high'] > df.iloc[i+2]['high']):
                swing_highs.append(df.iloc[i]['high'])
            
            # Swing low
            if (df.iloc[i]['low'] < df.iloc[i-1]['low'] and
                df.iloc[i]['low'] < df.iloc[i-2]['low'] and
                df.iloc[i]['low'] < df.iloc[i+1]['low'] and
                df.iloc[i]['low'] < df.iloc[i+2]['low']):
                swing_lows.append(df.iloc[i]['low'])
        
        return {
            'swing_highs': swing_highs[-5:],  # Last 5
            'swing_lows': swing_lows[-5:]
        }
    
    def _is_sweep_long(self, candle: pd.Series, levels: dict) -> bool:
        """Check if candle shows long sweep pattern"""
        # Wick below body
        lower_wick = candle['open'] - candle['low'] if candle['close'] > candle['open'] else candle['close'] - candle['low']
        body = abs(candle['close'] - candle['open'])
        
        if body == 0:
            return False
        
        # Wick ratio check
        wick_ratio = lower_wick / body if body > 0 else 0
        if wick_ratio < self.min_sweep_wick_ratio:
            return False
        
        # Check if we swept near a liquidity level
        for level in levels['swing_lows']:
            if abs(candle['low'] - level) / level < 0.005:  # Within 0.5%
                return True
        
        return False
    
    def _is_sweep_short(self, candle: pd.Series, levels: dict) -> bool:
        """Check if candle shows short sweep pattern"""
        # Wick above body
        upper_wick = candle['high'] - candle['close'] if candle['close'] > candle['open'] else candle['high'] - candle['open']
        body = abs(candle['close'] - candle['open'])
        
        if body == 0:
            return False
        
        # Wick ratio check
        wick_ratio = upper_wick / body if body > 0 else 0
        if wick_ratio < self.min_sweep_wick_ratio:
            return False
        
        # Check if we swept near a liquidity level
        for level in levels['swing_highs']:
            if abs(candle['high'] - level) / level < 0.005:  # Within 0.5%
                return True
        
        return False
    
    def _create_signal(self, 
                       timestamp: datetime,
                       direction: TradeDirection,
                       pair: str,
                       candle: pd.Series,
                       htf_aligned: bool) -> Optional[SweepSignal]:
        """Create a trade signal from detected sweep"""
        
        entry_price = candle['close']
        
        if direction == TradeDirection.LONG:
            stop_loss = entry_price * (1 - self.sl_percent)
            take_profit = entry_price * (1 + self.tp_percent)
            sweep_low = candle['low']
            sweep_high = candle['high']
        else:
            stop_loss = entry_price * (1 + self.sl_percent)
            take_profit = entry_price * (1 - self.tp_percent)
            sweep_low = candle['low']
            sweep_high = candle['high']
        
        # Calculate signal strength
        strength = SignalStrength.MODERATE
        if htf_aligned:
            strength = SignalStrength.STRONG
        elif candle['volume'] > candle.get('volume_sma', 0) * 2:
            strength = SignalStrength.WEAK
        
        return SweepSignal(
            timestamp=timestamp,
            direction=direction,
            pair=pair,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strength=strength,
            sweep_low=sweep_low,
            sweep_high=sweep_high,
            volume_ratio=candle['volume'] / candle.get('volume_sma', candle['volume']),
            htf_aligned=htf_aligned
        )

def main():
    """Test the engine with sample data"""
    print("Liquidity Sweep Engine loaded")
    print("Risk parameters: 1.2% SL / 2.4% TP (2:1 RR)")

if __name__ == '__main__':
    main()
