#!/usr/bin/env python3
"""
Agent Coordinator - Polls signal files and fires consensus-based trade queue.
Fixed: Actually reads signal files from data/signals/ (previously disconnected).
"""

import json
import time
import signal
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

LOG_DIR = Path(__file__).parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - coordinator - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'coordinator.log'),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger('coordinator')

SIGNAL_DIR  = Path(__file__).parent / 'data' / 'signals'
TRADE_QUEUE = Path(__file__).parent / 'data' / 'trade_queue.jsonl'
RUNNING = True

# Consensus rules
MIN_SCOUTS        = 2      # How many scouts must agree
MIN_CONFIDENCE    = 0.70   # Average confidence threshold
WINDOW_SECONDS    = 300    # Signals must arrive within 5 minutes
COOLDOWN_SECONDS  = 120    # Ignore same asset for 2 min after queuing


def signal_handler(signum, frame):
    global RUNNING
    logger.info(f"Signal {signum} — shutting down")
    RUNNING = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def load_recent_signals(max_age_seconds: int = WINDOW_SECONDS) -> List[Dict]:
    """Read all signal files newer than max_age_seconds"""
    signals = []
    if not SIGNAL_DIR.exists():
        return signals

    cutoff = time.time() - max_age_seconds

    for path in SIGNAL_DIR.glob("signal_*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                continue
            with open(path) as f:
                sig = json.load(f)
            sig["_file"] = str(path)
            signals.append(sig)
        except Exception as e:
            logger.warning(f"Bad signal file {path.name}: {e}")

    return signals


def check_consensus(signals: List[Dict], last_queued: Dict) -> Dict | None:
    """
    Check if signals meet consensus threshold.
    Returns a trade dict if consensus reached, else None.
    """
    # Group by asset + direction
    groups: Dict[str, List[Dict]] = {}
    for sig in signals:
        key = f"{sig.get('asset', '')}:{sig.get('direction', '')}"
        groups.setdefault(key, []).append(sig)

    for key, group in groups.items():
        asset, direction = key.split(":", 1)

        # Check cooldown
        if asset in last_queued:
            elapsed = time.time() - last_queued[asset]
            if elapsed < COOLDOWN_SECONDS:
                continue

        # Need MIN_SCOUTS unique agents
        agent_ids = set(s.get("agent_id") for s in group)
        if len(agent_ids) < MIN_SCOUTS:
            continue

        avg_confidence = sum(s.get("confidence", 0) for s in group) / len(group)
        if avg_confidence < MIN_CONFIDENCE:
            continue

        # Use most recent signal for prices
        latest = max(group, key=lambda s: s.get("timestamp", ""))

        trade = {
            "id": f"trade_{int(time.time())}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset": asset,
            "direction": direction,
            "entry": latest.get("entry_price"),
            "stop_loss": latest.get("stop_loss"),
            "take_profit": latest.get("take_profit"),
            "scouts": len(agent_ids),
            "avg_confidence": round(avg_confidence, 4),
            "status": "pending_execution",
        }

        logger.info(
            f"🎯 CONSENSUS: {direction} {asset} | "
            f"{len(agent_ids)} scouts | {avg_confidence:.1%} confidence"
        )
        return trade

    return None


def queue_trade(trade: Dict):
    """Append trade to queue file"""
    TRADE_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRADE_QUEUE, "a") as f:
        f.write(json.dumps(trade) + "\n")
    logger.info(f"✅ Trade queued: {trade['direction']} {trade['asset']} @ {trade['entry']}")


def archive_signals(signals: List[Dict]):
    """Move processed signal files to archive so they don't re-trigger"""
    archive = SIGNAL_DIR / 'processed'
    archive.mkdir(exist_ok=True)
    for sig in signals:
        p = Path(sig.get("_file", ""))
        if p.exists():
            try:
                p.rename(archive / p.name)
            except Exception:
                pass


def main():
    global RUNNING

    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    last_queued: Dict[str, float] = {}

    logger.info("=" * 60)
    logger.info("🧠 COORDINATOR STARTED")
    logger.info(f"   Min scouts: {MIN_SCOUTS} | Min confidence: {MIN_CONFIDENCE:.0%}")
    logger.info(f"   Window: {WINDOW_SECONDS}s | Cooldown: {COOLDOWN_SECONDS}s")
    logger.info("=" * 60)

    cycle = 0
    while RUNNING:
        try:
            cycle += 1
            signals = load_recent_signals()

            if signals:
                trade = check_consensus(signals, last_queued)
                if trade:
                    queue_trade(trade)
                    last_queued[trade["asset"]] = time.time()
                    archive_signals(signals)

            if cycle % 20 == 0:
                logger.info(f"Polling... cycle {cycle} | {len(signals)} recent signals")

            for _ in range(15):   # Poll every 15 seconds
                if not RUNNING:
                    break
                time.sleep(1)

        except Exception as e:
            logger.error(f"Coordinator error: {e}")
            time.sleep(10)

    logger.info("Coordinator stopped")


if __name__ == "__main__":
    main()
