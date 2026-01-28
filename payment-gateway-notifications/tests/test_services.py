"""
Unit tests for Payment Gateway Notification services.

Run with: pytest tests/test_services.py -v
"""

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from models.merchant import Merchant, NotificationType
from models.payment import PaymentEvent, WebhookPayload, TelegramMessage


class TestMerchantModel:
    """Tests for Merchant model."""

    def test_create_webhook_merchant(self):
        """Test creating a webhook merchant."""
        merchant = Merchant.create_webhook_merchant(
            merchant_id="0x1234567890123456789012345678901234567890",
            webhook_url="https://example.com/webhook",
            name="Test Shop"
        )

        assert merchant.id == "0x1234567890123456789012345678901234567890"
        assert merchant.notification_type == NotificationType.WEBHOOK
        assert merchant.webhook_url == "https://example.com/webhook"
        assert merchant.webhook_secret is not None
        assert len(merchant.webhook_secret) == 64  # 32 bytes hex
        assert merchant.name == "Test Shop"

    def test_create_telegram_merchant(self):
        """Test creating a Telegram merchant."""
        merchant = Merchant.create_telegram_merchant(
            merchant_id="0x1234567890123456789012345678901234567890",
            telegram_chat_id="123456789",
            name="Test Shop"
        )

        assert merchant.notification_type == NotificationType.TELEGRAM
        assert merchant.telegram_chat_id == "123456789"
        assert merchant.webhook_url is None

    def test_merchant_validation_invalid_address(self):
        """Test that invalid Ethereum addresses are rejected."""
        with pytest.raises(ValueError, match="Invalid Ethereum address"):
            Merchant(
                id="invalid",
                notification_type=NotificationType.WEBHOOK,
                webhook_url="https://example.com"
            )

    def test_merchant_validation_missing_webhook_url(self):
        """Test that webhook merchants require URL."""
        with pytest.raises(ValueError, match="Webhook URL is required"):
            Merchant(
                id="0x1234567890123456789012345678901234567890",
                notification_type=NotificationType.WEBHOOK
            )

    def test_merchant_validation_missing_telegram_chat_id(self):
        """Test that Telegram merchants require chat ID."""
        with pytest.raises(ValueError, match="Telegram chat ID is required"):
            Merchant(
                id="0x1234567890123456789012345678901234567890",
                notification_type=NotificationType.TELEGRAM
            )

    def test_merchant_from_dict(self):
        """Test creating merchant from dictionary."""
        data = {
            'id': '0x1234567890123456789012345678901234567890',
            'notification_type': 'webhook',
            'name': 'Test',
            'webhook_url': 'https://example.com',
            'webhook_secret': 'secret123',
            'telegram_chat_id': None,
            'is_active': True
        }

        merchant = Merchant.from_dict(data)
        assert merchant.id == data['id']
        assert merchant.is_webhook()

    def test_merchant_short_id(self):
        """Test short ID generation."""
        merchant = Merchant.create_webhook_merchant(
            merchant_id="0x1234567890123456789012345678901234567890",
            webhook_url="https://example.com"
        )

        short = merchant.short_id()
        assert short == "0x1234...7890"


