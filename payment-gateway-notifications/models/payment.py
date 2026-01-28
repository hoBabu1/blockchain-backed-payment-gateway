"""
Payment data models.

Represents payment events and webhook payloads.
"""

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional


# Common token decimals mapping
TOKEN_DECIMALS = {
    # USDC on various networks
    '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 6,  # Mainnet USDC
    '0x1c7d4b196cb0c7b01d743fbc6116a902379c7238': 6,  # Sepolia USDC
    # USDT
    '0xdac17f958d2ee523a2206206994597c13d831ec7': 6,  # Mainnet USDT
    # DAI
    '0x6b175474e89094c44da98b954eedeac495271d0f': 18,  # Mainnet DAI
}

# Token symbol mapping
TOKEN_SYMBOLS = {
    '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USDC',
    '0x1c7d4b196cb0c7b01d743fbc6116a902379c7238': 'USDC',
    '0xdac17f958d2ee523a2206206994597c13d831ec7': 'USDT',
    '0x6b175474e89094c44da98b954eedeac495271d0f': 'DAI',
}


@dataclass
class PaymentEvent:
    """
    Represents a payment event from the blockchain.

    This is the data extracted from PaymentExecuted events
    emitted by the smart contract.
    """

    # Unique payment intent ID from the contract
    payment_intent_id: str

    # Merchant's Ethereum address
    merchant_id: str

    # Customer's Ethereum address
    customer_address: str

    # Token contract address
    token_address: str

    # Amount in token's smallest unit (e.g., wei)
    amount: str

    # Transaction hash
    transaction_hash: str

    # Block number where transaction was mined
    block_number: int

    # Block timestamp
    block_timestamp: datetime

    # Event status
    status: str = "completed"

    # When the event was processed locally
    processed_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Normalize addresses to lowercase."""
        self.merchant_id = self.merchant_id.lower()
        self.customer_address = self.customer_address.lower()
        self.token_address = self.token_address.lower()
        self.transaction_hash = self.transaction_hash.lower()

    @classmethod
    def from_graph_data(cls, data: Dict[str, Any]) -> 'PaymentEvent':
        """
        Create PaymentEvent from The Graph query result.

        Args:
            data: Dictionary from Graph query

        Returns:
            PaymentEvent instance
        """
        # Parse block timestamp (Graph returns Unix timestamp as string)
        timestamp = data.get('blockTimestamp') or data.get('timestamp')
        if isinstance(timestamp, str):
            block_timestamp = datetime.fromtimestamp(int(timestamp))
        elif isinstance(timestamp, int):
            block_timestamp = datetime.fromtimestamp(timestamp)
        else:
            block_timestamp = datetime.utcnow()

        return cls(
            payment_intent_id=data.get('paymentIntentId') or data.get('id'),
            merchant_id=data.get('merchant') or data.get('merchantId'),
            customer_address=data.get('customer') or data.get('customerAddress'),
            token_address=data.get('token') or data.get('tokenAddress'),
            amount=str(data.get('amount', '0')),
            transaction_hash=data.get('transactionHash') or data.get('txHash'),
            block_number=int(data.get('blockNumber', 0)),
            block_timestamp=block_timestamp,
            status='completed'
        )

    def get_token_symbol(self) -> str:
        """Get human-readable token symbol."""
        return TOKEN_SYMBOLS.get(self.token_address, 'TOKEN')

    def get_token_decimals(self) -> int:
        """Get token decimals for formatting."""
        return TOKEN_DECIMALS.get(self.token_address, 18)

    def get_formatted_amount(self) -> str:
        """
        Get human-readable formatted amount.

        Returns:
            Amount with proper decimal places and symbol
        """
        decimals = self.get_token_decimals()
        amount_int = int(self.amount)
        amount_decimal = Decimal(amount_int) / Decimal(10 ** decimals)

        # Format with appropriate precision
        if decimals <= 6:
            formatted = f"{amount_decimal:.2f}"
        else:
            formatted = f"{amount_decimal:.4f}"

        return f"{formatted} {self.get_token_symbol()}"

    def short_customer_address(self) -> str:
        """Get shortened customer address for display."""
        return f"{self.customer_address[:6]}...{self.customer_address[-4:]}"

    def short_merchant_address(self) -> str:
        """Get shortened merchant address for display."""
        return f"{self.merchant_id[:6]}...{self.merchant_id[-4:]}"

    def short_payment_id(self) -> str:
        """Get shortened payment ID for display."""
        if len(self.payment_intent_id) > 20:
            return f"{self.payment_intent_id[:10]}...{self.payment_intent_id[-6:]}"
        return self.payment_intent_id

    def get_event_id(self) -> str:
        """Generate unique event ID for deduplication."""
        return f"evt_{self.transaction_hash}_{self.payment_intent_id}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'payment_intent_id': self.payment_intent_id,
            'merchant_id': self.merchant_id,
            'customer_address': self.customer_address,
            'token_address': self.token_address,
            'amount': self.amount,
            'transaction_hash': self.transaction_hash,
            'block_number': self.block_number,
            'block_timestamp': self.block_timestamp.isoformat(),
            'status': self.status,
            'processed_at': self.processed_at.isoformat()
        }


@dataclass
class WebhookPayload:
    """
    Webhook payload to be sent to merchants.

    Contains the payment event data along with metadata
    for verification and processing.
    """

    event_id: str
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    signature: Optional[str] = None

    @classmethod
    def from_payment_event(
        cls,
        event: PaymentEvent,
        event_type: str = "payment.completed"
    ) -> 'WebhookPayload':
        """
        Create webhook payload from payment event.

        Args:
            event: PaymentEvent to convert
            event_type: Type of event (default: payment.completed)

        Returns:
            WebhookPayload instance
        """
        return cls(
            event_id=event.get_event_id(),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            data={
                'payment_intent_id': event.payment_intent_id,
                'merchant_id': event.merchant_id,
                'customer_address': event.customer_address,
                'token_address': event.token_address,
                'amount': event.amount,
                'formatted_amount': event.get_formatted_amount(),
                'transaction_hash': event.transaction_hash,
                'block_number': event.block_number,
                'block_timestamp': event.block_timestamp.isoformat(),
                'status': event.status
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'data': self.data,
            'signature': self.signature
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), separators=(',', ':'))

    def sign(self, secret: str) -> str:
        """
        Generate HMAC signature for the payload.

        Args:
            secret: Secret key for signing

        Returns:
            Hex-encoded HMAC-SHA256 signature
        """
        # Create a copy without signature for signing
        payload_dict = self.to_dict()
        payload_dict.pop('signature', None)

        payload_json = json.dumps(payload_dict, separators=(',', ':'), sort_keys=True)
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        self.signature = signature
        return signature

    @staticmethod
    def verify_signature(payload_json: str, signature: str, secret: str) -> bool:
        """
        Verify HMAC signature of a payload.

        Args:
            payload_json: JSON string of payload (without signature)
            signature: Signature to verify
            secret: Secret key

        Returns:
            True if signature is valid
        """
        expected = hmac.new(
            secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)


@dataclass
class TelegramMessage:
    """
    Formatted message for Telegram notifications.

    Formats payment events into user-friendly Telegram messages
    with proper formatting and links.
    """

    payment_event: PaymentEvent
    etherscan_url: str = "https://sepolia.etherscan.io"

    def format(self) -> str:
        """
        Format the payment event as a Telegram message.

        Returns:
            Formatted message string with emojis and links
        """
        event = self.payment_event
        tx_link = f"{self.etherscan_url}/tx/{event.transaction_hash}"

        message = f"""🎉 *Payment Received!*

💰 *Amount:* {event.get_formatted_amount()}
👤 *Customer:* `{event.short_customer_address()}`
📝 *Payment ID:* `{event.short_payment_id()}`

🔗 [View Transaction]({tx_link})

⏰ *Time:* {event.block_timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC
📦 *Block:* #{event.block_number}

---
_Powered by PaymentGateway_"""

        return message

    def format_plain(self) -> str:
        """
        Format as plain text (no markdown).

        Returns:
            Plain text message
        """
        event = self.payment_event
        tx_link = f"{self.etherscan_url}/tx/{event.transaction_hash}"

        return f"""Payment Received!

Amount: {event.get_formatted_amount()}
Customer: {event.short_customer_address()}
Payment ID: {event.short_payment_id()}

View Transaction: {tx_link}

Time: {event.block_timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC
Block: #{event.block_number}

---
Powered by PaymentGateway"""
