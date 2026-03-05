#!/usr/bin/env python3
"""
ML-Enhanced Signals - Pattern recognition with simple models
"""
import json
import statistics
from pathlib import Path
from collections import deque
from datetime import datetime, timezone

class SimpleMLScout:
    """Pattern recognition without heavy ML dependencies"""
    
    def __init__(self, lookback=50):
        self.lookback = lookback
        self.price_history = deque(maxlen=lookback)
        self.volume_history = deque(maxlen=lookback)
    
    def add_data(self, price, volume=0):
        """Add price/volume data point"""
        self.price_history.append(price)
        self.volume_history.append(volume)
    
    def calculate_features(self):
        """Calculate technical features"""
        if len(self.price_history) < 20:
            return None
        
        prices = list(self.price_history)
        
        # Price-based features
        returns = [(prices[i] - prices[i-1]) / prices[i-1] 
                   for i in range(1, len(prices))]
        
        # Moving averages
        sma_5 = statistics.mean(prices[-5:])
        sma_20 = statistics.mean(prices[-20:])
        
        # Volatility (standard deviation of returns)
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0
        
        # Trend strength
        trend = (prices[-1] - prices[-20]) / prices[-20]
        
        # Momentum
        momentum = prices[-1] / prices[-5] - 1
        
        # RSI approximation
        gains = [r for r in returns if r > 0]
        losses = [abs(r) for r in returns if r < 0]
        avg_gain = statistics.mean(gains) if gains else 0
        avg_loss = statistics.mean(losses) if losses else 0.001  # Avoid div by zero
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return {
            'current_price': prices[-1],
            'sma_5': sma_5,
            'sma_20': sma_20,
            'volatility': volatility,
            'trend_20d': trend,
            'momentum_5d': momentum,
            'rsi': rsi,
            'price_vs_sma5': prices[-1] / sma_5 - 1,
            'price_vs_sma20': prices[-1] / sma_20 - 1
        }
    
    def predict_signal(self) -> dict:
        """Generate signal based on features"""
        features = self.calculate_features()
        
        if not features:
            return {'signal': 'NEUTRAL', 'confidence': 0.5, 'reason': 'Insufficient data'}
        
        score = 0
        reasons = []
        
        # Trend following
        if features['trend_20d'] > 0.05:
            score += 2
            reasons.append("Uptrend")
        elif features['trend_20d'] < -0.05:
            score -= 2
            reasons.append("Downtrend")
        
        # Momentum
        if features['momentum_5d'] > 0.02:
            score += 1
            reasons.append("Positive momentum")
        elif features['momentum_5d'] < -0.02:
            score -= 1
            reasons.append("Negative momentum")
        
        # RSI
        if features['rsi'] < 30:
            score += 2
            reasons.append("Oversold (RSI)")
        elif features['rsi'] > 70:
            score -= 2
            reasons.append("Overbought (RSI)")
        
        # Moving average crossover
        if features['price_vs_sma5'] > 0 and features['price_vs_sma20'] > 0:
            score += 1
            reasons.append("Above MAs")
        elif features['price_vs_sma5'] < 0 and features['price_vs_sma20'] < 0:
            score -= 1
            reasons.append("Below MAs")
        
        # Volatility filter
        if features['volatility'] > 0.05:
            score *= 0.8  # Reduce confidence in high volatility
            reasons.append("High vol")
        
        # Determine signal
        if score >= 3:
            signal = 'STRONG_BUY'
            confidence = min(0.5 + abs(score) * 0.1, 0.95)
        elif score >= 1:
            signal = 'BUY'
            confidence = min(0.5 + abs(score) * 0.1, 0.85)
        elif score <= -3:
            signal = 'STRONG_SELL'
            confidence = min(0.5 + abs(score) * 0.1, 0.95)
        elif score <= -1:
            signal = 'SELL'
            confidence = min(0.5 + abs(score) * 0.1, 0.85)
        else:
            signal = 'NEUTRAL'
            confidence = 0.5
        
        return {
            'signal': signal,
            'confidence': round(confidence, 2),
            'score': score,
            'features': features,
            'reasons': reasons,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

if __name__ == '__main__':
    import random
    
    # Simulate price data
    scout = SimpleMLScout(lookback=50)
    price = 66000
    
    for _ in range(60):
        price *= (1 + random.gauss(0.001, 0.02))
        scout.add_data(price, random.randint(1000000, 5000000))
    
    result = scout.predict_signal()
    print(json.dumps(result, indent=2))
