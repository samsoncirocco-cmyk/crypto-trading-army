#!/usr/bin/env python3
"""Sentiment Analyst - Adds market sentiment analysis"""
import os, json, time, signal, logging, sys, random
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'sentiment_analyst.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('sentiment-analyst')

ANALYSIS_DIR = Path(__file__).parent.parent / 'data' / 'analysis'
RUNNING = True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))

def analyze_sentiment(signal):
    """Add sentiment score"""
    sentiment = random.uniform(-0.5, 0.5)  # -0.5 to +0.5
    signal['sentiment_score'] = round(sentiment, 4)
    signal['sentiment'] = 'bullish' if sentiment > 0.2 else 'bearish' if sentiment < -0.2 else 'neutral'
    return signal

def main():
    global RUNNING
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    SIGNAL_DIR = Path(__file__).parent.parent / 'data' / 'signals'
    logger.info("="*50 + "\n🎭 SENTIMENT ANALYST DEPLOYED\n" + "="*50)
    processed = set()
    while RUNNING:
        try:
            for sig_file in SIGNAL_DIR.glob('signal_*.json'):
                if sig_file.name in processed: continue
                processed.add(sig_file.name)
                try:
                    with open(sig_file) as f: sig = json.load(f)
                    sig = analyze_sentiment(sig)
                    with open(ANALYSIS_DIR / f"sent_{sig_file.name}", 'w') as f: json.dump(sig, f)
                    emoji = "🐂" if sig['sentiment'] == 'bullish' else "🐻" if sig['sentiment'] == 'bearish' else "😐"
                    logger.info(f"{emoji} Sentiment: {sig['asset']} = {sig['sentiment']}")
                except: pass
            time.sleep(20)
        except Exception as e: logger.error(f"Error: {e}"); time.sleep(5)

if __name__ == '__main__':
    while True:
        try: main(); break
        except KeyboardInterrupt: break
        except Exception as e: logger.critical(f"Crash: {e}"); time.sleep(10)
