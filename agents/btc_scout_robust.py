#!/usr/bin/env python3
"""
BTC Scout Agent - Real price data from Coinbase Advanced Trade API
Detects liquidity sweep patterns using actual OHLCV candles.
No more random mock data — this watches the real market.
"""

import os
import sys
import time
import json
import signal
import logging
import traceback
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'btc_scout_robust.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('btc-scout-robust')

AGENT_ID = "btc-scout-robust"
ASSET = "BTC-USD"
SIGNAL_DIR = Path(__file__).parent.parent / 'data' / 'signals'
RUNNING = True

# Strategy params
SL_PCT = 0.012   # 1.2% stop loss
TP_PCT = 0.024   # 2.4% take profit (2:1 RR)
MIN_WICK_RATIO = 2.0      # Wick must be 2x body
MIN_VOLUME_RATIO = 1.4    # 1.4x avg volume
SWEEP_LOOKBACK = 15       # candles to look back for swing levels


def signal_handler(signum, frame):
    global RUNNING
    logger.info(f"Signal {signum} — shutting down gracefully")
    RUNNING = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def get_candles_public(product_id: str, granularity: str = "ONE_MINUTE", limit: int = 60):
    """
    Fetch recent candles from Coinbase Exchange public API (no auth required).
    Uses api.exchange.coinbase.com (GDAX) which has public OHLCV data.
    granularity: ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, ONE_HOUR, ONE_DAY
    """
    seconds_map = {
        "ONE_MINUTE":      60,
        "FIVE_MINUTE":    300,
        "FIFTEEN_MINUTE": 900,
        "ONE_HOUR":       3600,
        "ONE_DAY":        86400,
    }
    interval = seconds_map.get(granularity, 60)

    # Public endpoint — no auth needed
    url = f"https://api.exchange.coinbase.com/products/{product_id}/candles"
    # Note: omit start/end for simple latest-N-candles fetch
    # Coinbase Exchange returns newest-first by default (up to 300 per call)
    params = {"granularity": str(interval)}

    try:
        resp = requests.get(url, params=params, timeout=10,
                            headers={"User-Agent": "btc-scout/1.0"})
        resp.raise_for_status()
        raw = resp.json()   # [[time, low, high, open, close, volume], ...]

        parsed = []
        for c in raw:
            parsed.append({
                "time":   int(c[0]),
                "low":    float(c[1]),
                "high":   float(c[2]),
                "open":   float(c[3]),
                "close":  float(c[4]),
                "volume": float(c[5]),
            })

        # Sort ascending by time (API returns newest-first)
        parsed.sort(key=lambda x: x["time"])
        return parsed[-limit:]   # Cap at limit

    except Exception as e:
        logger.warning(f"Candle fetch failed: {e}")
        return []


def find_swing_lows(candles, lookback=10):
    """Return recent swing low levels"""
    lows = []
    for i in range(2, len(candles) - 2):
        c = candles[i]
        if (c["low"] < candles[i-1]["low"] and
                c["low"] < candles[i-2]["low"] and
                c["low"] < candles[i+1]["low"] and
                c["low"] < candles[i+2]["low"]):
            lows.append(c["low"])
    return lows[-5:]  # Last 5 swing lows


def find_swing_highs(candles, lookback=10):
    """Return recent swing high levels"""
    highs = []
    for i in range(2, len(candles) - 2):
        c = candles[i]
        if (c["high"] > candles[i-1]["high"] and
                c["high"] > candles[i-2]["high"] and
                c["high"] > candles[i+1]["high"] and
                c["high"] > candles[i+2]["high"]):
            highs.append(c["high"])
    return highs[-5:]


