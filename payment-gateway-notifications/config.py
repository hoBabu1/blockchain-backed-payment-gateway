"""
Configuration module for Payment Gateway Notifications service.

Loads settings from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class GraphConfig:
    """The Graph subgraph configuration."""
    url: str
    polling_interval: int = 5


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    url: str


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str


@dataclass
class NetworkConfig:
    """Blockchain network configuration."""
    network: str
    etherscan_url: str


@dataclass
class APIConfig:
    """API server configuration."""
    host: str
    port: int


@dataclass
class WebhookConfig:
    """Webhook delivery configuration."""
    timeout: int
    max_retries: int
    retry_delays: List[int]  # Delays in minutes


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str
    file: Optional[str]


@dataclass
class ServiceConfig:
    """Service-level configuration."""
    name: str
    shutdown_timeout: int


class Config:
    """
    Main configuration class that aggregates all config sections.

    Usage:
        from config import config

        print(config.graph.url)
        print(config.telegram.bot_token)
    """

    def __init__(self):
        self._load_config()

    def _load_config(self):
        """Load all configuration from environment variables."""

        # The Graph configuration
        self.graph = GraphConfig(
            url=os.getenv('SUBGRAPH_URL', ''),
            polling_interval=int(os.getenv('POLLING_INTERVAL', '5'))
        )

        # Database configuration
        self.database = DatabaseConfig(
            url=os.getenv('DATABASE_URL', 'sqlite:///./payment_notifications.db')
        )

        # Telegram configuration
        self.telegram = TelegramConfig(
            bot_token=os.getenv('TELEGRAM_BOT_TOKEN', '')
        )

        # Network configuration
        self.network = NetworkConfig(
            network=os.getenv('NETWORK', 'sepolia'),
            etherscan_url=os.getenv('ETHERSCAN_URL', 'https://sepolia.etherscan.io')
        )

        # API configuration
        self.api = APIConfig(
            host=os.getenv('API_HOST', '0.0.0.0'),
            port=int(os.getenv('API_PORT', '8000'))
        )

        # Webhook configuration
        retry_delays_str = os.getenv('WEBHOOK_RETRY_DELAYS', '1,5,15,60')
        retry_delays = [int(d.strip()) for d in retry_delays_str.split(',')]

        self.webhook = WebhookConfig(
            timeout=int(os.getenv('WEBHOOK_TIMEOUT', '30')),
            max_retries=int(os.getenv('WEBHOOK_MAX_RETRIES', '4')),
            retry_delays=retry_delays
        )

        # Logging configuration
        self.logging = LoggingConfig(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            file=os.getenv('LOG_FILE')
        )

        # Service configuration
        self.service = ServiceConfig(
            name=os.getenv('SERVICE_NAME', 'PaymentGatewayNotifications'),
            shutdown_timeout=int(os.getenv('SHUTDOWN_TIMEOUT', '30'))
        )

    def validate(self) -> List[str]:
        """
        Validate required configuration values.

        Returns:
            List of validation error messages (empty if all valid)
        """
        errors = []

        if not self.graph.url:
            errors.append("SUBGRAPH_URL is required")

        if not self.telegram.bot_token:
            errors.append("TELEGRAM_BOT_TOKEN is required")

        if not self.database.url:
            errors.append("DATABASE_URL is required")

        return errors

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0


# Global configuration instance
config = Config()
