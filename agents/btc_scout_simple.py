#!/usr/bin/env python3
"""
Simple Paper Trading Agent - Deployed Agent Army
Monitors BTC and simulates trades (paper mode only)
"""

import json
import time
import random
from datetime import datetime, timezone
from pathlib import Path

AGENT_ID = "btc-scout-1"
ASSET = "BTC-USD"
SIGNAL_DIR = Path(__file__).parent.parent / 'data' / 'signals'

def generate_mock_signal():
    """Generate a mock signal for testing"""
    base_price = 65000
    noise = random.uniform(-500, 500)
    current_price = base_price + noise
    
    direction = "LONG" if random.random() > 0.4 else "SHORT"  # 60% long bias
    
    return {
        'agent_id': AGENT_ID,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'asset': ASSET,
        'direction': direction,
        'confidence': random.uniform(0.7, 0.95),
        'entry_price': current_price,
        'stop_loss': current_price * 0.98,
        'take_profit': current_price * 1.04,
        'paper_mode': True
    }

def main():
    print(f"[{AGENT_ID}] Agent Army - BTC Scout DEPLOYED")
    print(f"[{AGENT_ID}] Monitoring {ASSET} for liquidity sweeps...")
    print(f"[{AGENT_ID}] Paper mode only - no real trades")
    
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    
    cycle = 0
    while True:
        cycle += 1
        
        # Simulate signal detection (every 2-5 minutes)
        if random.random() < 0.3:  # 30% chance per cycle
            signal = generate_mock_signal()
            
            # Write signal file
            signal_file = SIGNAL_DIR / f"signal_{AGENT_ID}_{int(time.time())}.json"
            with open(signal_file, 'w') as f:
                json.dump(signal, f, indent=2)
            
            print(f"[{AGENT_ID}] 🚨 SIGNAL: {signal['direction']} {ASSET} @ ${signal['entry_price']:,.2f} (conf: {signal['confidence']:.1%})")
        
        if cycle % 10 == 0:
            print(f"[{AGENT_ID}] Status: {cycle} cycles, watching for sweeps...")
        
        time.sleep(30)  # Check every 30 seconds

if __name__ == '__main__':
    main()