def detect_sweep(candles):
    """
    Detect liquidity sweep on the most recent candle.
    Returns signal dict or None.
    """
    if len(candles) < SWEEP_LOOKBACK + 5:
        return None

    # Volume average (last 20 candles excluding latest)
    vol_sample = [c["volume"] for c in candles[-21:-1]]
    avg_volume = sum(vol_sample) / len(vol_sample) if vol_sample else 0

    candle = candles[-1]
    vol_ratio = candle["volume"] / avg_volume if avg_volume > 0 else 0

    if vol_ratio < MIN_VOLUME_RATIO:
        return None  # Low volume — skip

    body = abs(candle["close"] - candle["open"])
    if body == 0:
        return None

    # --- Check LONG sweep (wick below, body closed up) ---
    if candle["close"] > candle["open"]:
        lower_wick = candle["open"] - candle["low"]
        wick_ratio = lower_wick / body
        if wick_ratio >= MIN_WICK_RATIO:
            swing_lows = find_swing_lows(candles[:-1])
            for level in swing_lows:
                if abs(candle["low"] - level) / level < 0.005:  # Within 0.5%
                    entry = candle["close"]
                    sl = entry * (1 - SL_PCT)
                    tp = entry * (1 + TP_PCT)
                    confidence = min(0.95, 0.65 + (wick_ratio - 2) * 0.05 + (vol_ratio - 1.4) * 0.03)
                    return {
                        "agent_id": AGENT_ID,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "asset": ASSET,
                        "direction": "LONG",
                        "confidence": round(confidence, 4),
                        "entry_price": round(entry, 2),
                        "stop_loss": round(sl, 2),
                        "take_profit": round(tp, 2),
                        "wick_ratio": round(wick_ratio, 2),
                        "volume_ratio": round(vol_ratio, 2),
                        "swept_level": round(level, 2),
                        "paper_mode": True,
                    }

    # --- Check SHORT sweep (wick above, body closed down) ---
    if candle["close"] < candle["open"]:
        upper_wick = candle["high"] - candle["open"]
        wick_ratio = upper_wick / body
        if wick_ratio >= MIN_WICK_RATIO:
            swing_highs = find_swing_highs(candles[:-1])
            for level in swing_highs:
                if abs(candle["high"] - level) / level < 0.005:
                    entry = candle["close"]
                    sl = entry * (1 + SL_PCT)
                    tp = entry * (1 - TP_PCT)
                    confidence = min(0.95, 0.65 + (wick_ratio - 2) * 0.05 + (vol_ratio - 1.4) * 0.03)
                    return {
                        "agent_id": AGENT_ID,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "asset": ASSET,
                        "direction": "SHORT",
                        "confidence": round(confidence, 4),
                        "entry_price": round(entry, 2),
                        "stop_loss": round(sl, 2),
                        "take_profit": round(tp, 2),
                        "wick_ratio": round(wick_ratio, 2),
                        "volume_ratio": round(vol_ratio, 2),
                        "swept_level": round(level, 2),
                        "paper_mode": True,
                    }

    return None


def write_signal(sig):
    try:
        ts = int(time.time())
        path = SIGNAL_DIR / f"signal_{AGENT_ID}_{ts}.json"
        with open(path, "w") as f:
            json.dump(sig, f, indent=2)
        logger.info(
            f"🚨 REAL SIGNAL: {sig['direction']} {ASSET} @ ${sig['entry_price']:,.2f} "
            f"SL ${sig['stop_loss']:,.2f} TP ${sig['take_profit']:,.2f} "
            f"(conf {sig['confidence']:.1%} | wick {sig['wick_ratio']}x | vol {sig['volume_ratio']}x)"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to write signal: {e}")
        return False


def main_loop():
    global RUNNING
    cycle = 0
    signals_generated = 0
    last_signal_candle_time = 0

    logger.info("=" * 60)
    logger.info(f"🤖 {AGENT_ID} STARTED — Real Coinbase data")
    logger.info(f"   Asset: {ASSET} | SL: {SL_PCT:.1%} | TP: {TP_PCT:.1%} | RR: 2:1")
    logger.info("=" * 60)

    while RUNNING:
        try:
            cycle += 1

            candles = get_candles_public(ASSET, "ONE_MINUTE", limit=60)
            if not candles:
                logger.warning("No candle data — will retry")
                time.sleep(15)
                continue

            current_price = candles[-1]["close"]
            latest_candle_time = candles[-1]["time"]

            # Only process if this is a new candle
            if latest_candle_time != last_signal_candle_time:
                last_signal_candle_time = latest_candle_time
                sig = detect_sweep(candles)
                if sig:
                    write_signal(sig)
                    signals_generated += 1

            if cycle % 5 == 0:
                logger.info(f"Watching: BTC @ ${current_price:,.2f} | cycles: {cycle} | signals: {signals_generated}")

            # Sleep 30s (half a 1m candle), checking RUNNING every second
            for _ in range(30):
                if not RUNNING:
                    break
                time.sleep(1)

        except Exception as e:
            logger.error(f"Loop error: {e}\n{traceback.format_exc()}")
            time.sleep(10)

    logger.info(f"Scout stopped. Cycles: {cycle}, Signals: {signals_generated}")


def main():
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    max_restarts = 10
    for attempt in range(max_restarts):
        try:
            main_loop()
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            wait = min((attempt + 1) * 5, 30)
            logger.critical(f"CRASH #{attempt+1}: {e} — restart in {wait}s")
            time.sleep(wait)


if __name__ == "__main__":
    main()
