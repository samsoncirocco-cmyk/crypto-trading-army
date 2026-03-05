#!/usr/bin/env python3
"""BTC Scout with REAL Coinbase price feeds"""
import os, json, time, signal, logging, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'btc_scout_live.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('btc-scout-live')

AGENT_ID = "btc-scout-live"
SIGNAL_DIR = Path(__file__).parent.parent / 'data' / 'signals'
RUNNING = True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))

# Import client
sys.path.insert(0, str(Path(__file__).parent.parent))
from coinbase_legacy import CoinbaseLegacyClient

def analyze_liquidity_sweep(prices, volumes):
    """Detect liquidity sweep pattern"""
    if len(prices) < 5:
        return None, 0
    
    # Look for sweep below/above key level followed by reversal
    recent_low = min(prices[-5:])
    recent_high = max(prices[-5:])
    current = prices[-1]
    
    # Long setup: swept below recent low, now reversing up
    if prices[-2] == recent_low and current > prices[-2]:
        return "LONG", 0.75
    
    # Short setup: swept above recent high, now reversing down  
    if prices[-2] == recent_high and current < prices[-2]:
        return "SHORT", 0.72
    
    return None, 0

def main():
    global RUNNING
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info("="*60)
    logger.info("🚀 BTC SCOUT LIVE - Real Price Feeds")
    logger.info("="*60)
    
    try:
        client = CoinbaseLegacyClient()
        logger.info("✅ Coinbase client connected")
    except Exception as e:
        logger.error(f"❌ Coinbase connection failed: {e}")
        return
    
    price_history = []
    cycle = 0
    
    while RUNNING:
        try:
            cycle += 1
            
            # Fetch real BTC price
            price = client.get_product_price('BTC-USD')
            price_history.append(price)
            if len(price_history) > 20:
                price_history.pop(0)
            
            logger.info(f"📊 BTC: ${price:,.2f}")
            
            # Analyze for signals (every 5th cycle ~30-60 seconds)
            if cycle % 5 == 0 and len(price_history) >= 10:
                direction, confidence = analyze_liquidity_sweep(price_history, [])
                
                if direction and confidence > 0.7:
                    signal = {
                        'agent_id': AGENT_ID,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'asset': 'BTC-USD',
                        'direction': direction,
                        'confidence': round(confidence, 4),
                        'entry_price': round(price, 2),
                        'stop_loss': round(price * 0.98, 2),
                        'take_profit': round(price * 1.04, 2),
                        'source': 'live_feed',
                        'paper_mode': True
                    }
                    
                    with open(SIGNAL_DIR / f"signal_{AGENT_ID}_{int(time.time())}.json", 'w') as f:
                        json.dump(signal, f)
                    
                    logger.info(f"🚨 SIGNAL: {direction} BTC @ ${price:,.2f} (conf: {confidence:.0%})")
            
            time.sleep(12)  # Fetch every 12 seconds
            
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(30)
    
    logger.info(f"Stopped after {cycle} cycles")

if __name__ == '__main__':
    while True:
        try: main(); break
        except KeyboardInterrupt: break
        except Exception as e: 
            logger.critical(f"Crash: {e}")
            time.sleep(60)
