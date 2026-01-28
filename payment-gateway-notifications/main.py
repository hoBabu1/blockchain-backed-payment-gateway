#!/usr/bin/env python3
"""
Payment Gateway Notifications Service.

Main entry point that orchestrates all notification services:
- Graph listener for blockchain events
- Webhook delivery service
- Telegram notification service
- Merchant registration API

Usage:
    python main.py

Environment variables:
    See .env.example for all configuration options.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from aiohttp import web

from config import config
from database.db import Database, close_db
from services.graph_listener import GraphListener
from services.webhook_service import WebhookService
from services.telegram_service import TelegramService
from services.notification_router import NotificationRouter
from api.merchant_api import create_app


# Configure logging
def setup_logging():
    """Configure logging based on config."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)

    handlers = [logging.StreamHandler(sys.stdout)]

    if config.logging.file:
        # Ensure log directory exists
        log_dir = os.path.dirname(config.logging.file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(config.logging.file))

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )

    # Reduce noise from third-party libraries
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


class PaymentNotificationService:
    """
    Main service orchestrator.

    Coordinates all components of the notification system:
    - Database connection
    - Graph listener for blockchain events
    - Webhook and Telegram delivery services
    - Notification router
    - REST API server
    """

    def __init__(self):
        self.db: Optional[Database] = None
        self.graph_listener: Optional[GraphListener] = None
        self.webhook_service: Optional[WebhookService] = None
        self.telegram_service: Optional[TelegramService] = None
        self.notification_router: Optional[NotificationRouter] = None
        self.api_app: Optional[web.Application] = None
        self.api_runner: Optional[web.AppRunner] = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start all services."""
        logger.info("=" * 60)
        logger.info(f"Starting {config.service.name}")
        logger.info("=" * 60)

        # Validate configuration
        errors = config.validate()
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            raise ValueError("Invalid configuration")

        # Initialize database
        logger.info("Initializing database...")
        self.db = Database()
        await self.db.connect()
        await self.db.init_schema()

        # Initialize services
        logger.info("Initializing services...")

        # Webhook service
        self.webhook_service = WebhookService(self.db)
        await self.webhook_service.start()

        # Telegram service
        self.telegram_service = TelegramService(self.db)
        await self.telegram_service.start()

        # Notification router
        self.notification_router = NotificationRouter(
            db=self.db,
            webhook_service=self.webhook_service,
            telegram_service=self.telegram_service
        )
        await self.notification_router.start()

        # Graph listener
        self.graph_listener = GraphListener(
            db=self.db,
            polling_interval=config.graph.polling_interval
        )

        # Register callback for payment events
        self.graph_listener.on_payment(self._handle_payment)

        await self.graph_listener.start()

        # Start API server
        logger.info("Starting API server...")
        self.api_app = create_app(
            db=self.db,
            webhook_service=self.webhook_service,
            telegram_service=self.telegram_service
        )

        self.api_runner = web.AppRunner(self.api_app)
        await self.api_runner.setup()

        site = web.TCPSite(
            self.api_runner,
            config.api.host,
            config.api.port
        )
        await site.start()

        logger.info("=" * 60)
        logger.info(f"Service started successfully!")
        logger.info(f"API server running at http://{config.api.host}:{config.api.port}")
        logger.info(f"Network: {config.network.network}")
        logger.info("=" * 60)

    async def stop(self) -> None:
        """Stop all services gracefully."""
        logger.info("Initiating graceful shutdown...")

        # Stop accepting new requests
        if self.api_runner:
            await self.api_runner.cleanup()

        # Stop Graph listener
        if self.graph_listener:
            await self.graph_listener.stop()

        # Stop notification router
        if self.notification_router:
            await self.notification_router.stop()

        # Stop delivery services
        if self.webhook_service:
            await self.webhook_service.stop()

        if self.telegram_service:
            await self.telegram_service.stop()

        # Close database
        await close_db()

        logger.info("Shutdown complete")
        self._shutdown_event.set()

    async def _handle_payment(self, event) -> None:
        """
        Handle a payment event from the Graph listener.

        Routes the notification to the appropriate service.
        """
        try:
            await self.notification_router.route_notification(event)
        except Exception as e:
            logger.error(f"Error handling payment event: {e}", exc_info=True)

    async def run(self) -> None:
        """Run the service until shutdown signal."""
        await self.start()

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        """Request service shutdown."""
        asyncio.create_task(self.stop())


def handle_signal(service: PaymentNotificationService, sig: signal.Signals) -> None:
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig.name}, initiating shutdown...")
    service.request_shutdown()


async def main() -> None:
    """Main entry point."""
    setup_logging()

    service = PaymentNotificationService()

    # Set up signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: handle_signal(service, s)
        )

    try:
        await service.run()
    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
        await service.stop()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
