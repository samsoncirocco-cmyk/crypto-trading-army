#!/usr/bin/env python3
"""
Trading Scheduler - Background daemon for automated trading
Runs DCA strategy on a schedule with state persistence
"""

import os
import sys
import time
import signal
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Setup logging before other imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / 'data' / 'scheduler.log')
    ]
)
logger = logging.getLogger(__name__)

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from strategy import DCAStrategy
from notifier import TelegramNotifier


class TradingScheduler:
    """
    Background scheduler for automated trading
    Handles graceful shutdown, state persistence, and error recovery
    """
    
    DATA_DIR = Path(__file__).parent / 'data'
    STATE_FILE = DATA_DIR / 'scheduler_state.json'
    
    def __init__(self):
        self.running = False
        self.strategy = None
        self.notifier = None
        self.shutdown_requested = False
        
        # Ensure data dir exists
        self.DATA_DIR.mkdir(exist_ok=True)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info("TradingScheduler initialized")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        self.running = False
    
    def _load_state(self) -> dict:
        """Load scheduler state from disk"""
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        return {
            'last_run': None,
            'total_trades': 0,
            'started_at': datetime.now(timezone.utc).isoformat()
        }
    
    def _save_state(self, state: dict):
        """Save scheduler state to disk"""
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def _should_run_dca(self, state: dict) -> bool:
        """Check if DCA should run now (once per day)"""
        last_run = state.get('last_run')
        if not last_run:
            return True
        
        last = datetime.fromisoformat(last_run)
        now = datetime.now(timezone.utc)
        
        # Run if it's a new day
        return last.date() != now.date()
    
    def run_once(self, product_id: str = 'BTC-USD', amount: float = 5.0):
        """Run DCA strategy once (for testing/cron)"""
        logger.info(f"Running one-time DCA: ${amount} of {product_id}")
        
        try:
            strategy = DCAStrategy()
            notifier = TelegramNotifier()
            
            result = strategy.execute_dca_buy(product_id, amount)
            
            if result.success:
                logger.info(f"DCA succeeded: {result.order_id}")
                notifier.send_trade_alert(
                    asset=product_id.split('-')[0],
                    amount=result.amount,
                    price=result.price or 0
                )
            else:
                logger.error(f"DCA failed: {result.error}")
                notifier.send_error_alert(f"DCA failed: {result.error}")
                
        except Exception as e:
            logger.exception("DCA execution failed")
            try:
                notifier = TelegramNotifier()
                notifier.send_error_alert(f"DCA exception: {str(e)}")
            except:
                pass
    
    def run(self, interval_minutes: int = 60):
        """
        Run scheduler daemon loop
        
        Args:
            interval_minutes: How often to check (default: hourly)
        """
        logger.info(f"Starting trading scheduler (interval: {interval_minutes}min)")
        
        self.running = True
        state = self._load_state()
        
        # Initialize strategy and notifier
        try:
            self.strategy = DCAStrategy()
            self.notifier = TelegramNotifier()
            self.notifier.send_message("🤖 Trading scheduler started")
        except Exception as e:
            logger.exception("Failed to initialize strategy/notifier")
            return
        
        logger.info(f"Scheduler state: {state}")
        
        loop_count = 0
        while self.running and not self.shutdown_requested:
            try:
                loop_count += 1
                logger.debug(f"Scheduler loop #{loop_count}")
                
                # Check if we should run DCA (once per day)
                if self._should_run_dca(state):
                    logger.info("Running daily DCA...")
                    
                    result = self.strategy.execute_dca_buy('BTC-USD', 5.0)
                    
                    if result.success:
                        logger.info(f"DCA completed: {result.order_id}")
                        state['last_run'] = datetime.now(timezone.utc).isoformat()
                        state['total_trades'] = state.get('total_trades', 0) + 1
                        
                        # Send notification
                        self.notifier.send_trade_alert(
                            asset='BTC',
                            amount=result.amount,
                            price=result.price or 0
                        )
                    else:
                        logger.error(f"DCA failed: {result.error}")
                        self.notifier.send_error_alert(f"DCA failed: {result.error}")
                
                # Check for dip opportunities (every loop)
                dip_result = self.strategy.check_and_buy_dip('BTC-USD')
                if dip_result and dip_result.success:
                    logger.info(f"Dip buy completed: {dip_result.order_id}")
                    self.notifier.send_trade_alert(
                        asset='BTC',
                        amount=dip_result.amount,
                        price=dip_result.price or 0,
                        note="📉 Dip buy"
                    )
                
                # Save state
                self._save_state(state)
                
                # Sleep until next check
                logger.debug(f"Sleeping for {interval_minutes} minutes...")
                
                # Sleep in small increments to allow quick shutdown
                sleep_seconds = interval_minutes * 60
                chunk = 5  # Check every 5 seconds
                for _ in range(0, sleep_seconds, chunk):
                    if self.shutdown_requested:
                        break
                    time.sleep(chunk)
                
            except Exception as e:
                logger.exception("Error in scheduler loop")
                try:
                    self.notifier.send_error_alert(f"Scheduler error: {str(e)}")
                except:
                    pass
                # Sleep briefly before retrying
                time.sleep(60)
        
        # Cleanup
        logger.info("Scheduler shutting down...")
        self._save_state(state)
        try:
            self.notifier.send_message("🛑 Trading scheduler stopped")
        except:
            pass
        logger.info("Scheduler stopped")


def main():
    """CLI entry point for daemon"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Trading Scheduler Daemon')
    parser.add_argument('--interval', type=int, default=60,
                        help='Check interval in minutes (default: 60)')
    parser.add_argument('--once', action='store_true',
                        help='Run once and exit (for cron)')
    parser.add_argument('--pair', default='BTC-USD',
                        help='Trading pair (default: BTC-USD)')
    parser.add_argument('--amount', type=float, default=5.0,
                        help='DCA amount in USD (default: 5.0)')
    
    args = parser.parse_args()
    
    scheduler = TradingScheduler()
    
    if args.once:
        scheduler.run_once(args.pair, args.amount)
    else:
        print(f"Starting daemon (interval: {args.interval}min)...")
        print("Press Ctrl+C to stop")
        scheduler.run(args.interval)


if __name__ == '__main__':
    main()
