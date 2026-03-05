#!/usr/bin/env python3
"""
Strategy Optimizer - Grid search for best parameters
"""
import json
import itertools
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass

@dataclass
class StrategyParams:
    entry_threshold: float  # 0.7, 0.75, 0.8
    exit_threshold: float   # 0.02, 0.03, 0.05
    position_size: float    # 5, 10, 15
    max_trades: int         # 2, 3, 5
    stop_loss: float        # 0.01, 0.02, 0.03

class StrategyOptimizer:
    """Grid search optimizer for trading strategies"""
    
    def __init__(self, data_dir='data/backtest'):
        self.data_dir = Path(data_dir)
        self.results = []
    
    def generate_param_grid(self):
        """Generate parameter combinations to test"""
        param_grid = {
            'entry_threshold': [0.75, 0.8, 0.85],
            'exit_threshold': [0.02, 0.03, 0.05],
            'position_size': [5, 10, 15],
            'max_trades': [2, 3, 5],
            'stop_loss': [0.01, 0.02, 0.03]
        }
        
        keys = param_grid.keys()
        values = param_grid.values()
        
        for combination in itertools.product(*values):
            yield dict(zip(keys, combination))
    
    def simulate_strategy(self, params, price_data):
        """Simulate strategy with given parameters"""
        equity = [10000]
        trades = []
        position = None
        daily_trades = 0
        
        for i, price in enumerate(price_data):
            # Reset daily count
            if i % 24 == 0:  # Assuming hourly data
                daily_trades = 0
            
            if daily_trades >= params['max_trades']:
                continue
            
            # Entry logic (simplified)
            if not position and self.should_enter(price, params):
                position = {
                    'entry': price,
                    'size': params['position_size']
                }
                daily_trades += 1
            
            # Exit logic
            elif position:
                change = (price - position['entry']) / position['entry']
                
                if change >= params['exit_threshold'] or change <= -params['stop_loss']:
                    pnl = position['size'] * change
                    equity.append(equity[-1] + pnl)
                    trades.append({
                        'pnl': pnl,
                        'return': change
                    })
                    position = None
        
        return {
            'final_equity': equity[-1],
            'total_return': (equity[-1] - equity[0]) / equity[0],
            'trades': len(trades),
            'win_rate': sum(1 for t in trades if t['pnl'] > 0) / len(trades) if trades else 0,
            'max_drawdown': self.calculate_drawdown(equity)
        }
    
    def should_enter(self, price, params):
        """Simplified entry condition"""
        import random
        return random.random() > params['entry_threshold']
    
    def calculate_drawdown(self, equity):
        """Calculate max drawdown"""
        peak = equity[0]
        max_dd = 0
        for val in equity[1:]:
            if val > peak:
                peak = val
            dd = (peak - val) / peak
            max_dd = max(max_dd, dd)
        return max_dd
    
    def run_optimization(self, price_data, top_n=5):
        """Run full grid search"""
        print("="*60)
        print("🔬 STRATEGY OPTIMIZATION")
        print("="*60)
        print(f"\nTesting {3**5} parameter combinations...")
        
        for params in self.generate_param_grid():
            result = self.simulate_strategy(params, price_data)
            result['params'] = params
            self.results.append(result)
        
        # Sort by return/drawdown ratio
        self.results.sort(
            key=lambda x: x['total_return'] / (x['max_drawdown'] + 0.001),
            reverse=True
        )
        
        print(f"\n📊 TOP {top_n} CONFIGURATIONS:")
        print("-"*60)
        
        for i, r in enumerate(self.results[:top_n], 1):
            print(f"\n#{i}:")
            print(f"   Return: {r['total_return']:.1%}")
            print(f"   Win Rate: {r['win_rate']:.1%}")
            print(f"   Trades: {r['trades']}")
            print(f"   Max DD: {r['max_drawdown']:.1%}")
            print(f"   Params: {r['params']}")
        
        # Save results
        with open('optimization_results.json', 'w') as f:
            json.dump(self.results[:20], f, indent=2)
        
        print(f"\n💾 Results saved to optimization_results.json")
        return self.results[0]

if __name__ == '__main__':
    import random
    
    # Generate synthetic price data
    price = 66000
    prices = []
    for _ in range(180 * 24):  # 6 months hourly
        price *= (1 + random.gauss(0.0001, 0.01))
        prices.append(price)
    
    optimizer = StrategyOptimizer()
    best = optimizer.run_optimization(prices, top_n=5)
    
    print("\n" + "="*60)
    print("✅ OPTIMIZATION COMPLETE")
    print("="*60)
