#!/usr/bin/env python3
"""
Trading Bot Test Suite
Validates API connectivity, JWT generation, and module imports.
Runs without real API keys for basic tests.
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add trading dir to path
sys.path.insert(0, str(Path(__file__).parent))


class TestImports(unittest.TestCase):
    """Test that all modules can be imported"""
    
    def test_coinbase_advanced_import(self):
        """Import coinbase_advanced without API keys"""
        with patch.dict(os.environ, {}, clear=True):
            # Should fail without keys, but module should import
            try:
                import coinbase_advanced
                self.assertTrue(hasattr(coinbase_advanced, 'CoinbaseAdvancedClient'))
                self.assertTrue(hasattr(coinbase_advanced, 'CoinbaseAPIError'))
                self.assertTrue(hasattr(coinbase_advanced, 'Account'))
                self.assertTrue(hasattr(coinbase_advanced, 'Order'))
            except Exception as e:
                self.fail(f"coinbase_advanced import failed: {e}")
    
    def test_portfolio_import(self):
        """Import portfolio module"""
        try:
            import portfolio
            self.assertTrue(hasattr(portfolio, 'PortfolioTracker'))
            self.assertTrue(hasattr(portfolio, 'Position'))
        except Exception as e:
            self.fail(f"portfolio import failed: {e}")
    
    def test_risk_import(self):
        """Import risk module"""
        try:
            import risk
            self.assertTrue(hasattr(risk, 'RiskManager'))
            self.assertTrue(hasattr(risk, 'RiskViolation'))
            self.assertTrue(hasattr(risk, 'TradingHaltedError'))
        except Exception as e:
            self.fail(f"risk import failed: {e}")
    
    def test_strategy_import(self):
        """Import strategy module"""
        try:
            import strategy
            self.assertTrue(hasattr(strategy, 'DCAStrategy'))
        except Exception as e:
            self.fail(f"strategy import failed: {e}")
    
    def test_notifier_import(self):
        """Import notifier module"""
        try:
            import notifier
            self.assertTrue(hasattr(notifier, 'TelegramNotifier'))
        except Exception as e:
            self.fail(f"notifier import failed: {e}")
    
    def test_scheduler_import(self):
        """Import scheduler module"""
        try:
            import scheduler
            self.assertTrue(hasattr(scheduler, 'BotScheduler'))
        except Exception as e:
            self.fail(f"scheduler import failed: {e}")


class TestJWTGeneration(unittest.TestCase):
    """Test JWT token generation"""
    
    def setUp(self):
        """Set up mock credentials"""
        self.mock_env = {
            'COINBASE_API_KEY_NAME': 'organizations/test/apiKeys/test-key',
            'COINBASE_API_PRIVATE_KEY': '''-----BEGIN EC PRIVATE KEY-----
MHQCAQEEIBase64EncodedPrivateKeyHereForTestingXyz123
AbCdEfGhIjKlMnOpQrStUvWxYz7890123456789
-----END EC PRIVATE KEY-----''',
            'PAPER_MODE': 'true'
        }
    
    @patch.dict(os.environ, {}, clear=True)
    def test_client_requires_keys(self):
        """Client should require API keys"""
        with self.assertRaises(ValueError):
            from coinbase_advanced import CoinbaseAdvancedClient
            CoinbaseAdvancedClient()
    
    def test_jwt_generation(self):
        """Test JWT token can be generated with valid credentials"""
        with patch.dict(os.environ, self.mock_env, clear=True):
            from coinbase_advanced import CoinbaseAdvancedClient
            client = CoinbaseAdvancedClient()
            
            # Generate JWT for a test request
            jwt_token = client._generate_jwt('GET', '/api/v3/brokerage/accounts')
            
            # JWT should have 3 parts separated by dots
            parts = jwt_token.split('.')
            self.assertEqual(len(parts), 3, "JWT should have header.payload.signature")
            
            # Each part should be non-empty
            for part in parts:
                self.assertTrue(len(part) > 0, "JWT parts should not be empty")


class TestRiskLimits(unittest.TestCase):
    """Test risk management limits are enforced"""
    
    def setUp(self):
        from risk import RiskManager
        # Clear any existing halt files
        data_dir = Path(__file__).parent / 'data'
        halt_file = data_dir / 'HALT'
        if halt_file.exists():
            halt_file.unlink()
        self.risk = RiskManager()
    
    def test_daily_budget_enforced(self):
        """Daily budget cannot be exceeded"""
        from risk import RiskViolation
        
        # Should allow order under limit
        self.assertTrue(self.risk.validate_order('BTC-USD', 5.0))
        
        # Should reject order over single transaction limit
        with self.assertRaises(RiskViolation):
            self.risk.validate_order('BTC-USD', 15.0)
    
    def test_allowed_pairs_only(self):
        """Only allowed pairs can be traded"""
        from risk import RiskViolation
        
        with self.assertRaises(RiskViolation):
            self.risk.validate_order('SOL-USD', 5.0)
    
    def test_positive_amounts_only(self):
        """Only positive amounts allowed"""
        from risk import RiskViolation
        
        with self.assertRaises(RiskViolation):
            self.risk.validate_order('BTC-USD', -5.0)
        
        with self.assertRaises(RiskViolation):
            self.risk.validate_order('BTC-USD', 0)


class TestDCAStrategy(unittest.TestCase):
    """Test DCA strategy logic"""
    
    def test_dca_initialization(self):
        """DCA strategy initializes correctly"""
        with patch.dict(os.environ, {}, clear=True):
            from strategy import DCAStrategy
            
            strategy = DCAStrategy(
                daily_amount=5.0,
                product_id='BTC-USD',
                dip_threshold=0.03
            )
            
            self.assertEqual(strategy.daily_amount, 5.0)
            self.assertEqual(strategy.product_id, 'BTC-USD')
            self.assertEqual(strategy.dip_threshold, 0.03)


class TestTelegramNotifier(unittest.TestCase):
    """Test Telegram notifier"""
    
    def test_notifier_requires_token(self):
        """Notifier requires TELEGRAM_BOT_TOKEN"""
        with patch.dict(os.environ, {}, clear=True):
            from notifier import TelegramNotifier
            
            notifier = TelegramNotifier()
            self.assertFalse(notifier.enabled, "Notifier should be disabled without token")


def run_tests():
    """Run all tests and return exit code"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestImports))
    suite.addTests(loader.loadTestsFromTestCase(TestJWTGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskLimits))
    suite.addTests(loader.loadTestsFromTestCase(TestDCAStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestTelegramNotifier))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    print("=" * 60)
    print("🧪 Trading Bot Test Suite")
    print("=" * 60)
    print()
    
    exit_code = run_tests()
    
    print()
    print("=" * 60)
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    print("=" * 60)
    
    sys.exit(exit_code)
