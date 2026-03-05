#!/usr/bin/env python3
"""
Regime Detector - Market Condition Classification

Detects market regimes (trending, ranging, high/low volatility)
for adaptive strategy behavior.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"

class RegimeDetector:
    """
    Detects market regimes using multiple indicators:
    - ADX for trend strength
    - ATR for volatility
    - Bollinger Band width
    - Volume profile
    """
    
    def __init__(self,
                 adx_period: int = 14,
                 adx_threshold: int = 25,
                 atr_period: int = 14,
                 bb_period: int = 20,
                 vol_lookback: int = 20):
        """
        Args:
            adx_period: Period for ADX calculation
            adx_threshold: ADX > threshold = trending
            atr_period: Period for ATR calculation
            bb_period: Bollinger Bands period
            vol_lookback: Lookback for volatility comparison
        """
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.atr_period = atr_period
        self.bb_period = bb_period
        self.vol_lookback = vol_lookback
    
    def detect_regime(self, df: pd.DataFrame) -> Dict:
        """
        Detect current market regime from price data
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            Dict with regime classification and metrics
        """
        if len(df) < self.bb_period + 10:
            return {'regime': MarketRegime.RANGING, 'confidence': 0.5}
        
        # Calculate indicators
        adx = self._calculate_adx(df)
        atr = self._calculate_atr(df)
        bb_width = self._calculate_bb_width(df)
        
        # Current values
        current_adx = adx.iloc[-1]
        current_atr = atr.iloc[-1]
        current_bb_width = bb_width.iloc[-1]
        
        # Volatility comparison
        atr_mean = atr.rolling(self.vol_lookback).mean().iloc[-1]
        is_high_vol = current_atr > atr_mean * 1.5
        is_low_vol = current_atr < atr_mean * 0.5
        
        # Trend direction
        sma_short = df['close'].rolling(10).mean().iloc[-1]
        sma_long = df['close'].rolling(30).mean().iloc[-1]
        
        is_uptrend = sma_short > sma_long
        is_downtrend = sma_short < sma_long
        
        # Determine regime
        regime = None
        confidence = 0.5
        
        if is_high_vol:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = min(current_atr / (atr_mean * 2), 1.0)
        elif is_low_vol:
            regime = MarketRegime.LOW_VOLATILITY
            confidence = min(1.0 - (current_atr / atr_mean), 1.0)
        elif current_adx > self.adx_threshold:
            if is_uptrend:
                regime = MarketRegime.TRENDING_UP
                confidence = (current_adx - self.adx_threshold) / 50
            else:
                regime = MarketRegime.TRENDING_DOWN
                confidence = (current_adx - self.adx_threshold) / 50
        else:
            regime = MarketRegime.RANGING
            confidence = (self.adx_threshold - current_adx) / self.adx_threshold
        
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            'regime': regime,
            'regime_name': regime.value,
            'confidence': confidence,
            'metrics': {
                'adx': current_adx,
                'atr': current_atr,
                'atr_vs_mean': current_atr / atr_mean if atr_mean > 0 else 1.0,
                'bb_width': current_bb_width,
                'is_uptrend': is_uptrend,
                'is_downtrend': is_downtrend
            }
        }
    
    def get_strategy_adjustments(self, regime: MarketRegime) -> Dict:
        """
        Get strategy parameter adjustments for current regime
        
        Returns dict with adjusted parameters
        """
        base_params = {
            'sweep_lookback': 20,
            'min_sweep_wick_ratio': 2.0,
            'volume_threshold': 1.5,
            'position_size_pct': 0.02,
            'max_trades_per_day': 3
        }
        
        adjustments = {
            MarketRegime.TRENDING_UP: {
                'bias': 'long',
                'position_size_pct': 0.025,  # Increase size
                'min_sweep_wick_ratio': 1.8,  # Easier entry
                'max_trades_per_day': 4
            },
            MarketRegime.TRENDING_DOWN: {
                'bias': 'short',
                'position_size_pct': 0.025,
                'min_sweep_wick_ratio': 1.8,
                'max_trades_per_day': 4
            },
            MarketRegime.RANGING: {
                'bias': 'neutral',
                'position_size_pct': 0.015,  # Reduce size
                'min_sweep_wick_ratio': 2.5,  # Stricter entry
                'max_trades_per_day': 2
            },
            MarketRegime.HIGH_VOLATILITY: {
                'bias': 'neutral',
                'position_size_pct': 0.01,  # Significant reduction
                'min_sweep_wick_ratio': 3.0,  # Very strict
                'max_trades_per_day': 2
            },
            MarketRegime.LOW_VOLATILITY: {
                'bias': 'neutral',
                'position_size_pct': 0.015,
                'min_sweep_wick_ratio': 2.0,
                'max_trades_per_day': 2  # Fewer opportunities
            }
        }
        
        regime_adjustments = adjustments.get(regime, {})
        return {**base_params, **regime_adjustments}
    
    def _calculate_adx(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average Directional Index"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Directional Movement
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        plus_dm[plus_dm <= minus_dm] = 0
        minus_dm[minus_dm <= plus_dm] = 0
        
        # Smoothed
        atr = tr.rolling(self.adx_period).mean()
        plus_di = 100 * plus_dm.rolling(self.adx_period).mean() / atr
        minus_di = 100 * minus_dm.rolling(self.adx_period).mean() / atr
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(self.adx_period).mean()
        
        return adx
    
    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(self.atr_period).mean()
        return atr
    
    def _calculate_bb_width(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Bollinger Band width"""
        sma = df['close'].rolling(self.bb_period).mean()
        std = df['close'].rolling(self.bb_period).std()
        
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        
        width = (upper - lower) / sma
        return width
    
    def regime_performance_matrix(self, 
                                   df: pd.DataFrame,
                                   signals: list) -> pd.DataFrame:
        """
        Calculate win rate by regime
        
        Returns performance matrix as DataFrame
        """
        results = []
        
        for i in range(len(df) - 1):
            window = df.iloc[max(0, i-50):i+1]
            regime_info = self.detect_regime(window)
            
            # Check if there was a signal at this bar
            # (simplified - in real impl would match timestamps)
            
            results.append({
                'timestamp': df.index[i],
                'regime': regime_info['regime_name'],
                'confidence': regime_info['confidence']
            })
        
        return pd.DataFrame(results)

if __name__ == '__main__':
    print("Regime Detector loaded")
    print("Detects: trending_up, trending_down, ranging, high_vol, low_vol")
