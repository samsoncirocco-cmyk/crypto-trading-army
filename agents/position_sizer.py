#!/usr/bin/env python3
"""Position Sizer - Kelly Criterion position sizing"""
import os, json, time, signal, logging, sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'position_sizer.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('position-sizer')

QUEUE_DIR = Path(__file__).parent.parent / 'data'
RUNNING = True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))

def calculate_position(trade):
    """Apply Kelly Criterion sizing"""
    win_rate = 0.35  # Conservative
    avg_win = 0.04   # 4%
    avg_loss = 0.02  # 2%
    
    kelly = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
    kelly = max(0.01, min(kelly * 0.25, 0.05))  # Half-Kelly, max 5%
    
    trade['position_size'] = round(kelly, 4)
    trade['usd_amount'] = round(10000 * kelly, 2)  # Assuming $10k portfolio
    return trade

def main():
    global RUNNING
    logger.info("="*50 + "\n📐 POSITION SIZER DEPLOYED\n" + "="*50)
    while RUNNING:
        try:
            queue_file = QUEUE_DIR / 'trade_queue.jsonl'
            if queue_file.exists():
                with open(queue_file) as f:
                    lines = f.readlines()
                sized = []
                for line in lines:
                    try:
                        trade = json.loads(line)
                        if 'position_size' not in trade:
                            trade = calculate_position(trade)
                            logger.info(f"📐 Sized: {trade['asset']} @ {trade['position_size']:.2%} = ${trade['usd_amount']}")
                        sized.append(json.dumps(trade))
                    except: sized.append(line.strip())
                with open(queue_file, 'w') as f:
                    f.write('\n'.join(sized) + '\n')
            time.sleep(30)
        except Exception as e: logger.error(f"Error: {e}"); time.sleep(5)

if __name__ == '__main__':
    while True:
        try: main(); break
        except KeyboardInterrupt: break
        except Exception as e: logger.critical(f"Crash: {e}"); time.sleep(10)
