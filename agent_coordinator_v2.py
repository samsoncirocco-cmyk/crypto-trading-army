#!/usr/bin/env python3
"""
Complete Agent Coordinator with Consensus Logic
"""
import os, json, time, signal, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger('coordinator')

BASE_DIR = Path(__file__).parent
SIGNAL_DIR = BASE_DIR / "data" / "signals"
QUEUE_FILE = BASE_DIR / "data" / "trade_queue.jsonl"
RUNNING = True

signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))
signal.signal(signal.SIGINT, lambda s,f: globals().update(RUNNING=False))

def load_signal(path):
    try:
        with open(path) as f:
            return json.load(f)
    except: return None

def get_consensus(signals):
    """Find 2+ scouts agreeing on same asset+direction within 5 min"""
    by_asset_dir = defaultdict(list)
    now = datetime.now(timezone.utc)
    
    for sig in signals:
        ts = datetime.fromisoformat(sig['timestamp'])
        if (now - ts) > timedelta(minutes=10):  # Skip old
            continue
        key = (sig['asset'], sig['direction'])
        by_asset_dir[key].append(sig)
    
    for (asset, direction), sigs in by_asset_dir.items():
        if len(sigs) >= 2:  # Consensus!
            avg_conf = sum(s['confidence'] for s in sigs) / len(sigs)
            avg_price = sum(s['entry_price'] for s in sigs) / len(sigs)
            return {
                'asset': asset,
                'direction': direction,
                'entry_price': round(avg_price, 2),
                'stop_loss': round(avg_price * 0.98, 2),
                'take_profit': round(avg_price * 1.04, 2),
                'confidence': round(avg_conf, 4),
                'signals': len(sigs),
                'timestamp': now.isoformat()
            }
    return None

def queue_trade(trade):
    with open(QUEUE_FILE, 'a') as f:
        f.write(json.dumps(trade) + '\n')
    logger.info(f"🚀 QUEUED: {trade['direction']} {trade['asset']} @ ${trade['entry_price']} (conf: {trade['confidence']:.0%})")

def main():
    global RUNNING
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.info("="*60 + "\n🎯 COORDINATOR STARTED\n" + "="*60)
    
    seen = set()
    while RUNNING:
        try:
            # Find new signals
            for sig_file in SIGNAL_DIR.glob('signal_*.json'):
                if sig_file.name in seen:
                    continue
                seen.add(sig_file.name)
            
            # Load all recent signals
            signals = []
            for sig_file in list(SIGNAL_DIR.glob('signal_*.json'))[-20:]:
                sig = load_signal(sig_file)
                if sig: signals.append(sig)
            
            # Check for consensus
            consensus = get_consensus(signals)
            if consensus:
                queue_trade(consensus)
            
            time.sleep(10)
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
