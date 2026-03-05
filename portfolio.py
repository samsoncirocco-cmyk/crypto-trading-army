#!/usr/bin/env python3
"""
Portfolio Manager - Multi-asset allocation and rebalancing
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List

@dataclass
class Position:
    asset: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    allocation_pct: float

@dataclass
class PortfolioState:
    total_value: float
    cash: float
    positions: Dict[str, Position]
    target_allocations: Dict[str, float]
    last_rebalance: str

class PortfolioManager:
    """Manage multi-asset portfolio with rebalancing"""
    
    # Target allocations (can be adjusted)
    DEFAULT_TARGETS = {
        'BTC-USD': 0.40,  # 40% BTC
        'ETH-USD': 0.30,  # 30% ETH
        'SOL-USD': 0.20,  # 20% SOL
        'CASH': 0.10      # 10% cash
    }
    
    REBALANCE_THRESHOLD = 0.05  # Rebalance if drift > 5%
    
    def __init__(self, data_dir='data/portfolio'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / 'portfolio_state.json'
        self.history_file = self.data_dir / 'portfolio_history.jsonl'
        self.state = self.load_state()
    
    def load_state(self) -> PortfolioState:
        """Load portfolio from disk"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
                return PortfolioState(**data)
        
        # Initialize new portfolio
        return PortfolioState(
            total_value=10000.0,
            cash=10000.0,
            positions={},
            target_allocations=self.DEFAULT_TARGETS.copy(),
            last_rebalance=datetime.now(timezone.utc).isoformat()
        )
    
    def save_state(self):
        """Save portfolio to disk"""
        with open(self.state_file, 'w') as f:
            json.dump(asdict(self.state), f, indent=2)
        
        # Append to history
        with open(self.history_file, 'a') as f:
            f.write(json.dumps({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_value': self.state.total_value,
                'cash': self.state.cash,
                'positions': {k: asdict(v) for k, v in self.state.positions.items()}
            }) + '\n')
    
    def update_prices(self, prices: Dict[str, float]):
        """Update position values with current prices"""
        total_value = self.state.cash
        
        for asset, position in self.state.positions.items():
            if asset in prices:
                position.current_price = prices[asset]
                position.market_value = position.quantity * position.current_price
                position.unrealized_pnl = (
                    position.market_value - position.quantity * position.avg_price
                )
                total_value += position.market_value
        
        self.state.total_value = total_value
        
        # Update allocation percentages
        for asset, position in self.state.positions.items():
            position.allocation_pct = position.market_value / total_value if total_value > 0 else 0
    
    def check_rebalance_needed(self) -> List[Dict]:
        """Check which positions need rebalancing"""
        rebalance_needed = []
        
        for asset, target in self.state.target_allocations.items():
            if asset == 'CASH':
                current = self.state.cash / self.state.total_value if self.state.total_value > 0 else 0
            else:
                position = self.state.positions.get(asset)
                current = position.allocation_pct if position else 0
            
            drift = abs(current - target)
            
            if drift > self.REBALANCE_THRESHOLD:
                rebalance_needed.append({
                    'asset': asset,
                    'current': current,
                    'target': target,
                    'drift': drift,
                    'action': 'REDUCE' if current > target else 'INCREASE'
                })
        
        return rebalance_needed
    
    def generate_rebalance_orders(self) -> List[Dict]:
        """Generate orders to rebalance portfolio"""
        orders = []
        
        for item in self.check_rebalance_needed():
            asset = item['asset']
            target_value = item['target'] * self.state.total_value
            
            if asset == 'CASH':
                current_value = self.state.cash
            else:
                position = self.state.positions.get(asset)
                current_value = position.market_value if position else 0
            
            diff = target_value - current_value
            
            if abs(diff) > 10:  # Minimum $10 trade
                orders.append({
                    'asset': asset,
                    'side': 'BUY' if diff > 0 else 'SELL',
                    'value_usd': abs(diff),
                    'reason': f"Rebalance: {item['drift']:.1%} drift"
                })
        
        return orders
    
    def buy(self, asset: str, quantity: float, price: float):
        """Execute buy order"""
        cost = quantity * price
        
        if cost > self.state.cash:
            raise ValueError(f"Insufficient cash: {self.state.cash} < {cost}")
        
        self.state.cash -= cost
        
        if asset in self.state.positions:
            # Update existing position
            pos = self.state.positions[asset]
            total_qty = pos.quantity + quantity
            pos.avg_price = (pos.quantity * pos.avg_price + cost) / total_qty
            pos.quantity = total_qty
        else:
            # New position
            self.state.positions[asset] = Position(
                asset=asset,
                quantity=quantity,
                avg_price=price,
                current_price=price,
                market_value=cost,
                unrealized_pnl=0,
                allocation_pct=0
            )
        
        self.save_state()
    
    def sell(self, asset: str, quantity: float, price: float):
        """Execute sell order"""
        if asset not in self.state.positions:
            raise ValueError(f"No position in {asset}")
        
        pos = self.state.positions[asset]
        
        if quantity > pos.quantity:
            raise ValueError(f"Insufficient quantity: {pos.quantity} < {quantity}")
        
        proceeds = quantity * price
        self.state.cash += proceeds
        
        if quantity == pos.quantity:
            del self.state.positions[asset]
        else:
            pos.quantity -= quantity
            pos.market_value = pos.quantity * price
        
        self.save_state()
    
    def get_summary(self) -> Dict:
        """Get portfolio summary"""
        return {
            'total_value': round(self.state.total_value, 2),
            'cash': round(self.state.cash, 2),
            'cash_pct': round(self.state.cash / self.state.total_value, 4) if self.state.total_value > 0 else 0,
            'positions': len(self.state.positions),
            'unrealized_pnl': round(
                sum(p.unrealized_pnl for p in self.state.positions.values()), 2
            ),
            'last_rebalance': self.state.last_rebalance
        }

if __name__ == '__main__':
    pm = PortfolioManager()
    
    # Update with current prices
    pm.update_prices({
        'BTC-USD': 66500,
        'ETH-USD': 3450,
        'SOL-USD': 145
    })
    
    print("Portfolio Summary:")
    print(json.dumps(pm.get_summary(), indent=2))
    
    print("\nRebalance Check:")
    rebalance = pm.check_re