#!/usr/bin/env python3
"""
Coinbase API Client - LEGACY AUTH (HMAC-SHA256)
For API keys in format: a60aaebb-55df-40b3-a815-4a14d29e2913
"""
import os
import json
import time
import base64
import hmac
import hashlib
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Account:
    uuid: str
    currency: str
    available: float
    hold: float

    @property
    def balance(self) -> float:
        return self.available + self.hold


@dataclass 
class Order:
    order_id: str
    product_id: str
    side: str
    size: float
    price: Optional[float]
    status: str
    created_time: str


class CoinbaseLegacyClient:
    """
    Coinbase Legacy API Client (HMAC-SHA256)
    Uses API Key + Secret for authentication
    """
    
    BASE_URL = "https://api.exchange.coinbase.com"  # Legacy endpoint
    ALLOWED_PAIRS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'AVAX-USD', 'MATIC-USD']
    
    def __init__(self):
        self.api_key = os.getenv('COINBASE_API_KEY_NAME')
        self.api_secret = os.getenv('COINBASE_API_PRIVATE_KEY', '')
        self.live_mode = os.getenv('PAPER_MODE', 'true').lower() == 'false'
        
        if not self.api_key or not self.api_secret:
            raise ValueError("COINBASE_API_KEY_NAME and COINBASE_API_PRIVATE_KEY required")
    
    def _get_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        """Generate HMAC-SHA256 signature"""
        message = timestamp + method.upper() + path + body
        secret = base64.b64decode(self.api_secret)
        signature = hmac.new(secret, message.encode('utf-8'), hashlib.sha256).digest()
        return base64.b64encode(signature).decode()
    
    def _request(self, method: str, path: str, body: str = '') -> Dict:
        """Make authenticated request"""
        timestamp = str(int(time.time()))
        signature = self._get_signature(timestamp, method, path, body)
        
        headers = {
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-SIGN': signature,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-PASSPHRASE': '',  # May be empty for some key types
            'Content-Type': 'application/json'
        }
        
        url = self.BASE_URL + path
        
        try:
            if body:
                resp = requests.request(method, url, headers=headers, data=body, timeout=30)
            else:
                resp = requests.request(method, url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            print(f"Error: {e.response.text if hasattr(e, 'response') else e}")
            raise
    
    def get_product_price(self, product_id: str) -> float:
        """Get current product price"""
        data = self._request("GET", f"/products/{product_id}/ticker")
        return float(data.get('price', 0))
    
    def list_accounts(self) -> List[Account]:
        """List all accounts"""
        data = self._request("GET", "/accounts")
        accounts = []
        for acc in data:
            accounts.append(Account(
                uuid=acc.get('id', ''),
                currency=acc.get('currency', ''),
                available=float(acc.get('available', 0)),
                hold=float(acc.get('hold', 0))
            ))
        return accounts
    
    def place_market_order(self, product_id: str, side: str, funds: float) -> Order:
        """Place a market order"""
        if product_id not in self.ALLOWED_PAIRS:
            raise ValueError(f"Product {product_id} not allowed")
        
        body = json.dumps({
            'type': 'market',
            'side': side.lower(),
            'product_id': product_id,
            'funds': str(funds)
        })
        
        data = self._request("POST", "/orders", body)
        
        return Order(
            order_id=data.get('id', ''),
            product_id=product_id,
            side=side.upper(),
            size=funds,
            price=None,
            status=data.get('status', 'pending'),
            created_time=datetime.now(timezone.utc).isoformat()
        )


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    
    try:
        client = CoinbaseLegacyClient()
        print("✅ Client initialized")
        
        price = client.get_product_price('BTC-USD')
        print(f"✅ BTC Price: ${price}")
        
        accounts = client.list_accounts()
        print(f"✅ Accounts: {len(accounts)}")
        for acc in accounts[:3]:
            print(f"   {acc.currency}: {acc.available}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
