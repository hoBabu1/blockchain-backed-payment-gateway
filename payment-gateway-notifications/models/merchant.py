"""
Merchant data model.

Represents a merchant registered in the payment gateway notification system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import secrets


class NotificationType(str, Enum):
    """Supported notification delivery methods."""
    WEBHOOK = "webhook"
    TELEGRAM = "telegram"


@dataclass
class Merchant:
    """
    Represents a merchant in the notification system.

    Attributes:
        id: Merchant's Ethereum address (0x-prefixed)
        notification_type: Preferred notification method
        name: Human-readable merchant name
        webhook_url: URL for webhook notifications
        webhook_secret: Secret for HMAC signature verification
        telegram_chat_id: Telegram chat ID for notifications
        is_active: Whether merchant is actively receiving notifications
        created_at: Timestamp when merchant was registered
        updated_at: Timestamp of last update
    """

    id: str
    notification_type: NotificationType
    name: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate and normalize merchant data."""
        # Ensure notification_type is an enum
        if isinstance(self.notification_type, str):
            self.notification_type = NotificationType(self.notification_type)

        # Normalize Ethereum address
        if self.id and not self.id.startswith('0x'):
            self.id = '0x' + self.id
        self.id = self.id.lower()

        # Validate based on notification type
        self.validate()

    def validate(self) -> None:
        """
        Validate merchant configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.id or len(self.id) != 42:
            raise ValueError("Invalid Ethereum address")

        if self.notification_type == NotificationType.WEBHOOK:
            if not self.webhook_url:
                raise ValueError("Webhook URL is required for webhook notifications")
            if not self.webhook_url.startswith(('http://', 'https://')):
                raise ValueError("Webhook URL must be a valid HTTP(S) URL")

        elif self.notification_type == NotificationType.TELEGRAM:
            if not self.telegram_chat_id:
                raise ValueError("Telegram chat ID is required for Telegram notifications")

    @classmethod
    def create_webhook_merchant(
        cls,
        merchant_id: str,
        webhook_url: str,
        name: Optional[str] = None
    ) -> 'Merchant':
        """
        Factory method to create a webhook merchant.

        Args:
            merchant_id: Merchant's Ethereum address
            webhook_url: URL for webhook notifications
            name: Optional merchant name

        Returns:
            Merchant configured for webhook notifications
        """
        return cls(
            id=merchant_id,
            notification_type=NotificationType.WEBHOOK,
            name=name,
            webhook_url=webhook_url,
            webhook_secret=cls.generate_secret()
        )

    @classmethod
    def create_telegram_merchant(
        cls,
        merchant_id: str,
        telegram_chat_id: str,
        name: Optional[str] = None
    ) -> 'Merchant':
        """
        Factory method to create a Telegram merchant.

        Args:
            merchant_id: Merchant's Ethereum address
            telegram_chat_id: Telegram chat ID
            name: Optional merchant name

        Returns:
            Merchant configured for Telegram notifications
        """
        return cls(
            id=merchant_id,
            notification_type=NotificationType.TELEGRAM,
            name=name,
            telegram_chat_id=telegram_chat_id
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Merchant':
        """
        Create Merchant from dictionary (e.g., database row).

        Args:
            data: Dictionary with merchant data

        Returns:
            Merchant instance
        """
        return cls(
            id=data['id'],
            notification_type=data['notification_type'],
            name=data.get('name'),
            webhook_url=data.get('webhook_url'),
            webhook_secret=data.get('webhook_secret'),
            telegram_chat_id=data.get('telegram_chat_id'),
            is_active=data.get('is_active', True),
            created_at=data.get('created_at', datetime.utcnow()),
            updated_at=data.get('updated_at', datetime.utcnow())
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Merchant to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'id': self.id,
            'notification_type': self.notification_type.value,
            'name': self.name,
            'webhook_url': self.webhook_url,
            'webhook_secret': self.webhook_secret,
            'telegram_chat_id': self.telegram_chat_id,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """
        Convert Merchant to dictionary for public API (excludes secrets).

        Returns:
            Dictionary representation without sensitive data
        """
        data = self.to_dict()
        # Remove sensitive fields
        if 'webhook_secret' in data:
            data['webhook_secret'] = '***' if data['webhook_secret'] else None
        return data

    @staticmethod
    def generate_secret(length: int = 32) -> str:
        """
        Generate a random secret for webhook signature verification.

        Args:
            length: Length of the secret in bytes

        Returns:
            Hex-encoded secret string
        """
        return secrets.token_hex(length)

    def is_webhook(self) -> bool:
        """Check if merchant uses webhook notifications."""
        return self.notification_type == NotificationType.WEBHOOK

    def is_telegram(self) -> bool:
        """Check if merchant uses Telegram notifications."""
        return self.notification_type == NotificationType.TELEGRAM

    def short_id(self) -> str:
        """Get shortened merchant ID for display."""
        if len(self.id) > 10:
            return f"{self.id[:6]}...{self.id[-4:]}"
        return self.id

    def __repr__(self) -> str:
        return (
            f"Merchant(id={self.short_id()}, "
            f"type={self.notification_type.value}, "
            f"active={self.is_active})"
        )
