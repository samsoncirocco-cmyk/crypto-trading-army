#!/usr/bin/env python3
"""Test Coinbase API authentication"""
import os, sys, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from coinbase_advanced import CoinbaseAdvancedClient

def test_auth():
    print("="*60)
    print("🧪 TESTING COINBASE API AUTH")
    print("="*60)
    
    # Check env vars
    key = os.getenv('COINBASE_API_KEY_NAME')
    secret = os.getenv('COINBASE_API_PRIVATE_KEY')
    
    print(f"\n📋 Environment:")
    print(f"   API Key: {'✅ Set' if key else '❌ Missing'}")
    print(f"   Secret: {'✅ Set' if secret else '❌ Missing'}")
    print(f"   Paper Mode: {os.getenv('PAPER_MODE', 'true')}")
    
    if not key or not secret:
        print("\n❌ Missing credentials!")
        return False
    
    try:
        client = CoinbaseAdvancedClient()
        print(f"\n🔑 Client initialized")
        
        # Test JWT generation
        jwt = client._generate_jwt("GET", "/api/v3/brokerage/products")
        print(f"✅ JWT generated ({len(jwt)} chars)")
        
        # Test API call
        print(f"\n📡 Testing API call...")
        result = client.get_product_price("BTC-USD")
        print(f"✅ BTC Price: ${result}")
        
        # Test accounts
        print(f"\n💰 Fetching accounts...")
        accounts = client.list_accounts()
        print(f"✅ Found {len(accounts)} accounts")
        for acc in accounts[:3]:
            print(f"   {acc.currency}: {acc.available}")
        
        print(f"\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_auth()
    sys.exit(0 if success else 1)
