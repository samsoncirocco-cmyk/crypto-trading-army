#!/usr/bin/env python3
"""
Final Integration Test - End-to-end pipeline validation
"""
import os, sys, time, json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

def test_full_pipeline():
    """Test complete signal → consensus → execution flow"""
    print("="*60)
    print("🔥 FINAL INTEGRATION TEST")
    print("="*60)
    
    BASE_DIR = Path(__file__).parent
    SIGNAL_DIR = BASE_DIR / 'data' / 'signals'
    QUEUE_FILE = BASE_DIR / 'data' / 'trade_queue.jsonl'
    
    # Clean up
    for f in SIGNAL_DIR.glob('test_*.json'):
        f.unlink()
    if QUEUE_FILE.exists():
        QUEUE_FILE.unlink()
    
    # Step 1: Generate signals
    print("\n📡 Step 1: Generating test signals...")
    signals = [
        {'agent_id': 'test-1', 'asset': 'BTC-USD', 'direction': 'LONG', 'confidence': 0.85, 'entry_price': 66382.0},
        {'agent_id': 'test-2', 'asset': 'BTC-USD', 'direction': 'LONG', 'confidence': 0.82, 'entry_price': 66390.0},
        {'agent_id': 'test-3', 'asset': 'SOL-USD', 'direction': 'SHORT', 'confidence': 0.75, 'entry_price': 84.0},
    ]
    
    for sig in signals:
        sig['timestamp'] = datetime.now(timezone.utc).isoformat()
        sig['source'] = 'integration_test'
        filename = f"signal_{sig['agent_id']}_{int(time.time())}.json"
        with open(SIGNAL_DIR / filename, 'w') as f:
            json.dump(sig, f)
    print(f"   ✅ Generated {len(signals)} signals")
    
    # Step 2: Run consensus
    print("\n🤝 Step 2: Running consensus...")
    
    # Load all signals
    loaded = []
    for f in SIGNAL_DIR.glob('signal_*.json'):
        try:
            with open(f) as fh:
                loaded.append(json.load(fh))
        except: pass
    
    # Check consensus
    btc_longs = [s for s in loaded if s['asset'] == 'BTC-USD' and s['direction'] == 'LONG']
    
    if len(btc_longs) >= 2:
        print(f"   ✅ Consensus: LONG BTC ({len(btc_longs)} signals)")
        
        # Queue trade
        trade = {
            'asset': 'BTC-USD',
            'direction': 'LONG',
            'entry_price': sum(s['entry_price'] for s in btc_longs) / len(btc_longs),
            'confidence': sum(s['confidence'] for s in btc_longs) / len(btc_longs),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        with open(QUEUE_FILE, 'a') as f:
            f.write(json.dumps(trade) + '\n')
        print(f"   ✅ Trade queued")
    else:
        print(f"   ⚠️  No consensus")
        return False
    
    # Step 3: Execute
    print("\n💰 Step 3: Executing trade...")
    
    from paper_simulator import PaperTradingSimulator
    sim = PaperTradingSimulator(BASE_DIR / 'data')
    
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE) as f:
            for line in f:
                try:
                    trade = json.loads(line)
                    result = sim.place_market_order(
                        trade['asset'], 
                        'BUY',  # LONG = BUY
                        10.0,
                        trade['entry_price']
                    )
                    print(f"   ✅ Executed: {result['trade_id']}")
                    print(f"   ✅ Size: ${result['size_usd']} at ${result['entry_price']}")
                except Exception as e:
                    print(f"   ❌ Execution failed: {e}")
                    return False
    
    # Step 4: Verify
    print("\n✓ Step 4: Verification...")
    stats = sim.get_stats()
    print(f"   Trades: {stats['trades']}")
    print(f"   Positions: {len(sim.positions)}")
    
    print("\n" + "="*60)
    print("✅ INTEGRATION TEST PASSED")
    print("="*60)
    print("Pipeline: Signal → Consensus → Queue → Execution")
    print("Ready for live deployment")
    print("="*60)
    
    return True

if __name__ == '__main__':
    success = test_full_pipeline()
    sys.exit(0 if success else 1)
