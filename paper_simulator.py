#!/usr/bin/env python3
"""
Paper Trading Simulator - Simulates fills without Coinbase API
For testing strategy without real money
"""
import os, json, time, random
from datetime import datetime, timezone
from pathlib import Path

class PaperTradingSimulator:
    """Simulates market orders and tracks P&L"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.trades_file = data_dir / 'paper_trades.jsonl'
        self.positions = {}  # asset -> position
        self.daily_pnl = 0
        
    def place_market_order(self, asset: str, side: str, size_usd: float, entry_price: float):
        """Simulate a market order fill"""
        
        # Simulate slippage (0.1% - 0.3%)
        slippage = random.uniform(0.001, 0.003)
        
        if side.upper() == 'BUY':
            fill_price = entry_price * (1 + slippage)
        else:
            fill_price = entry_price * (1 - slippage)
        
        # Calculate position size in asset units
        position_size = size_usd / fill_price
        
        trade = {
            'trade_id': f"paper_{int(time.time())}_{asset.replace('-', '')}",
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'asset': asset,
            'side': side.upper(),
            'size_usd': size_usd,
            'position_size': round(position_size, 8),
            'entry_price': round(fill_price, 2),
            'slippage': round(slippage * 100, 3),
            'status': 'FILLED',
            'paper_mode': True
        }
        
        # Track position
        if side.upper() == 'BUY':
            self.positions[asset] = {
                'size': position_size,
                'entry': fill_price,
                'side': 'LONG'
            }
        else:
            self.positions[asset] = {
                'size': position_size,
                'entry': fill_price,
                'side': 'SHORT'
            }
        
        # Save trade
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.trades_file, 'a') as f:
            f.write(json.dumps(trade) + '\n')
        
        return trade
    
    def close_position(self, asset: str, exit_price: float):
        """Close a position and calculate P&L"""
        if asset not in self.positions:
            return None
        
        pos = self.positions[asset]
        
        if pos['side'] == 'LONG':
            pnl_pct = (exit_price - pos['entry']) / pos['entry']
        else:
            pnl_pct = (pos['entry'] - exit_price) / pos['entry']
        
        pnl_usd = pos['size'] * pos['entry'] * pnl_pct
        
        trade = {
            'trade_id': f"paper_close_{int(time.time())}_{asset.replace('-', '')}",
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'asset': asset,
            'side': 'SELL' if pos['side'] == 'LONG' else 'BUY',
            'exit_price': round(exit_price, 2),
            'entry_price': round(pos['entry'], 2),
            'pnl_usd': round(pnl_usd, 2),
            'pnl_pct': round(pnl_pct * 100, 2),
            'status': 'CLOSED',
            'paper_mode': True
        }
        
        self.daily_pnl += pnl_usd
        del self.positions[asset]
        
        # Save trade
        with open(self.trades_file, 'a') as f:
            f.write(json.dumps(trade) + '\n')
        
        return trade
    
    def get_stats(self):
        """Get trading statistics"""
        if not self.trades_file.exists():
            return {'trades': 0, 'pnl': 0}
        
        trades = []
        with open(self.trades_file) as f:
            for line in f:
                try: trades.append(json.loads(line))
                except: pass
        
        closed = [t for t in trades if t.get('status') == 'CLOSED']
        total_pnl = sum(t.get('pnl_usd', 0) for t in closed)
        winners = sum(1 for t in closed if t.get('pnl_usd', 0) > 0)
        
        return {
            'trades': len(trades),
            'closed': len(closed),
            'winners': winners,
            'pnl': round(total_pnl, 2),
            'win_rate': round(winners / len(closed), 2) if closed else 0
        }

if __name__ == '__main__':
    # Test
    sim = PaperTradingSimulator(Path('./data/paper'))
    
    # Simulate a trade
    trade = sim.place_market_order('BTC-USD', 'BUY', 10.0, 66214.61)
    print(f"Entered: {trade}")
    
    # Simulate close with profit
    close = sim.close_position('BTC-USD', 68800.00)
    print(f"Closed: {close}")
    
    print(f"\nStats: {sim.get_stats()}")
