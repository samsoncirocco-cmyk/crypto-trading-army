#!/usr/bin/env python3
"""ETH Scout with REAL Coinbase price feeds"""
import os, json, time, signal, logging, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'eth_scout_live.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('eth-scout-live')

AGENT_ID = "eth-scout-live"
SIGNAL_DIR = Path(__file__).parent.parent / 'data' / 'signals'
RUNNING = True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))

sys.path.insert(0, str(Path(__file__).parent.parent))
from coinbase_legacy import CoinbaseLegacyClient

def analyze_trend_momentum(prices):
    """Detect trend momentum"""
    if len(prices) < 10:
        return None, 0
    
    # Simple moving average crossover
    sma_short = sum(prices[-5:]) / 5
    sma_long = sum(prices[-10:]) / 10
    current = prices[-1]
    
    if sma_short > sma_long * 1.005:  # Short above long by 0.5%
        return "LONG", 0.72
    elif sma_short < sma_long * 0.995:  # Short below long by 0.5%
        return "SHORT", 0.70
    
    return None, 0

def main():
    global RUNNING
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info("="*60)
    logger.info("🚀 ETH SCOUT LIVE - Real Price Feeds")
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
            
            price = client.get_product_price('ETH-USD')
            price_history.append(price)
            if len(price_history) > 20:
                price_history.pop(0)
            
            logger.info(f"📊 ETH: ${price:,.2f}")
            
            if cycle % 5 == 0 and len(price_history) >= 10:
                direction, confidence = analyze_trend_momentum(price_history)
                
                if direction and confidence > 0.7:
                    signal = {
                        'agent_id': AGENT_ID,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'asset': 'ETH-USD',
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
                    
                    logger.info(f"🚨 SIGNAL: {direction} ETH @ ${price:,.2f} (conf: {confidence:.0%})")
            
            time.sleep(14)
            
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