class TestPaymentEvent:
    """Tests for PaymentEvent model."""

    def test_create_from_graph_data(self):
        """Test creating payment event from Graph data."""
        data = {
            'paymentIntentId': 'pi_test123',
            'merchant': '0x1234567890123456789012345678901234567890',
            'customer': '0x0987654321098765432109876543210987654321',
            'token': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
            'amount': '100000000',
            'transactionHash': '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
            'blockNumber': '12345678',
            'blockTimestamp': '1706400000'
        }

        event = PaymentEvent.from_graph_data(data)

        assert event.payment_intent_id == 'pi_test123'
        assert event.merchant_id == data['merchant'].lower()
        assert event.amount == '100000000'
        assert event.block_number == 12345678

    def test_formatted_amount_usdc(self):
        """Test formatting USDC amounts."""
        event = PaymentEvent(
            payment_intent_id='pi_test',
            merchant_id='0x1234567890123456789012345678901234567890',
            customer_address='0x0987654321098765432109876543210987654321',
            token_address='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',  # USDC
            amount='100000000',  # 100 USDC
            transaction_hash='0xabc123',
            block_number=12345,
            block_timestamp=datetime.utcnow()
        )

        formatted = event.get_formatted_amount()
        assert formatted == "100.00 USDC"

    def test_event_id_generation(self):
        """Test event ID generation."""
        event = PaymentEvent(
            payment_intent_id='pi_test123',
            merchant_id='0x1234567890123456789012345678901234567890',
            customer_address='0x0987654321098765432109876543210987654321',
            token_address='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
            amount='100000000',
            transaction_hash='0xabcdef',
            block_number=12345,
            block_timestamp=datetime.utcnow()
        )

        event_id = event.get_event_id()
        assert event_id.startswith('evt_')
        assert 'abcdef' in event_id


class TestWebhookPayload:
    """Tests for WebhookPayload model."""

    def test_create_from_payment_event(self):
        """Test creating webhook payload from payment event."""
        event = PaymentEvent(
            payment_intent_id='pi_test123',
            merchant_id='0x1234567890123456789012345678901234567890',
            customer_address='0x0987654321098765432109876543210987654321',
            token_address='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
            amount='100000000',
            transaction_hash='0xabcdef',
            block_number=12345,
            block_timestamp=datetime.utcnow()
        )

        payload = WebhookPayload.from_payment_event(event)

        assert payload.event_type == 'payment.completed'
        assert payload.data['payment_intent_id'] == 'pi_test123'
        assert payload.data['amount'] == '100000000'

    def test_sign_payload(self):
        """Test HMAC signature generation."""
        event = PaymentEvent(
            payment_intent_id='pi_test123',
            merchant_id='0x1234567890123456789012345678901234567890',
            customer_address='0x0987654321098765432109876543210987654321',
            token_address='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
            amount='100000000',
            transaction_hash='0xabcdef',
            block_number=12345,
            block_timestamp=datetime.utcnow()
        )

        payload = WebhookPayload.from_payment_event(event)
        secret = 'test_secret_key'

        signature = payload.sign(secret)

        assert signature is not None
        assert len(signature) == 64  # SHA256 hex
        assert payload.signature == signature

    def test_verify_signature(self):
        """Test signature verification."""
        payload_dict = {
            'event_id': 'evt_test',
            'event_type': 'payment.completed',
            'timestamp': '2024-01-01T00:00:00Z',
            'data': {'amount': '100'}
        }

        secret = 'test_secret'
        import json
        import hmac
        import hashlib

        payload_json = json.dumps(payload_dict, separators=(',', ':'), sort_keys=True)
        signature = hmac.new(
            secret.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()

        assert WebhookPayload.verify_signature(payload_json, signature, secret)
        assert not WebhookPayload.verify_signature(payload_json, 'wrong_sig', secret)


class TestTelegramMessage:
    """Tests for TelegramMessage formatting."""

    def test_format_message(self):
        """Test Telegram message formatting."""
        event = PaymentEvent(
            payment_intent_id='pi_test123',
            merchant_id='0x1234567890123456789012345678901234567890',
            customer_address='0x0987654321098765432109876543210987654321',
            token_address='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
            amount='100000000',
            transaction_hash='0xabcdef1234567890',
            block_number=12345678,
            block_timestamp=datetime.utcnow()
        )

        msg = TelegramMessage(
            payment_event=event,
            etherscan_url='https://sepolia.etherscan.io'
        )

        formatted = msg.format()

        assert 'Payment Received!' in formatted
        assert '100.00 USDC' in formatted
        assert 'sepolia.etherscan.io' in formatted
        assert '12345678' in formatted


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
