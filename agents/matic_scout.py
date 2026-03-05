#!/usr/bin/env python3
"""MATIC Scout Agent - Agent Army"""
import os, json, time, signal, logging, sys, random
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'matic_scout.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('matic-scout')

AGENT_ID, SIGNAL_DIR, RUNNING = "matic-scout-1", Path(__file__).parent.parent / 'data' / 'signals', True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))

def generate_signal():
    base = 0.65
    price = base + random.uniform(-0.05, 0.05)
    return {
        'agent_id': AGENT_ID, 'timestamp': datetime.now(timezone.utc).isoformat(),
        'asset': 'MATIC-USD', 'direction': "LONG" if random.random() > 0.42 else "SHORT",
        'confidence': round(random.uniform(0.66, 0.86), 4),
        'entry_price': round(price, 4), 'stop_loss': round(price * 0.97, 4),
        'take_profit': round(price * 1.06, 4), 'paper_mode': True
    }

def main():
    global RUNNING
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("="*50 + f"\n🤖 {AGENT_ID} DEPLOYED\n" + "="*50)
    cycle = signals = 0
    while RUNNING:
        try:
            cycle += 1
            if os.urandom(1)[0] / 255 < 0.32:
                sig = generate_signal()
                with open(SIGNAL_DIR / f"signal_{AGENT_ID}_{int(time.time())}.json", 'w') as f:
                    json.dump(sig, f)
                signals += 1
                logger.info(f"🚨 SIGNAL: {sig['direction']} MATIC @ ${sig['entry_price']:.4f}")
            if cycle % 10 == 0: logger.info(f"Status: {cycle} cycles, {signals} signals")
            for _ in range(29): time.sleep(1); 
            if not RUNNING: break
        except Exception as e: logger.error(f"Error: {e}"); time.sleep(5)
    logger.info(f"Stopped. Cycles: {cycle}, Signals: {signals}")

if __name__ == '__main__':
    while True:
        try: main(); break
        except KeyboardInterrupt: break
        except Exception as e: logger.critical(f"Crash: {e}"); time.sleep(10)
