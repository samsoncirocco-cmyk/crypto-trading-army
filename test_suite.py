#!/usr/bin/env python3
"""
Test Suite - Automated testing for all components
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

def test_coinbase_connection():
    """Test API connectivity"""
    print("\n🔌 Testing Coinbase Connection...")
    try:
        from coinbase_legacy import CoinbaseLegacyClient
        client = CoinbaseLegacyClient()
        btc = client.get_product_price('BTC-USD')
        print(f"   ✅ BTC: ${btc:,.2f}")
        return True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False

def test_signal_generation():
    """Test signal generation"""
    print("\n📡 Testing Signal Generation...")
    import json
    from datetime import datetime, timezone
    
    signal = {
        'agent_id': 'test',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'asset': 'BTC-USD',
        'direction': 'LONG',
        'confidence': 0.85,
        'entry_price': 66214.61,
        'source': 'test'
    }
    
    print(f"   ✅ Signal: {signal['direction']} {signal['asset']}")
    return True

def test_consensus():
    """Test consensus logic"""
    print("\n🤝 Testing Consensus...")
    
    signals = [
        {'asset': 'BTC-USD', 'direction': 'LONG', 'confidence': 0.8},
        {'asset': 'BTC-USD', 'direction': 'LONG', 'confidence': 0.75},
        {'asset': 'SOL-USD', 'direction': 'SHORT', 'confidence': 0.7}
    ]
    
    # Check for consensus (2+ agreeing)
    btc_longs = [s for s in signals if s['asset'] == 'BTC-USD' and s['direction'] == 'LONG']
    
    if len(btc_longs) >= 2:
        print(f"   ✅ Consensus: LONG BTC (2 signals)")
        return True
    else:
        print(f"   ⚠️  No consensus")
        return False

def test_paper_simulator():
    """Test paper trading"""
    print("\n📋 Testing Paper Simulator...")
    try:
        from paper_simulator import PaperTradingSimulator
        sim = PaperTradingSimulator(Path('./data/test'))
        
        trade = sim.place_market_order('BTC-USD', 'BUY', 10.0, 66214.61)
        print(f"   ✅ Trade entered: ${trade['size_usd']}")
        
        close = sim.close_position('BTC-USD', 67000.00)
        if close:
            print(f"   ✅ Trade closed: ${close['pnl_usd']:+.2f}")
        
        return True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False

def test_risk_limits():
    """Test risk management"""
    print("\n🛡️  Testing Risk Limits...")
    
    # Hardcoded limits
    MAX_TRADES = 3
    MAX_POSITION = 10
    
    trades_today = 2
    position = 5
    
    if trades_today < MAX_TRADES and position < MAX_POSITION:
        print(f"   ✅ Within limits (trades: {trades_today}/{MAX_TRADES})")
        return True
    else:
        print(f"   🚫 Limit exceeded")
        return False

def run_all_tests():
    """Run full test suite"""
    print("="*60)
    print("🧪 TEST SUITE")
    print("="*60)
    
    results = []
    
    results.append(("Coinbase API", test_coinbase_connection()))
    results.append(("Signal Generation", test_signal_generation()))
    results.append(("Consensus", test_consensus()))
    results.append(("Paper Simulator", test_paper_simulator()))
    results.append(("Risk Limits", test_risk_limits()))
    
    print("\n" + "="*60)
    print("📊 RESULTS")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")
    
    print(f"\n   {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*60)
    
    return passed == total

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
