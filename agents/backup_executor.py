#!/usr/bin/env python3
"""Backup Executor - Secondary trade execution (failover)"""
import os, json, time, signal, logging, sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'backup_executor.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('backup-executor')

TRADES_DIR = Path(__file__).parent.parent / 'data' / 'trades'
RUNNING = True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))

def check_primary_executor():
    """Check if primary executor is running"""
    import subprocess
    result = subprocess.run(['pgrep', '-f', 'execution_bot_v2'], capture_output=True)
    return result.returncode == 0

def main():
    global RUNNING
    logger.info("="*50 + "\n🔄 BACKUP EXECUTOR DEPLOYED\n" + "="*50)
    logger.info("Monitoring primary executor...")
    while RUNNING:
        try:
            if not check_primary_executor():
                logger.warning("⚠️ Primary executor DOWN - would activate backup")
            else:
                logger.debug("✅ Primary executor healthy")
            time.sleep(60)
        except Exception as e: logger.error(f"Error: {e}"); time.sleep(30)

if __name__ == '__main__':
    while True:
        try: main(); break
        except KeyboardInterrupt: break
        except Exception as e: logger.critical(f"Crash: {e}"); time.sleep(10)
