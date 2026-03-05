#!/usr/bin/env python3
"""
BTC Scout Agent - Monitors BTC for liquidity sweeps
"""

import sys
import time
import json
from datetime import datetime, timezone
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from coinbase_advanced import CoinbaseAdvancedClient
from liquidity_sweep_engine import LiquiditySweepEngine

AGENT_ID = "btc-scout-1"
ASSET = "BTC-USD"

def main():
    print(f"[{AGENT_ID}] BTC Scout Agent starting...")
    
    client = CoinbaseAdvancedClient()
    engine = LiquiditySweepEngine(
        sweep_lookback=15,
        min_sweep_wick_ratio=1.8,
        volume_threshold=1.3,
        sl_percent=0.02,
        tp_percent=0.04
    )
    
    # Initial price fetch to detect pattern
    last_price = None
    price_history = []
    
    print(f"[{AGENT_ID}] Monitoring {ASSET} for liquidity sweeps...")
    
    while True:
        try:
            # Get current price
            current_price = client.get_product_price(ASSET)
            
            if last_price:
                # Simple sweep detection (enhanced version would use full OHLC)
                change_pct = (current_price - last_price) / last_price
                
                # Detect sweep pattern
                if abs(change_pct) > 0.005:  # 0.5% move
                    print(f"[{AGENT_ID}] Price move detected: {change_pct:+.2%}")
                    
                    # Build mock signal
                    signal = {
                        'agent_id': AGENT_ID,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'asset': ASSET,
                        'direction': 'LONG' if change_pct < 0 else 'SHORT',
                        'confidence': 0.75,
                        'entry_price': current_price,
                        'stop_loss': current_price * 0.98,
                        'take_profit': current_price * 1.04
                    }
                    
                    # Write to signal file
                    signal_file = Path(__file__).parent.parent / 'data' / 'signals' / f"{AGENT_ID}_{int(time.time())}.json"
                    with open(signal_file, 'w') as f:
                        json.dump(signal, f)
                    
                    print(f"[{AGENT_ID}] SIGNAL: {signal['direction']} {ASSET} @ ${current_price:,.2f}")
            
            last_price = current_price
            price_history.append(current_price)
            
            # Keep only last 100 prices
            if len(price_history) > 100:
                price_history = price_history[-100:]
            
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            print(f"[{AGENT_ID}] Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
