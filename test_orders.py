#!/usr/bin/env python3
"""Test live order placement in paper mode"""
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from coinbase_legacy import CoinbaseLegacyClient
import json

def test_order_placement():
    print("="*60)
    print("🧪 TESTING ORDER PLACEMENT (Paper Mode)")
    print("="*60)
    
    client = CoinbaseLegacyClient()
    print("✅ Client connected")
    
    # Get current prices
    btc = client.get_product_price('BTC-USD')
    print(f"📊 BTC: ${btc:,.2f}")
    
    # Test paper order
    print("\n📋 Placing PAPER order...")
    try:
        order = client.place_market_order('BTC-USD', 'buy', 10.0)
        print(f"✅ Order placed: {order.order_id}")
        print(f"   Asset: {order.product_id}")
        print(f"   Side: {order.side}")
        print(f"   Size: ${order.size}")
        print(f"   Status: {order.status}")
        return True
    except Exception as e:
        print(f"❌ Order failed: {e}")
        return False

if __name__ == '__main__':
    success = test_order_placement()
    print("\n" + "="*60)
    print("✅ READY FOR LIVE TRADING" if success else "❌ FIX ERRORS FIRST")
    print("="*60)
