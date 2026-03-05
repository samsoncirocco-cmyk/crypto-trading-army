#!/usr/bin/env python3
"""
Coinbase Advanced Trade API Client - FIXED VERSION
Handles both PEM and base64 private key formats
"""
import os
import json
import time
import uuid
import base64
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


class CoinbaseAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class CoinbaseAdvancedClient:
    """
    Coinbase Advanced Trade API Client
    Auth: JWT with ES256 (ECDSA)
    """

    BASE_URL = "https://api.coinbase.com"
    ALLOWED_PAIRS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'AVAX-USD', 'MATIC-USD']

    def __init__(self):
        self.api_key_name = os.getenv('COINBASE_API_KEY_NAME')
        raw_secret = os.getenv('COINBASE_API_PRIVATE_KEY', '')
        self.api_private_key = raw_secret.replace('\\n', '\n')
        self.live_mode = os.getenv('PAPER_MODE', 'true').lower() == 'false'

        if not self.api_key_name or not self.api_private_key:
            raise ValueError("COINBASE_API_KEY_NAME and COINBASE_API_PRIVATE_KEY required")

    def _load_private_key(self):
        """Load private key from PEM or base64 format"""
        from cryptography.hazmat.primitives import serialization
        
        key_data = self.api_private_key
        
        # Try PEM format first
        if 'BEGIN EC PRIVATE KEY' in key_data or 'BEGIN PRIVATE KEY' in key_data:
            return serialization.load_pem_private_key(key_data.encode(), password=None)
        
        # Try base64-encoded DER
        try:
            der_data = base64.b64decode(key_data)
            return serialization.load_der_private_key(der_data, password=None)
        except:
            pass
        
        # Try raw bytes
        try:
            return serialization.load_der_private_key(key_data.encode(), password=None)
        except:
            pass
        
        raise ValueError("Could not load private key - not valid PEM or DER format")

    def _generate_jwt(self, request_method: str, request_path: str) -> str:
        """Generate ES256 JWT for Coinbase Advanced Trade API"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

        now = int(time.time())
        nonce = str(uuid.uuid4())
        uri = f"{request_method.upper()} api.coinbase.com{request_path}"

        header = {"alg": "ES256", "kid": self.api_key_name, "typ": "JWT", "nonce": nonce}
        payload = {
            "sub": self.api_key_name,
            "iss": "cdp",
            "nbf": now,
            "exp": now + 120,
            "uri": uri,
        }

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

        header_b64 = b64url(json.dumps(header, separators=(',', ':')).encode())
        payload_b64 = b64url(json.dumps(payload, separators=(',', ':')).encode())
        signing_input = f"{header_b64}.{payload_b64}".encode()

        private_key = self._load_private_key()
        signature = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))

        # DER → raw (r || s) for JWT
        r, s = decode_dss_signature(signature)
        raw_sig = r.to_bytes(32, 'big') + s.to_bytes(32, 'big')

        return f"{header_b64}.{payload_b64}.{b64url(raw_sig)}"

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        """Make authenticated request to Coinbase Advanced Trade API"""
        url = f"{self.BASE_URL}{path}"
        jwt_token = self._generate_jwt(method, path)

        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        try:
            resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
            except:
                error_data = {}
            raise CoinbaseAPIError(
                f"API Error {e.response.status_code}: {error_data.get('message', str(e))}",
                status_code=e.response.status_code,
                response=error_data,
            )
        except requests.exceptions.RequestException as e:
            raise CoinbaseAPIError(f"Request failed: {e}")

    def list_accounts(self) -> List[Account]:
        """List all accounts with balances"""
        data = self._request("GET", "/api/v3/brokerage/accounts")
        accounts = []
        for acc in data.get('accounts', []):
            accounts.append(Account(
                uuid=acc.get('uuid', ''),
                currency=acc.get('currency', ''),
                available=float(acc.get('available_balance', {}).get('value', 0)),
                hold=float(acc.get('hold', {}).get('value', 0))
            ))
        return accounts

    def get_product_price(self, product_id: str) -> float:
        """Get current product price"""
        data = self._request("GET", f"/api/v3/brokerage/products/{product_id}")
        return float(data.get('price', 0))

    def place_market_order(self, product_id: str, side: str, amount_usd: float) -> Order:
        """Place a market order"""
        if product_id not in self.ALLOWED_PAIRS:
            raise ValueError(f"Product {product_id} not in allowed pairs")

        client_order_id = str(uuid.uuid4())
        
        payload = {
            "client_order_id": client_order_id,
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": {
                "market_market_ioc": {
                    "quote_size": str(amount_usd)
                }
            }
        }

        data = self._request("POST", "/api/v3/brokerage/orders", json=payload)
        
        order_data = data.get('success_response', {})
        return Order(
            order_id=order_data.get('order_id', ''),
            product_id=product_id,
            side=side.upper(),
            size=amount_usd,
            price=None,
            status='PENDING',
            created_time=datetime.now(timezone.utc).isoformat()
        )

    def get_order(self, order_id: str) -> Dict:
        """Get order status"""
        return self._request("GET", f"/api/v3/brokerage/orders/historical/{order_id}")


if __name__ == '__main__':
    # Test
    from dotenv import load_dotenv
    load_dotenv()
    
    client = CoinbaseAdvancedClient()
    print(f"BTC Price: ${client.get_product_price('BTC-USD')}")
