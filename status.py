# Trading Bot Status Dashboard
# Run: python3 status.py

import os, json
from pathlib import Path
from datetime import datetime, timezone, timedelta

def print_status():
    print("="*70)
    print("🤖 CRYPTO GOD JOHN - STATUS DASHBOARD")
    print("="*70)
    
    # Check .env
    env_exists = Path('.env').exists()
    print(f"\n📁 Environment: {'✅ .env found' if env_exists else '❌ .env missing'}")
    
    # Check API
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from coinbase_legacy import CoinbaseLegacyClient
        client = CoinbaseLegacyClient()
        btc = client.get_product_price('BTC-USD')
        print(f"🔌 Coinbase API: ✅ Connected (BTC: ${btc:,.0f})")
    except Exception as e:
        print(f"🔌 Coinbase API: ❌ {e}")
    
    # Check logs
    log_dir = Path('logs')
    if log_dir.exists():
        log_files = list(log_dir.glob('*.log'))
        print(f"\n📊 Logs: {len(log_files)} log files")
        for f in log_files[-3:]:
            size = f.stat().st_size / 1024
            print(f"   {f.name}: {size:.1f}KB")
    
    # Check signals
    signal_dir = Path('data/signals')
    if signal_dir.exists():
        signals = list(signal_dir.glob('*.json'))
        print(f"\n📡 Signals: {len(signals)} generated")
    
    # Check trades
    trades_dir = Path('data/trades')
    if trades_dir.exists():
        trades = list(trades_dir.glob('*.json'))
        today = datetime.now(timezone.utc).date().isoformat()
        today_trades = [t for t in trades if t.stat().st_mtime > (datetime.now().timestamp() - 86400)]
        print(f"\n💰 Trades: {len(trades)} total, {len(today_trades)} today")
    
    # Check mode
    paper = os.getenv('PAPER_MODE', 'true').lower() == 'true'
    print(f"\n🎮 Mode: {'📋 PAPER (safe)' if paper else '💰 LIVE (real money)'}")
    
    # Safety limits
    print(f"\n🛡️  Safety Limits:")
    print(f"   Max trades/day: 3")
    print(f"   Max position: $10")
    print(f"   Daily loss halt: $5")
    
    print("\n" + "="*70)
    print("Commands:")
    print("   ./quick-start.sh  - Start trading")
    print("   ./DEPLOY.sh       - Full deployment")
    print("   python3 test_suite.py - Run tests")
    print("="*70)

if __name__ == '__main__':
    print_status()
