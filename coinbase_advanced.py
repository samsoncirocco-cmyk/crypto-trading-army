"""
Coinbase Advanced Trade API Client
Uses JWT (ES256/ECDSA) authentication — required by Coinbase Advanced Trade API
"""

import os
import json
import time
import uuid
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Account:
    """Represents a Coinbase account/balance"""
    uuid: str
    currency: str
    available: float
    hold: float

    @property
    def balance(self) -> float:
        return self.available + self.hold


@dataclass
class Order:
    """Represents a placed order"""
    order_id: str
    product_id: str
    side: str
    size: float
    price: Optional[float]
    status: str
    created_time: str


class CoinbaseAPIError(Exception):
    """Raised when Coinbase API returns an error"""
    def __init__(self, message: str, status_code: int = 0, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class CoinbaseAdvancedClient:
    """
    Coinbase Advanced Trade API Client
    Auth: JWT with ES256 (ECDSA) — required by Coinbase CDP

    API keys from https://portal.cdp.coinbase.com
    Set env vars:
        COINBASE_API_KEY_NAME   — e.g. "organizations/xxx/apiKeys/yyy"
        COINBASE_API_PRIVATE_KEY — PEM-encoded EC private key (multi-line, or \\n-separated)
        PAPER_MODE              — "true" (default) or "false" to go live
    """

    BASE_URL = "https://api.coinbase.com"
    ALLOWED_PAIRS = ['BTC-USD', 'ETH-USD', 'SOL-USD']

    def __init__(self):
        self.api_key_name = os.getenv('COINBASE_API_KEY_NAME')
        raw_secret = os.getenv('COINBASE_API_PRIVATE_KEY', '')
        # Allow \\n-separated PEM in env vars
        self.api_private_key = raw_secret.replace('\\n', '\n')
        self.live_mode = os.getenv('PAPER_MODE', 'true').lower() == 'false'

        if not self.api_key_name or not self.api_private_key:
            raise ValueError(
                "COINBASE_API_KEY_NAME and COINBASE_API_PRIVATE_KEY are required.\n"
                "Get keys at: https://portal.cdp.coinbase.com"
            )

    def _generate_jwt(self, request_method: str, request_path: str) -> str:
        """
        Generate ES256 JWT for Coinbase Advanced Trade API.
        Requires: pip install cryptography
        """
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec
            import base64
        except ImportError:
            raise ImportError(
                "Missing 'cryptography' package. Run: pip install cryptography"
            )

        now = int(time.time())
        nonce = str(uuid.uuid4())
        uri = f"{request_method.upper()} api.coinbase.com{request_path}"

        header = {"alg": "ES256", "kid": self.api_key_name, "typ": "JWT"}
        payload = {
            "sub": self.api_key_name,
            "iss": "cdp",
            "nbf": now,
            "exp": now + 120,
            "uri": uri,
            "nonce": nonce,
        }

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

        header_b64 = b64url(json.dumps(header, separators=(',', ':')).encode())
        payload_b64 = b64url(json.dumps(payload, separators=(',', ':')).encode())
        signing_input = f"{header_b64}.{payload_b64}".encode()

        private_key = serialization.load_pem_private_key(
            self.api_private_key.encode(), password=None
        )
        signature = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))

        # DER → raw (r || s) for JWT
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
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
            except Exception:
                error_data = {}
            raise CoinbaseAPIError(
                f"API Error {e.response.status_code}: {error_data.get('message', str(e))}",
                status_code=e.response.status_code,
                response=error_data,
            )
        except requests.exceptions.RequestException as e:
            raise CoinbaseAPIError(f"Request failed: {e}")

    def get_accounts(self) -> List[Account]:
        """Get all account balances"""
        data = self._request('GET', '/api/v3/brokerage/accounts')
        accounts = []
        for acc in data.get('accounts', []):
            available = float(acc.get('available_balance', {}).get('value', 0))
            hold = float(acc.get('hold', {}).get('value', 0))
            accounts.append(Account(
                uuid=acc.get('uuid', ''),
                currency=acc.get('currency', ''),
                available=available,
                hold=hold,
            ))
        return accounts

    def get_usd_balance(self) -> float:
        """Get available USD balance"""
        for acc in self.get_accounts():
            if acc.currency == 'USD':
                return acc.available
        return 0.0

    def get_product_price(self, product_id: str = 'BTC-USD') -> float:
        """Get current best bid/ask midpoint price"""
        data = self._request('GET', f'/api/v3/brokerage/best_bid_ask',
                             params={'product_ids': product_id})
        pricebooks = data.get('pricebooks', [])
        if pricebooks:
            bids = pricebooks[0].get('bids', [])
            asks = pricebooks[0].get('asks', [])
            if bids and asks:
                return (float(bids[0]['price']) + float(asks[0]['price'])) / 2
        # Fallback to product endpoint
        fallback = self._request('GET', f'/api/v3/brokerage/products/{product_id}')
        return float(fallback.get('price', 0))

    def place_market_buy(self, product_id: str, amount_usd: float) -> Optional[Order]:
        """
        Place a market BUY order.
        amount_usd: how many dollars to spend
        """
        if product_id not in self.ALLOWED_PAIRS:
            raise ValueError(f"{product_id} not in allowed pairs: {self.ALLOWED_PAIRS}")

        if not self.live_mode:
            print(f"[PAPER] Would BUY ${amount_usd:.2f} of {product_id}")
            return None

        payload = {
            'client_order_id': f"bot-{uuid.uuid4().hex[:12]}",
            'product_id': product_id,
            'side': 'BUY',
            'order_configuration': {
                'market_market_ioc': {
                    'quote_size': str(amount_usd)   # USD amount for buys
                }
            }
        }
        data = self._request('POST', '/api/v3/brokerage/orders', json=payload)
        result = data.get('success_response', {})
        return Order(
            order_id=result.get('order_id', ''),
            product_id=product_id,
            side='BUY',
            size=amount_usd,
            price=None,
            status='PENDING',
            created_time=datetime.now(timezone.utc).isoformat(),
        )

    def place_market_sell(self, product_id: str, base_size: float) -> Optional[Order]:
        """
        Place a market SELL order.
        base_size: quantity of base asset (BTC/ETH) to sell
        """
        if product_id not in self.ALLOWED_PAIRS:
            raise ValueError(f"{product_id} not in allowed pairs: {self.ALLOWED_PAIRS}")

        if not self.live_mode:
            print(f"[PAPER] Would SELL {base_size:.8f} {product_id.split('-')[0]}")
            return None

        payload = {
            'client_order_id': f"bot-{uuid.uuid4().hex[:12]}",
            'product_id': product_id,
            'side': 'SELL',
            'order_configuration': {
                'market_market_ioc': {
                    'base_size': str(base_size)   # Asset quantity for sells
                }
            }
        }
        data = self._request('POST', '/api/v3/brokerage/orders', json=payload)
        result = data.get('success_response', {})
        return Order(
            order_id=result.get('order_id', ''),
            product_id=product_id,
            side='SELL',
            size=base_size,
            price=None,
            status='PENDING',
            created_time=datetime.now(timezone.utc).isoformat(),
        )

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order status by ID"""
        data = self._request('GET', f'/api/v3/brokerage/orders/historical/{order_id}')
        order = data.get('order', {})
        avg_price = order.get('average_filled_price')
        return Order(
            order_id=order.get('order_id', ''),
            product_id=order.get('product_id', ''),
            side=order.get('side', ''),
            size=float(order.get('filled_size', 0)),
            price=float(avg_price) if avg_price else None,
            status=order.get('status', 'UNKNOWN'),
            created_time=order.get('created_time', ''),
        )

    def get_fills(self, product_id: str, limit: int = 100) -> List[Dict]:
        """Get recent fills (executed trades) — used for cost basis tracking"""
        data = self._request('GET', '/api/v3/brokerage/orders/historical/fills',
                             params={'product_id': product_id, 'limit': limit})
        return data.get('fills', [])
